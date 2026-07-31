import os
import shutil
import tempfile
import time
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables dynamically at startup
load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Import parsing, ML, and agent pipeline
from pipeline import run_screening_pipeline


# Set page configuration
st.set_page_config(
    page_title="Resume Screening Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium dark-mode styling
st.markdown(
    """
    <style>
    /* Main background */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    /* Headers display font */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* Glassmorphic panels */
    div.css-1r6g72y, div.stForm, .glass-panel {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    
    /* Terminal Console */
    .terminal-console {
        background-color: #020617 !important;
        border: 1px solid #1e293b !important;
        border-radius: 12px !important;
        font-family: 'Courier New', Courier, monospace !important;
        color: #38bdf8 !important;
        padding: 1rem !important;
        font-size: 0.85rem !important;
        line-height: 1.4 !important;
        max-height: 300px !important;
        overflow-y: auto !important;
    }
    
    /* Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #8b5cf6 !important;
    }
    
    /* Glow effect for sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Session State
if "screening_results" not in st.session_state:
    st.session_state.screening_results = None
if "logs" not in st.session_state:
    st.session_state.logs = []

# Sidebar Configuration
with st.sidebar:
    st.image("assets/banner.png", use_container_width=True)
    st.markdown("### ⚙️ Pipeline Settings")
    
    model_choice = st.selectbox(
        "Gemini Core Model",
        options=["gemini-3.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"],
        index=0,
        help="Select the AI brain models for the collaborative agents."
    )
    
    st.markdown("---")
    st.markdown("### 🤖 Pipeline Agents")
    st.markdown("1. 🔍 **Parser Agent**")
    st.markdown("2. ⚖️ **Review Agent**")
    st.markdown("3. 🛡️ **QA Agent**")
    st.markdown("4. 👑 **Ranking Agent**")
    
    st.markdown("---")
    st.markdown("### 📂 Testing Resumes")
    st.markdown("Mock resume profiles are stored in: `sample_resumes/` folder in your workspace.")

# Header Title Block
st.markdown("<h1 style='text-align: center; background: linear-gradient(135deg, #fff 0%, #a5b4fc 50%, #818cf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>🚀 Resume Screening Agent</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>Unified Python Platform: Machine Learning (TF-IDF Similarity) + AI (Multi-Agent Audit Pipeline)</p>", unsafe_allow_html=True)

# Main form configuration
if st.session_state.screening_results is None:
    
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.markdown("### 📄 Configure Target Job Description (JD)")
        default_jd = """We are looking for a Senior Full-Stack Software Engineer with 5+ years of experience to join our core engineering team.

Key Requirements:
- Strong proficiency in Python, FastAPI, and asynchronous programming.
- Hands-on experience with modern frontend frameworks, preferably React with TypeScript.
- Working knowledge of databases (PostgreSQL/MongoDB) and cache layers (Redis).
- Experience with cloud architecture (AWS/GCP), Docker, and CI/CD pipelines.
- Solid understanding of software design patterns and writing clean, testable code.

Nice to have:
- Experience building AI-driven features or working with LLM APIs."""
        
        job_description = st.text_area(
            "Target Role Requirements:",
            value=default_jd,
            height=260
        )
        
    with col2:
        st.markdown("### 📥 Upload Candidate Resumes")
        uploaded_files = st.file_uploader(
            "Select Resume documents (PDF, DOCX, TXT):",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            help="Select multiple resumes from sample_resumes/ to screen them as a batch."
        )
        
        if uploaded_files:
            st.markdown(f"**Selected files ({len(uploaded_files)}):**")
            for f in uploaded_files:
                st.markdown(f"- {f.name} ({f.size / 1024:.0f} KB)")
                
    st.markdown("---")
    
    # Run pipeline button
    btn_col = st.columns([1, 4, 1])
    if btn_col[1].button("🚀 Run Multi-Agent ML/AI Screening Pipeline", use_container_width=True):
        if not uploaded_files:
            st.error("Please upload at least one candidate resume file.")
        elif not job_description.strip():
            st.error("Please provide a Job Description.")
        else:
            st.session_state.logs = []
            
            st.markdown("### 📟 Real-Time Agent Workflow Console")
            progress_bar = st.progress(0.0)
            console_view = st.empty()
            
            def log_to_console(message: str):
                st.session_state.logs.append(message)
                log_content = "\n".join([f"[{time.strftime('%H:%M:%S')}] {line}" for line in st.session_state.logs])
                console_view.code(log_content, language="bash")

            log_to_console("Initializing screening task...")
            
            # Write files to temp path for processing
            temp_dir = tempfile.mkdtemp()
            file_paths = []
            file_names = []
            for f in uploaded_files:
                temp_path = os.path.join(temp_dir, f.name)
                with open(temp_path, "wb") as buffer:
                    buffer.write(f.getbuffer())
                file_paths.append(temp_path)
                file_names.append(f.name)
                
            # Dynamically reload environment variables and configure genai on button click
            load_dotenv(override=True)
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                st.error("❌ **Error**: No `GEMINI_API_KEY` or `GOOGLE_API_KEY` found in environment/`.env` file. Please ensure you have created a `.env` file at the root directory of the project with a valid API key.")
                shutil.rmtree(temp_dir)
                st.stop()
            
            try:
                # Execute the centralized pipeline orchestrator
                results = run_screening_pipeline(
                    job_description=job_description,
                    file_paths=file_paths,
                    file_names=file_names,
                    model_name=model_choice,
                    log_callback=log_to_console
                )
                st.session_state.screening_results = results
                progress_bar.progress(1.0)
                shutil.rmtree(temp_dir)
                time.sleep(1.0)
                st.rerun()
            except Exception as e:
                st.error(f"❌ **Pipeline Execution Failed**: {str(e)}")
                shutil.rmtree(temp_dir)

# State: View Completed Results
if st.session_state.screening_results is not None:
    results = st.session_state.screening_results
    candidates_list = results["candidates"]
    report = results["ranking_report"]
    
    # Header reset and download actions
    col_hdr, col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([1.5, 1.0, 1.2, 1.2, 1.1])
    col_hdr.markdown("### 🏆 Screening Batch Results")
    
    # 1. Screen New Pool action
    if col_btn1.button("🔄 Screen New Pool", use_container_width=True):
        st.session_state.screening_results = None
        st.session_state.logs = []
        st.rerun()
        
    # 2. Download Recruiter Report action
    # Compile Markdown report
    report_md = f"""# Resume Screening Agent - Recruiter Batch Report
Date: {time.strftime('%Y-%m-%d')}
Role Title: {jd_analysis.role_title if jd_analysis else 'Target Position'}

## 💡 Batch Overview Findings
{report['overall_summary']}

---

## 📊 Candidate Leaderboard
"""
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
        
    col_btn2.download_button(
        label="📥 Download Markdown Report",
        data=report_md,
        file_name="Recruiter_Batch_Report.md",
        mime="text/markdown",
        use_container_width=True
    )

    # 3. Download CSV Leaderboard action
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
    csv_buffer = csv_df.to_csv(index=False).encode('utf-8')

    col_btn3.download_button(
        label="📥 Download CSV Rankings",
        data=csv_buffer,
        file_name="Candidate_Leaderboard.csv",
        mime="text/csv",
        use_container_width=True
    )

    # 4. Download JSON Details action
    import json
    class PipelineEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return super().default(obj)
    json_data = json.dumps(st.session_state.screening_results, cls=PipelineEncoder, indent=2)

    col_btn4.download_button(
        label="📥 Download JSON Report",
        data=json_data,
        file_name="Screening_Details_Report.json",
        mime="application/json",
        use_container_width=True
    )
        
    # Quick metrics cards
    m_col1, m_col2, m_col3 = st.columns(3)
    avg_score = sum([c["qa"].adjusted_score for c in candidates_list]) / len(candidates_list)
    top_cand = report["candidates"][0]["name"] if len(report["candidates"]) > 0 else "N/A"
    
    m_col1.metric("Candidates Screened", len(candidates_list))
    m_col2.metric("Average Score", f"{avg_score:.1f}%")
    m_col3.metric("Top Recommended Candidate", top_cand)
    
    # Global pool review summary box
    st.info(f"💡 **Batch Summary Findings**: {report['overall_summary']}")
    
    # Skill Gap Matrix expander
    jd_analysis = results.get("jd_analysis")
    if jd_analysis:
        with st.expander("📊 View Interactive Candidate Skill Gap Matrix", expanded=False):
            all_skills = list(jd_analysis.required_skills) + list(jd_analysis.preferred_skills)
            if all_skills:
                matrix_data = []
                for c_record in candidates_list:
                    c_name = c_record["profile"].name
                    row_dict = {"Candidate": c_name}
                    
                    eval_info = c_record.get("evaluation")
                    skills_lookup = {}
                    
                    # Safely retrieve skills_matrix from eval_info
                    skills_matrix = eval_info.get("skills_matrix") if isinstance(eval_info, dict) else getattr(eval_info, "skills_matrix", None)
                    if skills_matrix:
                        for skill_detail in skills_matrix:
                            skills_lookup[skill_detail["skill"].lower().strip()] = skill_detail["is_present"]
                    else:
                        cand_skills = [s.lower().strip() for s in c_record["profile"].skills]
                        for s in all_skills:
                            skills_lookup[s.lower().strip()] = s.lower().strip() in cand_skills
                            
                    for skill in all_skills:
                        is_present = skills_lookup.get(skill.lower().strip(), False)
                        row_dict[skill] = "✔️ Yes" if is_present else "❌ No"
                        
                    matrix_data.append(row_dict)
                    
                matrix_df = pd.DataFrame(matrix_data)
                st.dataframe(matrix_df, use_container_width=True, hide_index=True)
            else:
                st.text("No skills identified in the Job Description analysis.")
    
    # Layout Grid: Left Leaderboard Graph, Right Candidate Details Inspector
    col_left, col_right = st.columns([1.1, 1.8])
    
    with col_left:
        st.markdown("#### 📊 Candidate Leaderboard")
        
        # Prepare leaderboard dataframe
        leader_data = []
        for c in report["candidates"]:
            matching_full = next((x for x in candidates_list if x["profile"].name.strip().lower() == c["name"].strip().lower()), None)
            ml_similarity = matching_full["ml_score"] if matching_full else 0.0
            
            leader_data.append({
                "Rank": f"#{c['rank']}",
                "Candidate": c["name"],
                "ML Match": f"{ml_similarity:.1f}%",
                "Final Score": f"{c['overall_score']:.1f}%",
                "Fit": c["recommendation"]
            })
            
        df = pd.DataFrame(leader_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Render horizontal bar chart of scores
        st.markdown("#### 📈 Matplotlib Score Comparison")
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0f172a')
        
        # Prepare graph data
        names = [c["name"] for c in report["candidates"]][::-1]
        final_scores = [c["overall_score"] for c in report["candidates"]][::-1]
        
        # Map colors based on scores
        colors = []
        for s in final_scores:
            if s >= 80:
                colors.append('#10b981') # green
            elif s >= 60:
                colors.append('#f59e0b') # orange
            else:
                colors.append('#f43f5e') # red
                
        bars = ax.barh(names, final_scores, color=colors, height=0.6)
        
        # Labels and design styling
        ax.set_title("Audited Overall Score Breakdown", color='#f1f5f9', fontsize=12, fontweight='bold')
        ax.set_xlabel("Overall Score (0-100%)", color='#94a3b8', fontsize=10)
        ax.tick_params(colors='#94a3b8', labelsize=9)
        ax.set_xlim(0, 105)
        
        # Grid lines
        ax.grid(axis='x', color='rgba(255, 255, 255, 0.05)', linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('rgba(255, 255, 255, 0.1)')
        ax.spines['bottom'].set_color('rgba(255, 255, 255, 0.1)')
        
        # Add labels to the ends of the bars
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 2, bar.get_y() + bar.get_height()/2, f'{width:.0f}%', 
                    va='center', ha='left', color='#f1f5f9', fontsize=8, fontweight='bold')
            
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        
    with col_right:
        st.markdown("#### 🔍 Candidate Detailed Profile Audit")
        
        # Dropdown selection for detailed view
        selected_name = st.selectbox(
            "Inspect Candidate Assessment:",
            options=[c["name"] for c in report["candidates"]]
        )
        
        # Retrieve candidate details
        cand_detail = next((x for x in candidates_list if x["profile"].name.strip().lower() == selected_name.strip().lower()), None)
        report_detail = next((x for x in report["candidates"] if x["name"].strip().lower() == selected_name.strip().lower()), None)
        
        if cand_detail and report_detail:
            # Candidate summary callout
            st.markdown(
                f"""
                <div style="background-color: rgba(99, 102, 241, 0.08); padding: 1rem; border-left: 3px solid #8b5cf6; border-radius: 6px; margin-bottom: 1.5rem; font-size: 0.9rem;">
                    <strong>Global Fit Verdict</strong>: {report_detail['summary']}
                </div>
                """,
                unsafe_allow_html=True
            )
            
            tab_fit, tab_questions, tab_emails, tab_qa, tab_profile = st.tabs([
                "📊 Rating Scorecard & Gaps",
                "❓ Tailored Interview Guide",
                "✉️ Recruiter Outreach Package",
                "🛡️ QA Audit Logs",
                "👤 Extracted Profile Details"
            ])
            
            with tab_fit:
                st.markdown("##### Score breakdowns by Category")
                cat_cols = st.columns(2)
                for i, cat in enumerate(cand_detail["evaluation"]["categories"]):
                    col_tgt = cat_cols[i % 2]
                    score = cat["score"]
                    color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#f43f5e"
                    
                    col_tgt.markdown(
                        f"""
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 0.75rem; margin-bottom: 0.75rem;">
                            <div style="display:flex; justify-content:space-between; margin-bottom: 0.25rem;">
                                <span style="font-size:0.8rem; font-weight:600;">{cat['category']}</span>
                                <span style="font-size:0.8rem; font-weight:700; color:{color};">{score:.0f}/100</span>
                            </div>
                            <div style="background:rgba(255,255,255,0.05); height:4px; border-radius:99px; overflow:hidden;">
                                <div style="background:{color}; width:{score}%; height:100%;"></div>
                            </div>
                            <p style="font-size:0.7rem; color:#94a3b8; margin-top:0.4rem; line-height:1.3;">{cat['reasoning']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                st.markdown("---")
                
                # Skills matching column
                sk_col1, sk_col2 = st.columns(2)
                with sk_col1:
                    st.markdown("<p style='color:#10b981; font-weight:bold; font-size:0.85rem;'>✔️ Matching Skills</p>", unsafe_allow_html=True)
                    if cand_detail["evaluation"]["matching_skills"]:
                        st.markdown(" ".join([f"<span style='background:rgba(16,185,129,0.1); color:#10b981; border:1px solid rgba(16,185,129,0.2); padding:0.15rem 0.4rem; border-radius:4px; font-size:0.75rem; margin-right:0.3rem;'>{s}</span>" for s in cand_detail["evaluation"]["matching_skills"]]), unsafe_allow_html=True)
                    else:
                        st.text("None identified.")
                with sk_col2:
                    st.markdown("<p style='color:#f43f5e; font-weight:bold; font-size:0.85rem;'>❌ Gaps / Missing Competencies</p>", unsafe_allow_html=True)
                    if cand_detail["evaluation"]["missing_skills"]:
                        st.markdown(" ".join([f"<span style='background:rgba(244,63,94,0.1); color:#f43f5e; border:1px solid rgba(244,63,94,0.2); padding:0.15rem 0.4rem; border-radius:4px; font-size:0.75rem; margin-right:0.3rem;'>{s}</span>" for s in cand_detail["evaluation"]["missing_skills"]]), unsafe_allow_html=True)
                    else:
                        st.text("None identified.")
                        
                st.markdown("---")
                
                # Pros & Cons
                pro_col, con_col = st.columns(2)
                with pro_col:
                    st.markdown("**Key Strengths**")
                    for p in cand_detail["evaluation"]["pros"]:
                        st.markdown(f"- {p}")
                with con_col:
                    st.markdown("**Areas of Concern**")
                    for c in cand_detail["evaluation"]["cons"]:
                        st.markdown(f"- {c}")
                        
            with tab_questions:
                st.markdown("##### ❓ Customized Interview Guide")
                st.write("Tailored behavioral and technical questions, expected answers, and red flags prepared for this candidate:")
                
                # Check if interview_guide is present in report_detail
                guide = report_detail.get("interview_guide") if isinstance(report_detail, dict) else getattr(report_detail, "interview_guide", None)
                if guide:
                    for idx, q_detail in enumerate(guide):
                        st.markdown(
                            f"""
                            <div style="background: rgba(15,23,42,0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                                <div style="display:flex; gap:0.5rem; margin-bottom:0.5rem;">
                                    <span style="color:#8b5cf6; font-weight:800; font-size:0.9rem;">Q{idx+1}</span>
                                    <span style="font-size:0.9rem; color:#f1f5f9; font-weight:bold; line-height:1.4;">{q_detail['question']}</span>
                                </div>
                                <div style="font-size:0.8rem; color:#a5b4fc; margin-bottom:0.4rem; padding-left: 1.5rem;">
                                    <strong>💡 Expected Answer:</strong> {q_detail['expected_answer']}
                                </div>
                                <div style="font-size:0.8rem; color:#f43f5e; padding-left: 1.5rem;">
                                    <strong>⚠️ Red Flags to watch:</strong> {q_detail['red_flags']}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                else:
                    flat_qs = report_detail.get("interview_questions") if isinstance(report_detail, dict) else getattr(report_detail, "interview_questions", [])
                    for idx, q in enumerate(flat_qs):
                        st.markdown(f"**Q{idx+1}**: {q}")
                        
            with tab_emails:
                st.markdown("##### ✉️ Personalized Outreach & Feedback Emails")
                st.write("AI-generated templates tailored specifically to this candidate's application results:")
                
                # Retrieve email drafts
                outreach = report_detail.get("outreach_email") if isinstance(report_detail, dict) else getattr(report_detail, "outreach_email", "")
                rejection = report_detail.get("rejection_email") if isinstance(report_detail, dict) else getattr(report_detail, "rejection_email", "")
                
                email_type = st.radio("Select Email Draft:", ["Interview Invitation (Outreach)", "Constructive Rejection"], key=f"email_type_{selected_name}")
                
                if email_type == "Interview Invitation (Outreach)":
                    st.text_area("Outreach Template:", value=outreach, height=250, key=f"outreach_text_{selected_name}")
                else:
                    st.text_area("Rejection Feedback Template:", value=rejection, height=250, key=f"rejection_text_{selected_name}")
                    
            with tab_qa:
                # Changes indicators
                if cand_detail["qa"]["changes_made"]:
                    st.warning(f"⚠️ **QA Audit: Score Adjusted**\n\n*   **Summary**: {cand_detail['qa']['adjustments_summary']}\n*   **Original Scorer Grade**: {cand_detail['qa']['original_score']:.0f}%\n*   **Audited Scorer Grade**: {cand_detail['qa']['adjusted_score']:.0f}%")
                else:
                    st.success("✔️ **QA Audit Verified**\n\nOriginal evaluator scores verified as consistent and accurate. No adjustments needed.")
                    
                st.markdown("##### QA Auditor Justification Details")
                st.info(cand_detail["qa"]["justification"])
                
            with tab_profile:
                # Candidate profile details
                st.markdown(f"**Contact**: 📧 {cand_detail['profile'].email} | 📞 {cand_detail['profile'].phone}")
                st.markdown(f"**Extracted Total Experience**: {cand_detail['profile'].experience_years:.1f} Years")
                
                st.markdown("##### extracted Skills Profile")
                st.write(", ".join(cand_detail["profile"].skills))
                
                st.markdown("##### Academic Credentials")
                for edu in cand_detail["profile"].education:
                    st.markdown(f"- {edu}")
                    
                st.markdown("##### Work History Timeline")
                for job in cand_detail["profile"].work_history:
                    st.markdown(f"- {job}")
