from pydantic import BaseModel, Field
from typing import List, Optional

class CandidateProfile(BaseModel):
    name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address of the candidate")
    phone: str = Field(description="Phone number of the candidate")
    skills: List[str] = Field(description="List of key technical and soft skills extracted")
    experience_years: float = Field(description="Total years of relevant experience extracted")
    education: List[str] = Field(description="List of degrees and certifications")
    work_history: List[str] = Field(description="List of companies, roles, and dates")

class ScorecardCategory(BaseModel):
    category: str = Field(description="e.g., Technical Skills, Experience, Education, Role Fit")
    score: float = Field(description="Score from 0 to 100")
    reasoning: str = Field(description="Detailed reasoning for this category's score")

class EvaluationResponse(BaseModel):
    candidate_name: str = Field(description="Name of the candidate")
    overall_score: float = Field(description="Aggregated score from 0 to 100")
    categories: List[ScorecardCategory] = Field(description="Breakdown of scores by category")
    matching_skills: List[str] = Field(description="Skills that match the Job Description")
    missing_skills: List[str] = Field(description="Required or preferred skills that are missing")
    pros: List[str] = Field(description="Key strengths and advantages of this candidate")
    cons: List[str] = Field(description="Concerns, red flags, or areas of development")
    recommendation: str = Field(description="Recommendation: 'Shortlist', 'Interview', or 'Reject'")

class QAResponse(BaseModel):
    candidate_name: str = Field(description="Name of the candidate")
    original_score: float = Field(description="Original overall score from Evaluator Agent")
    adjusted_score: float = Field(description="Adjusted overall score (or same if no change needed)")
    changes_made: bool = Field(description="True if scores or comments were adjusted")
    adjustments_summary: str = Field(description="Summary of adjustments made or 'None'")
    justification: str = Field(description="Reasoning behind QA decisions and verification check results")

class CandidateRankingDetail(BaseModel):
    rank: int = Field(description="Rank position (1 being the best)")
    name: str = Field(description="Candidate name")
    overall_score: float = Field(description="Verified overall score")
    recommendation: str = Field(description="Final recommendation")
    summary: str = Field(description="Brief summary of the candidate's fit")
    interview_questions: List[str] = Field(description="3-4 tailored technical or behavioral interview questions")

class BatchRankingReport(BaseModel):
    job_description: str = Field(description="The job description used for screening")
    candidates: List[CandidateRankingDetail] = Field(description="List of candidates sorted by rank")
    overall_summary: str = Field(description="Overview of the batch (talent pool distribution, general observations)")
