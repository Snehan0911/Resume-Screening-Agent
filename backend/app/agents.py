import os
import json
import logging
from typing import List, Callable, Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

from app.schemas import (
    CandidateProfile,
    EvaluationResponse,
    QAResponse,
    BatchRankingReport,
    CandidateRankingDetail
)

# Load env vars
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Google GenAI
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    logger.warning("GEMINI_API_KEY environment variable not set. Gemini API calls will fail.")

# Default model
MODEL_NAME = "gemini-3.5-flash"

def get_model(model_name: str = MODEL_NAME) -> genai.GenerativeModel:
    return genai.GenerativeModel(model_name)

class ResumeParserAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, raw_text: str, log_callback: Callable[[str], None] = None) -> CandidateProfile:
        if log_callback:
            log_callback("ResumeParserAgent: Parsing raw resume text into structured fields...")
        else:
            logger.info("ResumeParserAgent: Parsing raw resume...")

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
        {raw_text}
        ---
        """
        
        model = get_model(self.model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=CandidateProfile,
                temperature=0.1
            )
        )
        
        try:
            parsed_data = json.loads(response.text)
            return CandidateProfile(**parsed_data)
        except Exception as e:
            logger.error(f"Failed to parse resume JSON: {response.text}. Error: {str(e)}")
            raise e


class EvaluatorAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, profile: CandidateProfile, job_description: str, log_callback: Callable[[str], None] = None) -> EvaluationResponse:
        if log_callback:
            log_callback(f"EvaluatorAgent: Evaluating {profile.name} against the Job Description...")
        else:
            logger.info(f"EvaluatorAgent: Evaluating candidate {profile.name}...")

        prompt = f"""
        You are a Candidate Review Agent. Compare the candidate's parsed resume profile against the Job Description.
        Grade the candidate carefully across the following categories:
        1. Technical Skills: Do they have the required programming languages, frameworks, and technical skills?
        2. Experience: Is their experience level aligned with what's requested? Look at roles and responsibilities.
        3. Education: Does their education or certifications match the requirements?
        4. Role Fit: How well do their past roles prepare them for this specific position?

        For each category, provide:
        - A score between 0 and 100
        - Clear, objective reasoning for that score

        Calculate the overall score as a weighted average or general score (0 to 100) reflecting their match level.
        Identify:
        - Matching skills: List of skills the candidate has that are mentioned or highly relevant to the JD.
        - Missing skills: Crucial requirements in the JD that are not shown in the candidate's profile.
        - Pros: Highlights, strong achievements, or bonuses.
        - Cons: Red flags, gaps, lack of relevant context.
        - Recommendation: Classify as either 'Shortlist' (excellent fit), 'Interview' (good/borderline fit), or 'Reject' (poor fit).

        Candidate Profile:
        {json.dumps(profile.dict(), indent=2)}

        Job Description:
        ---
        {job_description}
        ---
        """

        model = get_model(self.model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=EvaluationResponse,
                temperature=0.2
            )
        )

        try:
            eval_data = json.loads(response.text)
            return EvaluationResponse(**eval_data)
        except Exception as e:
            logger.error(f"Failed to parse evaluation JSON: {response.text}. Error: {str(e)}")
            raise e


class QualityAssuranceAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, profile: CandidateProfile, job_description: str, evaluation: EvaluationResponse, log_callback: Callable[[str], None] = None) -> QAResponse:
        if log_callback:
            log_callback(f"QualityAssuranceAgent: Reviewing and double-checking scores for {profile.name}...")
        else:
            logger.info(f"QualityAssuranceAgent: Checking candidate {profile.name}...")

        prompt = f"""
        You are a Quality Assurance (QA) Agent. Your job is to critically verify the evaluation of candidate {profile.name} against their profile and the Job Description.
        Inspect the assessment for:
        1. Over-optimism or over-pessimism: Are the scores justified by actual experience listed in work history?
        2. Hallucinations: Did the evaluator list a matching skill that the candidate doesn't actually possess?
        3. Work history alignment: If the candidate has 2 years of experience, but the evaluator gave a high score under 'Experience' requiring 8 years, adjust the score down.
        4. Consistency: Apply a rigorous and fair grading standard.

        If you find discrepancies:
        - Set 'changes_made' to true.
        - Provide an 'adjusted_score' (higher or lower) and describe the 'adjustments_summary'.
        - Provide a comprehensive 'justification'.

        If you agree with the original evaluation:
        - Set 'changes_made' to false.
        - Set 'adjusted_score' to the same as the original overall score ({evaluation.overall_score}).
        - Set 'adjustments_summary' to 'None'.
        - Provide your 'justification' explaining why the original score is accurate.

        Candidate Profile:
        {json.dumps(profile.dict(), indent=2)}

        Evaluation Draft:
        {json.dumps(evaluation.dict(), indent=2)}

        Job Description:
        ---
        {job_description}
        ---
        """

        model = get_model(self.model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=QAResponse,
                temperature=0.1
            )
        )

        try:
            qa_data = json.loads(response.text)
            return QAResponse(**qa_data)
        except Exception as e:
            logger.error(f"Failed to parse QA JSON: {response.text}. Error: {str(e)}")
            raise e


class RankingAgent:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name

    def run(self, candidate_evaluations: List[Dict[str, Any]], job_description: str, log_callback: Callable[[str], None] = None) -> BatchRankingReport:
        if log_callback:
            log_callback("RankingAgent: Compiling candidates list, ranking them, and generating customized interview questions...")
        else:
            logger.info("RankingAgent: Sorting and ranking candidate batch...")

        # Prepare a lightweight text summary of each candidate's evaluations for the LLM context
        candidates_summary = []
        for index, item in enumerate(candidate_evaluations):
            profile = item["profile"]
            eval_info = item["evaluation"]
            qa_info = item["qa"]
            
            candidates_summary.append({
                "name": profile.name,
                "skills": profile.skills,
                "experience_years": profile.experience_years,
                "original_score": eval_info.overall_score,
                "qa_adjusted_score": qa_info.adjusted_score,
                "original_recommendation": eval_info.recommendation,
                "qa_changes_made": qa_info.changes_made,
                "qa_justification": qa_info.justification,
                "pros": eval_info.pros,
                "cons": eval_info.cons,
                "missing_skills": eval_info.missing_skills
            })

        prompt = f"""
        You are a Ranking and Aggregator Agent. You are given a list of candidate profiles along with their initial evaluations and QA reviews.
        Your task is:
        1. Rank the candidates from best to worst based on their QA adjusted scores and overall alignment with the Job Description.
        2. Create a brief summary (2-3 sentences) of each candidate's fit.
        3. Draft 3-4 custom, tailored interview questions for each candidate:
           - Tailor questions to probe specific gaps, missing skills, or inconsistencies in their work history.
           - Ask technical questions verifying their expertise in fields where they claim high skills but have short tenures.
        4. Write an overall summary of the batch (evaluating the talent pool strength, average fit, and recommendations for the hiring team).

        Candidates List:
        {json.dumps(candidates_summary, indent=2)}

        Job Description:
        ---
        {job_description}
        ---
        """

        model = get_model(self.model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=BatchRankingReport,
                temperature=0.2
            )
        )

        try:
            ranking_report = json.loads(response.text)
            return BatchRankingReport(**ranking_report)
        except Exception as e:
            logger.error(f"Failed to parse ranking JSON: {response.text}. Error: {str(e)}")
            raise e
