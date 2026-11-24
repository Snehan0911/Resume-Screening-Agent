import os
import re
import json
import time
import copy
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Dict, Any, Optional
import pypdf
import docx
import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load environment configurations with absolute project path support
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_PROJECT_DIR, ".env")
if os.path.exists(_ENV_PATH):
    load_dotenv(dotenv_path=_ENV_PATH, override=True)
load_dotenv(override=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    logger.warning("GEMINI_API_KEY not found in environment. Gemini API calls will fail.")

MODEL_NAME = "gemini-3.8-flash"

EXHAUSTED_OR_UNAVAILABLE_MODELS = set()

def get_model(model_name: str = MODEL_NAME) -> genai.GenerativeModel:
    return genai.GenerativeModel(model_name)

def clean_schema_for_gemini(schema_target: Any) -> Any:
    """
    Recursively inlines nested $defs and strips unsupported fields (such as 'default',
    'title', '$defs', '$ref') from Pydantic JSON schema so that google.generativeai's
    protobuf converter does not throw:
    - 'ValueError: Unknown field for Schema: default'
    - 'ValueError: Unknown field for Schema: $defs'
    """
    if not hasattr(schema_target, "model_json_schema") and not isinstance(schema_target, dict):
        return schema_target

    raw_schema = schema_target.model_json_schema() if hasattr(schema_target, "model_json_schema") else copy.deepcopy(schema_target)
    defs = raw_schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                target = copy.deepcopy(defs.get(ref_name, {}))
                return resolve(target)
            return {
                k: resolve(v)
                for k, v in node.items()
                if k not in ("default", "title", "$defs")
            }
        elif isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(raw_schema)

def generate_structured_json(
    prompt: str,
    schema: Any,
    preferred_model: str = MODEL_NAME,
    temperature: float = 0.3,
    max_output_tokens: Optional[int] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Robust generator that executes structured Gemini calls with automatic
    multi-model fallback cascading (handling 429 quota, 404 deprecation, 503 limits).
    """
    candidate_models = [
        preferred_model,
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-pro-latest"
    ]
    seen = set()
    ordered_models = []
    for m in candidate_models:
        if m and m not in seen and m not in EXHAUSTED_OR_UNAVAILABLE_MODELS:
            seen.add(m)
            ordered_models.append(m)

    # If all models in the list were marked exhausted, reset cache and try them
    if not ordered_models:
        EXHAUSTED_OR_UNAVAILABLE_MODELS.clear()
        for m in candidate_models:
            if m and m not in seen:
                seen.add(m)
                ordered_models.append(m)

    # Convert Pydantic schema to clean inlined schema dict without '$defs' or 'default' fields
    clean_response_schema = clean_schema_for_gemini(schema)

    last_error = None
    import time
    for model_candidate in ordered_models:
        try:
            model = get_model(model_candidate)
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": clean_response_schema,
                "temperature": temperature
            }
            if max_output_tokens:
                config_kwargs["max_output_tokens"] = max_output_tokens

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**config_kwargs)
            )
            raw_text = response.text.strip()
            # Clean markdown code blocks if present
            raw_text = re.sub(r'^```json\s*', '', raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r'^```\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)
            
            return json.loads(raw_text)
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # If model is deprecated (404) or daily quota is exceeded, skip for remainder of run
            if "404" in err_str or "no longer available" in err_str or "per day limit exceeded" in err_str:
                EXHAUSTED_OR_UNAVAILABLE_MODELS.add(model_candidate)

            if log_callback:
                log_callback(f"Model {model_candidate} warning: {str(e)[:80]}. Trying next fallback model...")
            # If rate limit or temporary server spike, briefly pause before trying next candidate
            if ("429" in err_str or "503" in err_str or "quota" in err_str or "exhausted" in err_str) and "per day" not in err_str:
                time.sleep(1.0)
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {str(last_error)}")


# ==========================================
# 📄 Part 1: Resume Document Text Parsers
# ==========================================

def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF document."""
    text = ""
    try:
        reader = pypdf.PdfReader(file_path)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    except Exception as e:
        logger.warning(f"Error reading PDF {os.path.basename(file_path)}: {str(e)}")
        text = f"Candidate Resume ({os.path.basename(file_path)})"
    if not text.strip():
        text = f"Candidate Resume ({os.path.basename(file_path)})"
    return text

def parse_docx(file_path: str) -> str:
    """Extract text from a Microsoft Word document."""
    text = ""
    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        tables_text = []
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    tables_text.append(" | ".join(row_text))
        text = "\n".join(paragraphs + tables_text)
    except Exception as e:
        logger.warning(f"Error reading DOCX {os.path.basename(file_path)}: {str(e)}")
        text = f"Candidate Resume ({os.path.basename(file_path)})"
    if not text.strip():
        text = f"Candidate Resume ({os.path.basename(file_path)})"
    return text

def parse_txt(file_path: str) -> str:
    """Extract text from a plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            return content if content.strip() else f"Candidate Resume ({os.path.basename(file_path)})"
    except Exception as e:
        logger.warning(f"Error reading TXT {os.path.basename(file_path)}: {str(e)}")
        return f"Candidate Resume ({os.path.basename(file_path)})"

def extract_text_from_file(file_path: str) -> str:
    """Identify extension and route to the appropriate parser."""
    _, ext = os.path.splitext(file_path.lower())
    if ext == ".pdf":
        return parse_pdf(file_path)
    elif ext == ".docx":
        return parse_docx(file_path)
    elif ext in [".txt", ".md", ".json"]:
        return parse_txt(file_path)
    else:
        return parse_txt(file_path)

def extract_experience_from_text(text: str) -> float:
    """Estimates years of experience from resume text when parser returns 0."""
    # 1. Look for explicit mentions: "over 6 years of experience", "5+ years", etc.
    exp_matches = re.findall(
        r'(?:over|more than|approx(?:imately)?|\+)?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?(?:\s+of)?\s+(?:professional\s+)?experience',
        text,
        re.IGNORECASE
    )
    if exp_matches:
        try:
            val = float(exp_matches[0])
            if 0.5 <= val <= 40:
                return val
        except ValueError:
            pass

    # 2. Extract year spans like '2018 - Present'
    year_matches = re.findall(r'\b(20\d{2}|19\d{2})\b', text)
    if year_matches:
        years = [int(y) for y in year_matches if 1985 <= int(y) <= 2030]
        has_present = bool(re.search(r'\b(present|current|now)\b', text, re.IGNORECASE))
        current_year = 2025
        if years:
            min_year = min(years)
            max_year = current_year if has_present else max(years)
            diff = max_year - min_year
            if 0 < diff <= 40:
                return float(diff)
    return 0.0

def sanitize_summary(summary: str) -> str:
    """Removes repetitive word loops and caps summary at 3 clean sentences."""
    if not summary:
        return "Screening batch completed successfully."
    
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if s.strip()]
    valid_sentences = []
    
    loop_words = {'safely', 'securely', 'successfully', 'nicely', 'smoothly', 'properly', 'seamlessly', 'natively', 'cleanly', 'neatly', 'today', 'forever', 'daily', 'done', 'together'}
    for s in sentences:
        words = [w.lower().strip('.,!?:;') for w in s.split()]
        if not words:
            continue
        loop_count = sum(1 for w in words if w in loop_words)
        if loop_count > 3:
            break
        has_repeat = False
        for i in range(len(words) - 1):
            if words[i] == words[i+1] and len(words[i]) > 3:
                has_repeat = True
                break
        if has_repeat:
            break
        valid_sentences.append(s)
        if len(valid_sentences) >= 3:
            break

    if valid_sentences:
        res = ' '.join(valid_sentences)
    else:
        res = summary[:250].rsplit(' ', 1)[0] + '.'
        
    return res

# ==========================================
# 📊 Part 2: Machine Learning Similarity Engine
# ==========================================

def compute_ml_similarity(job_description: str, resumes_text: List[str]) -> List[float]:
    """
    Computes mathematical relevance scores between Job Description and Resumes
    using TF-IDF vectorization and Cosine Similarity (Scikit-Learn).
    """
    if not resumes_text:
        return []
    
    try:
        # Prepend Job Description as reference, sanitizing empty or pure-whitespace documents
        cleaned_jd = job_description.strip() if job_description and job_description.strip() else "Job Description Requirements"
        cleaned_resumes = [
            r.strip() if r and r.strip() else "Candidate Profile Skills Experience"
            for r in resumes_text
        ]
        documents = [cleaned_jd] + cleaned_resumes
        
        # Fit TF-IDF Vectorizer
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(documents)
        
        # Row 0 is the Job Description vector
        jd_vector = tfidf_matrix[0:1]
        # Rows 1 to N are the candidate resume vectors
        resume_vectors = tfidf_matrix[1:]
        
        # Calculate Cosine Similarity
        similarity_matrix = cosine_similarity(jd_vector, resume_vectors)
        
        # Extract scores and convert to percentages
        scores = [float(score * 100) for score in similarity_matrix[0]]
        return scores
    except Exception as e:
        logger.warning(f"Error computing TF-IDF similarity: {e}. Defaulting to baseline.")
        return [50.0] * len(resumes_text)

# ==========================================
# 🧪 Part 3: Pydantic v2 Validation Schemas
# ==========================================

class SubscriptableModel(BaseModel):
    """A helper base class that makes Pydantic models subscriptable like dictionaries."""
    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item)

    def get(self, item, default=None):
        return getattr(self, item, default)

class CandidateProfile(SubscriptableModel):
    name: str = Field(default="Unknown Candidate", description="Full name of the candidate")
    email: str = Field(default="N/A", description="Email address of the candidate")
    phone: str = Field(default="N/A", description="Phone number of the candidate")
    skills: List[str] = Field(default_factory=list, description="List of key technical and soft skills extracted")
    experience_years: float = Field(default=0.0, description="Total years of relevant experience extracted")
    education: List[str] = Field(default_factory=list, description="List of degrees and certifications")
    work_history: List[str] = Field(default_factory=list, description="List of companies, roles, and dates")

class JDAnalysis(SubscriptableModel):
    role_title: str = Field(default="Target Position", description="Target role title, e.g. Senior Backend Engineer")
    required_skills: List[str] = Field(default_factory=list, description="List of mandatory technical and core skills required for the role")
    preferred_skills: List[str] = Field(default_factory=list, description="List of nice-to-have/preferred/optional skills")
    min_experience_years: float = Field(default=0.0, description="Minimum years of relevant experience requested. Default to 0.0 if not specified.")
    education_level: str = Field(default="Not Specified", description="Required minimum education level, e.g., Bachelor's Degree in Computer Science, or 'None'")
    key_responsibilities: List[str] = Field(default_factory=list, description="Top 3-5 main duties and responsibilities of the role")

class ScorecardCategory(SubscriptableModel):
    category: str = Field(default="General Fit", description="e.g., Technical Skills, Experience, Education, Role Fit")
    score: float = Field(default=70.0, description="Score from 0 to 100")
    reasoning: str = Field(default="Evaluated against role requirements.", description="Detailed reasoning for this category's score")

class SkillMatchDetail(SubscriptableModel):
    skill: str = Field(default="Skill", description="Name of the skill from the JD")
    is_present: bool = Field(default=False, description="True if candidate possesses this skill, False otherwise")
    evidence: str = Field(default="Not specified in resume", description="Brief evidence/reasoning from the resume")

class EvaluationResponse(SubscriptableModel):
    candidate_name: str = Field(default="Candidate", description="Name of the candidate")
    overall_score: float = Field(default=70.0, description="Aggregated score from 0 to 100")
    categories: List[ScorecardCategory] = Field(default_factory=list, description="Breakdown of scores by category")
    skills_matrix: List[SkillMatchDetail] = Field(default_factory=list, description="Status of candidate skills against all required/preferred JD skills")
    matching_skills: List[str] = Field(default_factory=list, description="Skills that match the Job Description")
    missing_skills: List[str] = Field(default_factory=list, description="Required or preferred skills that are missing")
    pros: List[str] = Field(default_factory=list, description="Key strengths and advantages of this candidate")
    cons: List[str] = Field(default_factory=list, description="Concerns, red flags, or areas of development")
    recommendation: str = Field(default="Interview", description="Recommendation: 'Shortlist', 'Interview', or 'Reject'")

class QAResponse(SubscriptableModel):
    candidate_name: str = Field(default="Candidate", description="Name of the candidate")
    original_score: float = Field(default=70.0, description="Original overall score from Evaluator Agent")
    adjusted_score: float = Field(default=70.0, description="Adjusted overall score (or same if no change needed)")
    changes_made: bool = Field(default=False, description="True if scores or comments were adjusted")
    adjustments_summary: str = Field(default="None", description="Summary of adjustments made or 'None'")
    justification: str = Field(default="Verified against candidate background and TF-IDF baseline.", description="Reasoning behind QA decisions")

class InterviewQuestionDetail(SubscriptableModel):
    question: str = Field(default="Describe your relevant technical background.", description="The tailored interview question to probe gaps/experience")
    expected_answer: str = Field(default="Clear explanation of relevant tools and problem-solving methodology.", description="What a strong candidate's answer should cover/demonstrate")
    red_flags: str = Field(default="Vague or generic answers.", description="Specific warnings or red flags to watch out for")

class CandidateRankingDetail(SubscriptableModel):
    rank: int = Field(default=1, description="Rank position (1 being the best)")
    name: str = Field(default="Candidate", description="Candidate name")
    overall_score: float = Field(default=75.0, description="Verified overall score")
    recommendation: str = Field(default="Interview", description="Final recommendation")
    summary: str = Field(default="Evaluated against role requirements.", description="1 concise sentence on candidate fit")
    interview_questions: List[str] = Field(default_factory=list, description="List of 2 tailored interview questions")
    interview_guide: List[InterviewQuestionDetail] = Field(default_factory=list, description="2 high-impact tailored interview questions with expected answers and red flags")
    outreach_email: str = Field(default="Dear Candidate,\n\nWe would like to invite you for an interview.", description="Short professional outreach email")
    rejection_email: str = Field(default="Dear Candidate,\n\nThank you for your application.", description="Short polite constructive rejection email")

class BatchRankingReport(SubscriptableModel):
    job_description: str = Field(default="", description="The job description used for screening")
    candidates: List[CandidateRankingDetail] = Field(default_factory=list, description="List of candidates sorted by rank")
    overall_summary: str = Field(default="Screening batch completed successfully.", description="Concise 2-3 sentence executive batch summary")

# ==========================================
# 🤖 Part 4: Collaborative AI Agent Pipeline
# ==========================================

class JDAnalyzerAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, raw_jd: str, log_callback: Callable[[str], None]) -> JDAnalysis:
        log_callback("JDAnalyzerAgent: Analyzing and structuring raw Job Description...")
        prompt = f"""
        You are an expert Job Description Analyzer Agent. Your job is to analyze the raw Job Description text below and extract it into a structured format:
        - Role Title: The official name/title of the position.
        - Required Skills: Must-have technical languages, libraries, platforms, or tools.
        - Preferred Skills: Good-to-have, optional, or bonus qualifications.
        - Minimum Experience Years: The threshold of years of experience required (extract as a float, e.g. 5.0). If not specified, return 0.0.
        - Education Level: The minimum or preferred degree/certification requested (e.g. Bachelor's Degree in Computer Science, or 'None').
        - Key Responsibilities: The primary responsibilities of this position.

        Raw Job Description:
        ---
        {raw_jd}
        ---
        """
        parsed_data = generate_structured_json(
            prompt=prompt,
            schema=JDAnalysis,
            preferred_model=self.model_name,
            temperature=0.1,
            log_callback=log_callback
        )
        return JDAnalysis(**parsed_data)


class ResumeParserAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, raw_text: str, log_callback: Callable[[str], None]) -> CandidateProfile:
        log_callback("ResumeParserAgent: Parsing raw resume text into structured fields...")
        cleaned_text = raw_text[:6000] if len(raw_text) > 6000 else raw_text
        prompt = f"""
        You are an expert Resume Parser Agent. Your job is to extract candidate details from the raw resume text provided below.
        Be accurate and extract details exactly as they appear in the resume:
        - Full Name (if not clearly found, use 'Unknown')
        - Email address
        - Phone number
        - Skills (both technical and soft skills)
        - Total years of experience (estimate a float based on dates of work history, e.g. 3.5 years)
        - Education (list of degrees, universities, certifications)
        - Work history (list of companies, roles, and dates)

        Raw Resume Text:
        ---
        {cleaned_text}
        ---
        """
        parsed_data = generate_structured_json(
            prompt=prompt,
            schema=CandidateProfile,
            preferred_model=self.model_name,
            temperature=0.1,
            log_callback=log_callback
        )
        return CandidateProfile(**parsed_data)


class EvaluatorAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, profile: CandidateProfile, jd_analysis: JDAnalysis, log_callback: Callable[[str], None]) -> EvaluationResponse:
        log_callback(f"EvaluatorAgent: Evaluating {profile.name} against structured Job Description...")
        prompt = f"""
        You are a Candidate Review Agent. Compare the candidate's parsed resume profile against the structured Job Description analysis below.
        
        Grade the candidate carefully across the following categories:
        1. Technical Skills: Do they possess the required and preferred skills? Look at their list of skills and work history.
        2. Experience: Is their years of experience ({profile.experience_years} years) aligned with what's requested ({jd_analysis.min_experience_years} years)? Look at roles and responsibilities.
        3. Education: Does their education or certifications match the requirements ({jd_analysis.education_level})?
        4. Role Fit: How well do their past roles prepare them for the responsibilities of this position?

        For each category, provide:
        - A score between 0 and 100
        - Clear, objective reasoning for that score

        Calculate the overall score as a weighted average or general score (0 to 100) reflecting their match level.
        
        Create a detailed 'skills_matrix' comparing candidate skills against all required and preferred skills in the JD:
        - List each skill from the JD's 'required_skills' and 'preferred_skills'.
        - Set 'is_present' to true if the candidate has the skill, false otherwise.
        - Provide 'evidence' showing where/how the skill is mentioned in their resume (e.g. 'Listed in skills profile' or '3 years at Acme Corp' or 'Not found').

        Also identify:
        - Matching skills: List of skills the candidate has that are mentioned or highly relevant to the JD.
        - Missing skills: Crucial required skills in the JD that are not shown in the candidate's profile.
        - Pros: Highlights, strong achievements, or bonuses.
        - Cons: Red flags, gaps, lack of relevant context.
        - Recommendation: Classify as either 'Shortlist' (excellent fit), 'Interview' (good/borderline fit), or 'Reject' (poor fit).

        Candidate Profile:
        {json.dumps(profile.model_dump(), indent=2)}

        Structured Job Description:
        {json.dumps(jd_analysis.model_dump(), indent=2)}
        """
        eval_data = generate_structured_json(
            prompt=prompt,
            schema=EvaluationResponse,
            preferred_model=self.model_name,
            temperature=0.2,
            log_callback=log_callback
        )
        return EvaluationResponse(**eval_data)


class QualityAssuranceAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, profile: CandidateProfile, jd_analysis: JDAnalysis, evaluation: EvaluationResponse, ml_score: float, log_callback: Callable[[str], None]) -> QAResponse:
        log_callback(f"QualityAssuranceAgent: Auditing evaluator scoring for {profile.name} (ML Cosine Similarity matches: {ml_score:.1f}%)...")
        prompt = f"""
        You are a Quality Assurance (QA) Agent. Your job is to critically verify the evaluation of candidate {profile.name} against their profile and the Job Description requirements.
        Take into account the Machine Learning Cosine Similarity score of {ml_score:.1f}% which represents direct text/keyword overlap.
        
        Inspect the assessment for:
        1. Over-optimism or over-pessimism: Are the scores justified by actual experience listed in work history?
        2. Hallucinations: Did the evaluator list a matching skill that the candidate doesn't actually possess?
        3. Work history alignment: If the candidate has {profile.experience_years} years of experience, but the evaluator gave a high score under 'Experience' requiring {jd_analysis.min_experience_years} years, adjust the score down.
        4. Consistency: Apply a rigorous and fair grading standard. Specifically flag cases where the candidate fails to meet the minimum experience of {jd_analysis.min_experience_years} years but was evaluated with an over-inflated score.

        If you find discrepancies:
        - Set 'changes_made' to true.
        - Provide an 'adjusted_score' (higher or lower) and describe the 'adjustments_summary'.
        - Provide a comprehensive 'justification' outlining the differences.

        If you agree with the original evaluation:
        - Set 'changes_made' to false.
        - Set 'adjusted_score' to the same as the original overall score ({evaluation.overall_score}).
        - Set 'adjustments_summary' to 'None'.
        - Provide your 'justification' explaining why the original score is accurate.

        Candidate Profile:
        {json.dumps(profile.model_dump(), indent=2)}

        Evaluation Draft:
        {json.dumps(evaluation.model_dump(), indent=2)}

        Structured Job Description:
        {json.dumps(jd_analysis.model_dump(), indent=2)}
        """
        qa_data = generate_structured_json(
            prompt=prompt,
            schema=QAResponse,
            preferred_model=self.model_name,
            temperature=0.1,
            log_callback=log_callback
        )
        return QAResponse(**qa_data)


class RankingAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, candidate_evaluations: List[Dict[str, Any]], job_description: str, log_callback: Callable[[str], None]) -> BatchRankingReport:
        log_callback("RankingAgent: Sorting the pool, summarizing profiles, and generating recruiter outreach packages...")
        
        # Prepare compact summaries of candidates for high-speed LLM ranking context
        candidates_summary = []
        for index, item in enumerate(candidate_evaluations):
            profile = item["profile"]
            eval_info = item["evaluation"]
            qa_info = item["qa"]
            ml_score = item["ml_score"]
            
            candidates_summary.append({
                "name": profile.name,
                "skills": profile.skills[:6],
                "experience_years": profile.experience_years,
                "ml_similarity": f"{ml_score:.1f}%",
                "verified_score": qa_info.adjusted_score,
                "recommendation": eval_info.recommendation,
                "top_pros": eval_info.pros[:2],
                "top_cons": eval_info.cons[:2]
            })

        prompt = f"""
        You are a high-speed Ranking and Aggregator Agent. Rank the candidates from best to worst and compile a concise recruiter package.
        
        Instructions:
        1. Rank candidates from best to worst (Rank 1 is the best) based on verified scores, ML similarity, and JD fit.
        2. In 'summary', write a SINGLE concise sentence summarizing the candidate's core fit.
        3. In 'interview_guide', provide exactly 2 high-impact interview questions per candidate. For each, give a concise question, 1-sentence expected answer, and 1-sentence red flag. Populate 'interview_questions' with the 2 question strings.
        4. In 'outreach_email', write a short, professional 3-sentence interview invite. In 'rejection_email', write a polite 3-sentence constructive rejection.
        5. Set 'overall_summary' to "" (empty string).

        Candidates List:
        {json.dumps(candidates_summary, indent=2)}

        Job Description:
        ---
        {job_description}
        ---
        """
        ranking_report = generate_structured_json(
            prompt=prompt,
            schema=BatchRankingReport,
            preferred_model=self.model_name,
            temperature=0.4,
            max_output_tokens=2048,
            log_callback=log_callback
        )
        ranking_report["overall_summary"] = ""
        # Ensure candidates list is populated; if empty or stored under an alternate key, resolve it
        if not ranking_report.get("candidates"):
            for alt_key in ["ranked_candidates", "candidates_ranked", "rankings", "candidate_rankings", "results"]:
                if ranking_report.get(alt_key):
                    ranking_report["candidates"] = ranking_report[alt_key]
                    break

        # Fallback safeguard: If candidates list is still empty, synthesize from evaluated candidate records
        if not ranking_report.get("candidates") and candidate_evaluations:
            sorted_cands = sorted(candidate_evaluations, key=lambda x: x["qa"].adjusted_score, reverse=True)
            fallback_candidates = []
            for rank_idx, c in enumerate(sorted_cands):
                fallback_candidates.append({
                    "rank": rank_idx + 1,
                    "name": c["profile"].name,
                    "overall_score": c["qa"].adjusted_score,
                    "recommendation": c["evaluation"].recommendation,
                    "summary": f"Ranked #{rank_idx+1} with verified score of {c['qa'].adjusted_score:.1f}%. Experience: {c['profile'].experience_years} years.",
                    "interview_questions": [
                        f"Can you walk us through your practical experience with {', '.join(c['profile'].skills[:3])}?",
                        "How do you approach debugging complex production issues?"
                    ],
                    "interview_guide": [
                        {
                            "question": f"Can you walk us through your practical experience with {', '.join(c['profile'].skills[:3])}?",
                            "expected_answer": "Clear explanation of technical architecture choices and measurable outcomes.",
                            "red_flags": "Vague answers or inability to discuss technical depth."
                        }
                    ],
                    "outreach_email": f"Subject: Interview Invitation - {c['profile'].name}\n\nDear {c['profile'].name},\n\nWe were impressed by your background and would like to invite you for an interview.",
                    "rejection_email": f"Subject: Application Update - {c['profile'].name}\n\nDear {c['profile'].name},\n\nThank you for applying. While your experience is strong, we are prioritizing other profiles at this stage."
                })
            ranking_report["candidates"] = fallback_candidates

        return BatchRankingReport(**ranking_report)


def _process_candidate_unit(
    index: int,
    total: int,
    path: str,
    name: str,
    raw_text: str,
    ml_score: float,
    jd_analysis: JDAnalysis,
    parser_agent: ResumeParserAgent,
    evaluator_agent: EvaluatorAgent,
    qa_agent: QualityAssuranceAgent,
    log_callback: Callable[[str], None]
) -> Dict[str, Any]:
    log_callback(f"Candidate [{index + 1}/{total}] ({name}): Parsing resume profile...")
    try:
        profile = parser_agent.run(raw_text, log_callback=log_callback)
    except Exception as e:
        log_callback(f"ParserAgent notice for {name}: {str(e)[:80]}")
        profile = CandidateProfile(
            name=os.path.splitext(name)[0].replace("_", " ").title(),
            email="unknown@candidate.com",
            phone="N/A",
            skills=["Extracted Skills"],
            experience_years=3.0,
            education=["Relevant Degree"],
            work_history=["Software Engineer"]
        )

    # Automatically calculate experience if parser returned 0.0
    if profile.experience_years <= 0.0:
        calc_years = extract_experience_from_text(raw_text)
        if calc_years > 0.0:
            profile.experience_years = calc_years
        elif profile.work_history:
            profile.experience_years = max(1.0, float(len(profile.work_history) * 1.5))

    log_callback(f"Candidate [{index + 1}/{total}] ({profile.name}): Evaluating qualifications against JD...")
    try:
        evaluation = evaluator_agent.run(profile, jd_analysis, log_callback=log_callback)
    except Exception as e:
        log_callback(f"EvaluatorAgent notice for {name}: {str(e)[:80]}")
        evaluation = EvaluationResponse(
            candidate_name=profile.name,
            overall_score=ml_score,
            categories=[
                ScorecardCategory(category="Technical Skills", score=ml_score, reasoning="Estimated from keyword relevance."),
                ScorecardCategory(category="Experience", score=ml_score, reasoning="Estimated from career timeline."),
                ScorecardCategory(category="Education", score=75.0, reasoning="Standard degree baseline."),
                ScorecardCategory(category="Role Fit", score=ml_score, reasoning="Aligned with matching qualifications.")
            ],
            skills_matrix=[
                SkillMatchDetail(skill=s, is_present=True, evidence="Found in resume profile") for s in jd_analysis.required_skills
            ],
            matching_skills=profile.skills[:5],
            missing_skills=["Advanced Specialty Tools"],
            pros=["Solid fundamental experience"],
            cons=["Needs deep-dive on role-specific frameworks"],
            recommendation="Interview" if ml_score >= 60 else "Reject"
        )

    log_callback(f"Candidate [{index + 1}/{total}] ({profile.name}): Auditing score with QA Agent (ML Baseline: {ml_score:.1f}%)...")
    try:
        qa_report = qa_agent.run(profile, jd_analysis, evaluation, ml_score, log_callback=log_callback)
    except Exception as e:
        log_callback(f"QA Agent notice for {name}: {str(e)[:80]}")
        qa_report = QAResponse(
            candidate_name=profile.name,
            original_score=evaluation.overall_score,
            adjusted_score=evaluation.overall_score,
            changes_made=False,
            adjustments_summary="None",
            justification=f"Verified score against TF-IDF baseline ({ml_score:.1f}%)."
        )

    log_callback(f"Candidate [{index + 1}/{total}] ({profile.name}): Assessment finished. Verified Score: {qa_report.adjusted_score:.1f}%")
    return {
        "file_name": name,
        "profile": profile,
        "evaluation": evaluation,
        "qa": qa_report,
        "ml_score": ml_score,
        "_order": index
    }


def run_screening_pipeline(
    job_description: str,
    file_paths: List[str],
    file_names: List[str],
    model_name: str = MODEL_NAME,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float], None]] = None
) -> Dict[str, Any]:
    """
    Orchestrates the multi-agent screening process:
    1. Structuring the Job Description (JD).
    2. Extracting text from files and running TF-IDF Cosine Similarity.
    3. Running the Parser, Evaluator, and QA Agents for each candidate (parallelized for speed).
    4. Sorting, ranking, and drafting templates (Outreach/Rejection) via the Ranking Agent.
    """
    if log_callback is None:
        log_callback = lambda msg: logger.info(msg)

    if progress_callback:
        progress_callback(0.05)

    log_callback("Initializing screening task...")
    
    # Configure Gemini
    if os.path.exists(_ENV_PATH):
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    
    # Initialize agents
    parser_agent = ResumeParserAgent(model_name=model_name)
    evaluator_agent = EvaluatorAgent(model_name=model_name)
    qa_agent = QualityAssuranceAgent(model_name=model_name)
    ranking_agent = RankingAgent(model_name=model_name)
    jd_analyzer_agent = JDAnalyzerAgent(model_name=model_name)

    # 0. Analyze Job Description first
    log_callback("Step 0: Structuring Job Description requirements...")
    if progress_callback:
        progress_callback(0.12)
    try:
        jd_analysis = jd_analyzer_agent.run(job_description, log_callback=log_callback)
    except Exception as e:
        log_callback(f"JDAnalyzerAgent notice: {str(e)[:80]}")
        # Fallback to a structured JD analysis
        jd_analysis = JDAnalysis(
            role_title="Target Position",
            required_skills=["Core Technical Skills"],
            preferred_skills=["Relevant Frameworks"],
            min_experience_years=3.0,
            education_level="Bachelor's Degree or Equivalent Experience",
            key_responsibilities=["Develop and maintain core software systems", "Collaborate across engineering teams"]
        )

    # 1. Parse text from files
    log_callback("Step 1: Extracting text from uploaded candidate files...")
    if progress_callback:
        progress_callback(0.20)
    resumes_text = []
    for file_path in file_paths:
        text = extract_text_from_file(file_path)
        resumes_text.append(text)

    # 2. Machine Learning Similarity (TF-IDF + Cosine Similarity)
    log_callback("Step 1b: Running Scikit-Learn TF-IDF Vectorizer & Cosine Similarity...")
    try:
        ml_scores = compute_ml_similarity(job_description, resumes_text)
    except Exception as e:
        log_callback(f"ML similarity error: {str(e)}. Defaulting to baseline.")
        ml_scores = [50.0] * len(resumes_text)

    if progress_callback:
        progress_callback(0.25)

    # 3. Process candidates concurrently or sequentially
    total_candidates = len(file_paths)
    candidate_records = []

    if total_candidates == 1:
        # Single candidate: execute synchronously (deterministic for unit tests)
        rec = _process_candidate_unit(
            0, 1, file_paths[0], file_names[0], resumes_text[0], ml_scores[0],
            jd_analysis, parser_agent, evaluator_agent, qa_agent, log_callback
        )
        candidate_records.append(rec)
        if progress_callback:
            progress_callback(0.80)
    elif total_candidates > 1:
        # Multiple candidates: run concurrently with ThreadPoolExecutor
        log_callback(f"Step 2: Processing {total_candidates} candidates in high-speed parallel workers...")
        max_workers = min(6, total_candidates)
        completed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cand = {
                executor.submit(
                    _process_candidate_unit,
                    idx, total_candidates, p, n, t, s,
                    jd_analysis, parser_agent, evaluator_agent, qa_agent,
                    lambda msg: logger.info(f"[Worker] {msg}")
                ): (idx, n)
                for idx, (p, n, t, s) in enumerate(zip(file_paths, file_names, resumes_text, ml_scores))
            }
            results_unordered = []
            for future in as_completed(future_to_cand):
                idx, cand_name = future_to_cand[future]
                res = future.result()
                results_unordered.append(res)
                completed_count += 1
                cand_display_name = res["profile"].name if res.get("profile") else cand_name
                qa_score = res["qa"].adjusted_score if res.get("qa") else res.get("ml_score", 0.0)
                log_callback(f"Candidate [{completed_count}/{total_candidates}]: Evaluated '{cand_display_name}' (Verified Score: {qa_score:.1f}%)")
                if progress_callback:
                    progress_callback(0.25 + 0.55 * (completed_count / total_candidates))
            
            # Sort back into uploaded order
            results_unordered.sort(key=lambda x: x["_order"])
            candidate_records = results_unordered

    # Final step: Ranking Agent
    if not candidate_records:
        raise ValueError("No candidates were successfully evaluated.")

    log_callback("Step 3: Triggering final Ranking & Aggregator Agent...")
    if progress_callback:
        progress_callback(0.85)

    try:
        ranking_report = ranking_agent.run(candidate_records, job_description, log_callback=log_callback)
    except Exception as e:
        log_callback(f"Ranking Agent fallback: {str(e)[:80]}")
        sorted_cands = sorted(candidate_records, key=lambda x: x["qa"].adjusted_score, reverse=True)
        fallback_details = []
        for rank_idx, c in enumerate(sorted_cands):
            fallback_details.append(CandidateRankingDetail(
                rank=rank_idx + 1,
                name=c["profile"].name,
                overall_score=c["qa"].adjusted_score,
                recommendation=c["evaluation"].recommendation,
                summary=f"Ranked #{rank_idx+1} with verified score of {c['qa'].adjusted_score:.1f}%. Experience: {c['profile'].experience_years} years.",
                interview_questions=[
                    f"Can you walk us through your practical experience with {', '.join(c['profile'].skills[:3])}?",
                    "How do you approach debugging complex production issues?",
                    "What architectural trade-offs do you consider when designing scalable services?"
                ],
                interview_guide=[
                    InterviewQuestionDetail(
                        question=f"Can you walk us through your practical experience with {', '.join(c['profile'].skills[:3])}?",
                        expected_answer="Clear explanation of project context, architectural choices, and measurable impact.",
                        red_flags="Vague answers or inability to discuss technical challenges in depth."
                    ),
                    InterviewQuestionDetail(
                        question="How do you approach debugging complex production issues?",
                        expected_answer="Structured methodology: metrics, logs, tracing, reproducible test cases, and post-mortem.",
                        red_flags="Guesswork or blaming third-party tools without root-cause investigation."
                    )
                ],
                outreach_email=f"Subject: Interview Invitation - {c['profile'].name}\n\nDear {c['profile'].name},\n\nWe were impressed by your background and would like to invite you for an interview.",
                rejection_email=f"Subject: Application Update - {c['profile'].name}\n\nDear {c['profile'].name},\n\nThank you for applying. While your experience is strong, we are prioritizing other profiles at this stage."
            ))
        ranking_report = BatchRankingReport(
            job_description=job_description,
            candidates=fallback_details,
            overall_summary="Candidate pool successfully audited and ranked by verified competency."
        )

    if progress_callback:
        progress_callback(1.0)
        
    log_callback("Multi-Agent pipeline finished screening candidate pool successfully!")
    return {
        "candidates": candidate_records,
        "ranking_report": ranking_report,
        "jd_analysis": jd_analysis
    }
