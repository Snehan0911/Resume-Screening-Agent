import os
import sys
import argparse
import json
import time
import pandas as pd
from dotenv import load_dotenv
from pipeline import run_screening_pipeline

class PipelineEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return super().default(obj)

def main():
    parser = argparse.ArgumentParser(
        description="Resume Screening Agent: Command Line Interface for Multi-Agent Resume Screening System."
    )
    parser.add_argument(
        "--jd",
        required=True,
        help="Path to the target Job Description text file."
    )
    parser.add_argument(
        "--resumes",
        required=True,
        help="Path to the directory containing candidate resumes (PDF, DOCX, TXT)."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path where the screened output should be saved."
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "md", "markdown"],
        default="json",
        help="Output file format: json, csv, or md (default: json)."
    )
    parser.add_argument(
        "--model",
        default="gemini-3.5-flash",
        help="Gemini Core model to use (default: gemini-3.5-flash)."
    )

    args = parser.parse_args()

    # Load environment configuration
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY or GOOGLE_API_KEY must be set in environment or .env file.")
        sys.exit(1)

    # Validate JD path
    if not os.path.exists(args.jd):
        print(f"Error: Job description file not found at {args.jd}")
        sys.exit(1)

    with open(args.jd, "r", encoding="utf-8", errors="ignore") as f:
        job_description = f.read()

    # Validate resumes path
    if not os.path.isdir(args.resumes):
        print(f"Error: Resumes directory not found at {args.resumes}")
        sys.exit(1)

    # Gather resumes
    resume_files = []
    for entry in os.scandir(args.resumes):
        if entry.is_file() and entry.name.lower().endswith(('.pdf', '.docx', '.txt', '.md')):
            resume_files.append(entry.path)

    if not resume_files:
        print(f"Error: No valid resume files (.pdf, .docx, .txt, .md) found in {args.resumes}")
        sys.exit(1)

    print(f"Loaded {len(resume_files)} resumes from {args.resumes} for screening.")

    # Execute pipeline
    def log_callback(msg: str):
        print(f"[Agent Logs] {msg}")

    try:
        results = run_screening_pipeline(
            job_description=job_description,
            file_paths=resume_files,
            file_names=[os.path.basename(p) for p in resume_files],
            model_name=args.model,
            log_callback=log_callback
        )
    except Exception as e:
        print(f"Pipeline execution failed: {str(e)}")
        sys.exit(1)

    # Format and save output
    print(f"\nProcessing completed successfully. Writing results to {args.output} in {args.format} format...")
    
    candidates_list = results["candidates"]
    report = results["ranking_report"]
    jd_analysis = results["jd_analysis"]

    if args.format == "json":
        # Save full structured json
        with open(args.output, "w", encoding="utf-8") as out:
            json.dump(results, out, cls=PipelineEncoder, indent=2)
            
    elif args.format == "csv":
        # Compile clean leaderboard CSV
        csv_data_list = []
        for c in report["candidates"]:
            matching_full = next((x for x in candidates_list if x["profile"].name.strip().lower() == c["name"].strip().lower()), None)
            ml_score_val = f"{matching_full['ml_score']:.1f}%" if matching_full else "N/A"
            exp_val = matching_full["profile"].experience_years if matching_full else "N/A"
            edu_val = ", ".join(matching_full["profile"].education) if matching_full else "N/A"
            skills_val = ", ".join(matching_full["profile"].skills[:5]) if matching_full else "N/A"
            
            csv_data_list.append({
                "Rank": c["rank"],
                "Name": c["name"],
                "File Name": matching_full["file_name"] if matching_full else "N/A",
                "Final Score (%)": f"{c['overall_score']:.1f}",
                "ML Match Score (%)": ml_score_val,
                "Recommendation": c["recommendation"],
                "Experience (Years)": exp_val,
                "Education": edu_val,
                "Top Skills": skills_val,
                "Verdict Summary": c["summary"]
            })
        csv_df = pd.DataFrame(csv_data_list)
        csv_df.to_csv(args.output, index=False)

    elif args.format in ["md", "markdown"]:
        # Compile Recruiter Batch Report in Markdown
        report_md = f"# Resume Screening Agent - Recruiter Batch Report\n"
        report_md += f"Role Title: {jd_analysis.role_title if jd_analysis else 'Target Position'}\n\n"
        report_md += f"## 💡 Batch Overview Findings\n{report['overall_summary']}\n\n"
        report_md += "---\n\n## 📊 Candidate Leaderboard\n"
        
        for c in report["candidates"]:
            matching_full = next((x for x in candidates_list if x["profile"].name.strip().lower() == c["name"].strip().lower()), None)
            ml_score_text = f"{matching_full['ml_score']:.1f}%" if matching_full else "N/A"
            report_md += f"- **Rank #{c['rank']}**: {c['name']} | Final Audited Score: {c['overall_score']:.1f}% | ML Match: {ml_score_text} | Verdict: {c['recommendation']}\n"
            
        report_md += "\n---\n\n## 🔍 Candidate Detailed Assessments & Guides\n"
        for c in report["candidates"]:
            matching_full = next((x for x in candidates_list if x["profile"].name.strip().lower() == c["name"].strip().lower()), None)
            report_md += f"\n### Candidate: {c['name']} (Rank #{c['rank']})\n"
            report_md += f"- **Final Score**: {c['overall_score']:.1f}%\n"
            report_md += f"- **Recommendation**: {c['recommendation']}\n"
            report_md += f"- **Fit Verdict**: {c['summary']}\n\n"
            
            # Interview Guide
            report_md += "#### ❓ Interview Guide\n"
            guide = c.get("interview_guide")
            if guide:
                for idx, q_detail in enumerate(guide):
                    report_md += f"{idx+1}. **Question**: {q_detail['question']}\n"
                    report_md += f"   - *Expected Answer*: {q_detail['expected_answer']}\n"
                    report_md += f"   - *Red Flags*: {q_detail['red_flags']}\n"
            else:
                flat_qs = c.get("interview_questions", [])
                for idx, q in enumerate(flat_qs):
                    report_md += f"{idx+1}. **Question**: {q}\n"
                    
            # Emails
            outreach = c.get("outreach_email", "")
            rejection = c.get("rejection_email", "")
            report_md += f"\n#### ✉️ Outreach Email\n```text\n{outreach}\n```\n"
            report_md += f"\n#### ✉️ Rejection Feedback Email\n```text\n{rejection}\n```\n"
            report_md += "\n---\n"

        with open(args.output, "w", encoding="utf-8") as out:
            out.write(report_md)

    print("File saved successfully.")

if __name__ == "__main__":
    main()
