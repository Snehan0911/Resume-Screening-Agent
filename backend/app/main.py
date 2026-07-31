import os
import uuid
import shutil
import threading
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.parser import extract_text_from_file
from app.agents import (
    ResumeParserAgent,
    EvaluatorAgent,
    QualityAssuranceAgent,
    RankingAgent
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Resume Screening API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database to store screening tasks and results
# In a production app, this would be SQLite or PostgreSQL
TASKS_DB: Dict[str, Dict[str, Any]] = {}
DB_LOCK = threading.Lock()

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    completed_count: int
    total_count: int
    logs: List[str]

def run_screening_pipeline(task_id: str, file_paths: List[str], file_names: List[str], job_description: str):
    """Background runner for the multi-agent screening process."""
    def add_log(message: str):
        with DB_LOCK:
            TASKS_DB[task_id]["logs"].append(message)
        logger.info(f"[Task {task_id}] {message}")

    try:
        total_files = len(file_paths)
        add_log(f"Starting pipeline for {total_files} resumes...")
        
        parser_agent = ResumeParserAgent()
        evaluator_agent = EvaluatorAgent()
        qa_agent = QualityAssuranceAgent()
        ranking_agent = RankingAgent()

        candidate_records = []

        for index, (file_path, file_name) in enumerate(zip(file_paths, file_names)):
            add_log(f"Processing file {index+1}/{total_files}: {file_name}")
            
            # Step 1: Parse resume file text
            add_log(f"[{file_name}] Extracting text from document...")
            raw_text = extract_text_from_file(file_path)
            if not raw_text.strip() or raw_text.startswith("Error"):
                add_log(f"[{file_name}] Error extracting text: {raw_text[:100]}...")
                with DB_LOCK:
                    TASKS_DB[task_id]["completed_count"] += 1
                    TASKS_DB[task_id]["progress"] = (index + 1) / (total_files + 1)
                continue

            # Step 2: Run Parser Agent
            try:
                profile = parser_agent.run(raw_text, log_callback=lambda msg: add_log(f"[{file_name}] {msg}"))
            except Exception as e:
                add_log(f"[{file_name}] Parser Agent failed: {str(e)}")
                with DB_LOCK:
                    TASKS_DB[task_id]["completed_count"] += 1
                    TASKS_DB[task_id]["progress"] = (index + 1) / (total_files + 1)
                continue

            # Step 3: Run Evaluator Agent
            try:
                evaluation = evaluator_agent.run(profile, job_description, log_callback=lambda msg: add_log(f"[{file_name}] {msg}"))
            except Exception as e:
                add_log(f"[{file_name}] Evaluator Agent failed: {str(e)}")
                with DB_LOCK:
                    TASKS_DB[task_id]["completed_count"] += 1
                    TASKS_DB[task_id]["progress"] = (index + 1) / (total_files + 1)
                continue

            # Step 4: Run QA Agent
            try:
                qa_report = qa_agent.run(profile, job_description, evaluation, log_callback=lambda msg: add_log(f"[{file_name}] {msg}"))
            except Exception as e:
                add_log(f"[{file_name}] QA Agent failed: {str(e)}")
                # Use evaluation score as fallback adjusted score if QA fails
                from app.schemas import QAResponse
                qa_report = QAResponse(
                    candidate_name=profile.name,
                    original_score=evaluation.overall_score,
                    adjusted_score=evaluation.overall_score,
                    changes_made=False,
                    adjustments_summary="None (QA agent failed, fell back to evaluator)",
                    justification=f"Fallback due to QA Agent exception: {str(e)}"
                )

            # Store the single candidate pipeline logs and outputs
            candidate_records.append({
                "file_name": file_name,
                "profile": profile,
                "evaluation": evaluation,
                "qa": qa_report
            })

            with DB_LOCK:
                TASKS_DB[task_id]["completed_count"] += 1
                TASKS_DB[task_id]["progress"] = (index + 1) / (total_files + 1)
                # Store partial results so UI can see them
                TASKS_DB[task_id]["candidates"] = [
                    {
                        "file_name": c["file_name"],
                        "name": c["profile"].name,
                        "email": c["profile"].email,
                        "phone": c["profile"].phone,
                        "skills": c["profile"].skills,
                        "experience_years": c["profile"].experience_years,
                        "education": c["profile"].education,
                        "work_history": c["profile"].work_history,
                        "evaluation": c["evaluation"].dict(),
                        "qa": c["qa"].dict()
                    }
                    for c in candidate_records
                ]

        # Step 5: Run Ranking & Summary Agent over all successfully parsed candidates
        if len(candidate_records) > 0:
            add_log("All resumes parsed and reviewed. Running final Ranking and Aggregator Agent...")
            try:
                ranking_report = ranking_agent.run(candidate_records, job_description, log_callback=add_log)
                
                with DB_LOCK:
                    TASKS_DB[task_id]["ranking_report"] = ranking_report.dict()
                    TASKS_DB[task_id]["status"] = "completed"
                    TASKS_DB[task_id]["progress"] = 1.0
                add_log("Screening process completed successfully!")
            except Exception as e:
                add_log(f"Final Ranking Agent failed: {str(e)}")
                # Fallback ranking if LLM fails
                sorted_candidates = sorted(candidate_records, key=lambda x: x["qa"].adjusted_score, reverse=True)
                fallback_candidates = []
                for idx, c in enumerate(sorted_candidates):
                    fallback_candidates.append({
                        "rank": idx + 1,
                        "name": c["profile"].name,
                        "overall_score": c["qa"].adjusted_score,
                        "recommendation": c["evaluation"].recommendation,
                        "summary": f"Ranked #{idx+1} based on score of {c['qa'].adjusted_score}. Experience: {c['profile'].experience_years} years.",
                        "interview_questions": [
                            f"Can you explain your experience with {', '.join(c['profile'].skills[:3])}?",
                            "What is your approach to learning new technical stacks?",
                            "Tell me about a challenging project you successfully delivered."
                        ]
                    })
                
                fallback_report = {
                    "job_description": job_description,
                    "candidates": fallback_candidates,
                    "overall_summary": "Batch compiled with fallback ranking due to ranking agent exception."
                }
                with DB_LOCK:
                    TASKS_DB[task_id]["ranking_report"] = fallback_report
                    TASKS_DB[task_id]["status"] = "completed"
                    TASKS_DB[task_id]["progress"] = 1.0
                add_log("Screening process completed with fallback ranking.")
        else:
            with DB_LOCK:
                TASKS_DB[task_id]["status"] = "failed"
                TASKS_DB[task_id]["progress"] = 1.0
            add_log("Screening failed: No resumes were successfully processed.")

    except Exception as e:
        add_log(f"Fatal error in background pipeline: {str(e)}")
        with DB_LOCK:
            TASKS_DB[task_id]["status"] = "failed"
            TASKS_DB[task_id]["progress"] = 1.0
    finally:
        # Clean up temporary files
        for path in file_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

@app.post("/api/analyze")
async def analyze_resumes(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    job_description: str = Form(...)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")

    task_id = str(uuid.uuid4())
    temp_dir = os.path.join(os.getcwd(), "temp_uploads", task_id)
    os.makedirs(temp_dir, exist_ok=True)

    file_paths = []
    file_names = []

    for file in files:
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_paths.append(file_path)
        file_names.append(file.filename)

    # Initialize task status
    with DB_LOCK:
        TASKS_DB[task_id] = {
            "status": "processing",
            "progress": 0.0,
            "completed_count": 0,
            "total_count": len(files),
            "logs": ["Task initialized. Received files: " + ", ".join(file_names)],
            "candidates": [],
            "ranking_report": None
        }

    # Start screening pipeline in the background
    background_tasks.add_task(
        run_screening_pipeline,
        task_id=task_id,
        file_paths=file_paths,
        file_names=file_names,
        job_description=job_description
    )

    return {"task_id": task_id, "status": "processing"}

@app.get("/api/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    with DB_LOCK:
        if task_id not in TASKS_DB:
            raise HTTPException(status_code=404, detail="Task not found")
        task = TASKS_DB[task_id]
        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "completed_count": task["completed_count"],
            "total_count": task["total_count"],
            "logs": task["logs"]
        }

@app.get("/api/results/{task_id}")
async def get_task_results(task_id: str):
    with DB_LOCK:
        if task_id not in TASKS_DB:
            raise HTTPException(status_code=404, detail="Task not found")
        task = TASKS_DB[task_id]
        if task["status"] == "processing":
            raise HTTPException(status_code=400, detail="Task is still processing")
        return {
            "task_id": task_id,
            "status": task["status"],
            "candidates": task["candidates"],
            "ranking_report": task["ranking_report"]
        }

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "api_configured": os.getenv("GEMINI_API_KEY") is not None}
