import os
import tempfile
import pytest
import json
from unittest.mock import MagicMock, patch
from pipeline import (
    parse_txt,
    extract_text_from_file,
    compute_ml_similarity,
    SubscriptableModel,
    CandidateProfile,
    JDAnalysis,
    EvaluationResponse,
    QAResponse,
    BatchRankingReport,
    run_screening_pipeline
)

# -------------------------------------------------------------
# Test Part 1: Text Parsers
# -------------------------------------------------------------

def test_parse_txt():
    # Create a temporary text file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as temp:
        temp.write("Hello world, this is a resume.")
        temp_path = temp.name

    try:
        parsed_text = parse_txt(temp_path)
        assert "Hello world" in parsed_text
    finally:
        os.remove(temp_path)

def test_extract_text_from_file():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as temp:
        temp.write("Resume content for testing.")
        temp_path = temp.name

    try:
        parsed_text = extract_text_from_file(temp_path)
        assert "Resume content" in parsed_text
    finally:
        os.remove(temp_path)

# -------------------------------------------------------------
# Test Part 2: ML Similarity Engine
# -------------------------------------------------------------

def test_compute_ml_similarity():
    jd = "Python software engineer with experience in FastAPI and React."
    resumes = [
        "Python engineer specializing in FastAPI backend services.",
        "Experienced React developer building beautiful frontends.",
        "Completely unrelated background, sales representative."
    ]
    scores = compute_ml_similarity(jd, resumes)
    assert len(scores) == 3
    assert all(isinstance(score, float) for score in scores)
    assert all(0.0 <= score <= 100.0 for score in scores)
    # The first resume shares more keywords with the JD than the sales resume
    assert scores[0] > scores[2]

def test_compute_ml_similarity_empty():
    assert compute_ml_similarity("JD", []) == []

# -------------------------------------------------------------
# Test Part 3: Pydantic v2 Subscriptable Schemas
# -------------------------------------------------------------

def test_subscriptable_model():
    profile = CandidateProfile(
        name="John Doe",
        email="john@example.com",
        phone="123-456-7890",
        skills=["Python", "SQL"],
        experience_years=5.5,
        education=["BS CS"],
        work_history=["Software Engineer at Acme"]
    )
    
    # Verify dictionary-like subscripting works (from SubscriptableModel base)
    assert profile["name"] == "John Doe"
    assert profile["skills"] == ["Python", "SQL"]
    assert profile["experience_years"] == 5.5
    
    # Verify get method works
    assert profile.get("email") == "john@example.com"
    assert profile.get("non_existent", "default_val") == "default_val"

# -------------------------------------------------------------
# Test Part 4: Mocked Pipeline Orchestrator Run
# -------------------------------------------------------------

@patch("pipeline.get_model")
def test_run_screening_pipeline_mocked(mock_get_model):
    # Setup mock return values for Gemini Model generation content
    mock_model = MagicMock()
    mock_get_model.return_value = mock_model

    # 1. Mock response for JDAnalyzerAgent
    jd_mock_response = MagicMock()
    jd_mock_response.text = json.dumps({
        "role_title": "Python Developer",
        "required_skills": ["Python", "Git"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 2.0,
        "education_level": "Bachelor's Degree",
        "key_responsibilities": ["Write clean code"]
    })

    # 2. Mock response for ResumeParserAgent
    parser_mock_response = MagicMock()
    parser_mock_response.text = json.dumps({
        "name": "Alice Green",
        "email": "alice@example.com",
        "phone": "555-1234",
        "skills": ["Python", "Git", "Docker"],
        "experience_years": 3.0,
        "education": ["BS CS"],
        "work_history": ["Dev at Google"]
    })

    # 3. Mock response for EvaluatorAgent
    evaluator_mock_response = MagicMock()
    evaluator_mock_response.text = json.dumps({
        "candidate_name": "Alice Green",
        "overall_score": 85.0,
        "categories": [
            {"category": "Technical Skills", "score": 90.0, "reasoning": "Strong python skills"},
            {"category": "Experience", "score": 80.0, "reasoning": "Meets experience requirements"},
            {"category": "Education", "score": 100.0, "reasoning": "Has BS CS degree"},
            {"category": "Role Fit", "score": 85.0, "reasoning": "Excellent fit"}
        ],
        "skills_matrix": [
            {"skill": "Python", "is_present": True, "evidence": "Used for 3 years"},
            {"skill": "Git", "is_present": True, "evidence": "Listed in skills"}
        ],
        "matching_skills": ["Python", "Git"],
        "missing_skills": [],
        "pros": ["Strong backend experience"],
        "cons": ["No front-end mentioned"],
        "recommendation": "Shortlist"
    })

    # 4. Mock response for QualityAssuranceAgent
    qa_mock_response = MagicMock()
    qa_mock_response.text = json.dumps({
        "candidate_name": "Alice Green",
        "original_score": 85.0,
        "adjusted_score": 85.0,
        "changes_made": False,
        "adjustments_summary": "None",
        "justification": "Evaluation is accurate"
    })

    # 5. Mock response for RankingAgent
    ranking_mock_response = MagicMock()
    ranking_mock_response.text = json.dumps({
        "job_description": "We need a Python developer.",
        "candidates": [
            {
                "rank": 1,
                "name": "Alice Green",
                "overall_score": 85.0,
                "recommendation": "Shortlist",
                "summary": "Excellent fit with 3 years of Python.",
                "interview_questions": ["Tell me about your Python project"],
                "interview_guide": [
                    {
                        "question": "Tell me about your Python project",
                        "expected_answer": "Demonstrated async experience",
                        "red_flags": "Unclear technical architecture contributions"
                    }
                ],
                "outreach_email": "Hi Alice, let's schedule an interview.",
                "rejection_email": "Dear Alice, we went with someone else."
            }
        ],
        "overall_summary": "Good pool of candidates."
    })

    # Generative model's generate_content calls are sequentially executed:
    # 1. JD analysis, 2. Parsing candidate, 3. Evaluation, 4. QA, 5. Ranking
    mock_model.generate_content.side_effect = [
        jd_mock_response,
        parser_mock_response,
        evaluator_mock_response,
        qa_mock_response,
        ranking_mock_response
    ]

    # Create dummy files to parse
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as resume_temp:
        resume_temp.write("Candidate Alice Green resume content.")
        resume_path = resume_temp.name

    try:
        results = run_screening_pipeline(
            job_description="We need a Python developer.",
            file_paths=[resume_path],
            file_names=["alice_green_resume.txt"],
            model_name="gemini-3.5-flash",
            log_callback=lambda x: None
        )
        
        # Verify results structure
        assert "candidates" in results
        assert "ranking_report" in results
        assert "jd_analysis" in results
        
        # Verify specific contents
        assert results["jd_analysis"].role_title == "Python Developer"
        assert len(results["candidates"]) == 1
        assert results["candidates"][0]["file_name"] == "alice_green_resume.txt"
        assert results["candidates"][0]["profile"].name == "Alice Green"
        assert results["ranking_report"].candidates[0].name == "Alice Green"
        assert results["ranking_report"].candidates[0].rank == 1
    finally:
        os.remove(resume_path)
