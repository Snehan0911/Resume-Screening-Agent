import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  X,
  Brain,
  CheckCircle,
  AlertTriangle,
  Play,
  Sparkles,
  ChevronRight,
  Mail,
  Phone,
  Calendar,
  Download,
  RefreshCw,
  Award,
  Briefcase,
  TrendingUp,
  FileDown
} from 'lucide-react';

interface ScorecardCategory {
  category: string;
  score: number;
  reasoning: string;
}

interface Candidate {
  file_name: string;
  name: string;
  email: string;
  phone: string;
  skills: string[];
  experience_years: number;
  education: string[];
  work_history: string[];
  evaluation: {
    overall_score: number;
    categories: ScorecardCategory[];
    matching_skills: string[];
    missing_skills: string[];
    pros: string[];
    cons: string[];
    recommendation: string;
  };
  qa: {
    candidate_name: string;
    original_score: number;
    adjusted_score: number;
    changes_made: boolean;
    adjustments_summary: string;
    justification: string;
  };
}

interface CandidateRankingDetail {
  rank: number;
  name: string;
  overall_score: number;
  recommendation: string;
  summary: string;
  interview_questions: string[];
}

interface RankingReport {
  job_description: string;
  candidates: CandidateRankingDetail[];
  overall_summary: string;
}

const DEFAULT_JOB_DESCRIPTION = `We are looking for a Senior Full-Stack Software Engineer with 5+ years of experience to join our core engineering team.

Key Requirements:
- Strong proficiency in Python, FastAPI, and asynchronous programming.
- Hands-on experience with modern frontend frameworks, preferably React with TypeScript.
- Working knowledge of databases (PostgreSQL/MongoDB) and cache layers (Redis).
- Experience with cloud architecture (AWS/GCP), Docker, and CI/CD pipelines.
- Solid understanding of software design patterns and writing clean, testable code.
- Strong communication skills and experience working in an agile environment.

Nice to have:
- Experience building AI-driven features or working with LLM APIs.
- Background in data processing or data pipelines.`;

export default function App() {
  const [jobDescription, setJobDescription] = useState(DEFAULT_JOB_DESCRIPTION);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'failed'>('idle');
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  
  // Results
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [rankingReport, setRankingReport] = useState<RankingReport | null>(null);
  const [selectedCandidateName, setSelectedCandidateName] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'match' | 'questions' | 'qa' | 'profile'>('match');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const logTerminalRef = useRef<HTMLDivElement>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [logs]);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, []);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (files: File[]) => {
    const validExtensions = ['.pdf', '.docx', '.txt', '.md'];
    const filtered = files.filter(file => {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      return validExtensions.includes(ext);
    });
    setSelectedFiles(prev => [...prev, ...filtered]);
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const triggerUpload = () => {
    fileInputRef.current?.click();
  };

  const handleStartScreening = async () => {
    if (selectedFiles.length === 0) {
      alert("Please upload at least one resume.");
      return;
    }
    if (!jobDescription.trim()) {
      alert("Please provide a Job Description.");
      return;
    }

    setErrorMsg(null);
    setStatus('processing');
    setProgress(0);
    setLogs(["Preparing files for upload..."]);
    setCandidates([]);
    setRankingReport(null);
    setSelectedCandidateName(null);

    const formData = new FormData();
    selectedFiles.forEach(file => {
      formData.append("files", file);
    });
    formData.append("job_description", jobDescription);

    try {
      const res = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server returned error: ${res.statusText}`);
      }

      const data = await res.json();
      setTaskId(data.task_id);
      setLogs(prev => [...prev, `Task started successfully with ID: ${data.task_id}`, "Connecting to agents..."]);
      
      // Start Polling
      startPolling(data.task_id);
    } catch (err: any) {
      setStatus('failed');
      setErrorMsg(err.message || "Failed to start screening process.");
      setLogs(prev => [...prev, `[ERROR] ${err.message || "Failed to connect to API"}`]);
    }
  };

  const startPolling = (taskId: string) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    
    pollingIntervalRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/status/${taskId}`);
        if (!res.ok) throw new Error("Failed to fetch task status.");
        
        const data = await res.json();
        setProgress(data.progress);
        setLogs(data.logs);
        setCompletedCount(data.completed_count);
        setTotalCount(data.total_count);

        if (data.status === 'completed') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          fetchResults(taskId);
        } else if (data.status === 'failed') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setStatus('failed');
          setErrorMsg("Screening pipeline reported a failure.");
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    }, 1500);
  };

  const fetchResults = async (taskId: string) => {
    setLogs(prev => [...prev, "Fetching final evaluations and ranking report..."]);
    try {
      const res = await fetch(`http://localhost:8000/api/results/${taskId}`);
      if (!res.ok) throw new Error("Failed to load screening results.");
      
      const data = await res.json();
      setCandidates(data.candidates || []);
      setRankingReport(data.ranking_report);
      setStatus('completed');
      
      // Select the top-ranked candidate by default
      if (data.ranking_report && data.ranking_report.candidates.length > 0) {
        setSelectedCandidateName(data.ranking_report.candidates[0].name);
      } else if (data.candidates && data.candidates.length > 0) {
        setSelectedCandidateName(data.candidates[0].name);
      }
    } catch (err: any) {
      setStatus('failed');
      setErrorMsg(err.message || "Failed to retrieve screening outcomes.");
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setTaskId(null);
    setProgress(0);
    setLogs([]);
    setSelectedFiles([]);
    setCandidates([]);
    setRankingReport(null);
    setSelectedCandidateName(null);
    setErrorMsg(null);
  };

  const downloadJSON = () => {
    if (!rankingReport) return;
    const reportData = {
      rankingReport,
      candidates
    };
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Resume_Screening_Report_${taskId?.slice(0, 8)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const selectedCandidate = candidates.find(c => c.name === selectedCandidateName);
  const selectedRankInfo = rankingReport?.candidates.find(c => c.name === selectedCandidateName);

  // Compute circular stroke offset for score SVG
  const getCircleStrokeProps = (score: number) => {
    const radius = 28;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (score / 100) * circumference;
    return {
      strokeDasharray: circumference,
      strokeDashoffset: strokeDashoffset
    };
  };

  // Get color for recommendation badge
  const getRecommendationBadge = (rec: string) => {
    const cleanRec = rec.toLowerCase();
    if (cleanRec.includes('shortlist')) {
      return <span className="badge badge-shortlist">Shortlist</span>;
    } else if (cleanRec.includes('interview')) {
      return <span className="badge badge-interview">Interview</span>;
    } else {
      return <span className="badge badge-reject">Reject</span>;
    }
  };

  const getScoreColorClass = (score: number) => {
    if (score >= 80) return 'text-emerald-400';
    if (score >= 60) return 'text-amber-400';
    return 'text-rose-400';
  };

  const getScoreStrokeColor = (score: number) => {
    if (score >= 80) return '#10b981'; // green-500
    if (score >= 60) return '#f59e0b'; // amber-500
    return '#f43f5e'; // rose-500
  };

  return (
    <div style={{ position: 'relative', overflow: 'hidden', minHeight: '100vh' }}>
      {/* Decorative Orbs */}
      <div className="glow-orb glow-orb-purple"></div>
      <div className="glow-orb glow-orb-cyan"></div>

      <div className="app-container">
        {/* Header */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)', borderRadius: '10px', padding: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(139, 92, 246, 0.3)' }}>
                <Brain size={24} color="white" />
              </div>
              <h1 className="gradient-text" style={{ fontSize: '1.8rem', fontWeight: 800 }}>TalentStream AI</h1>
            </div>
            <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.9rem', marginTop: '0.25rem' }}>
              Collaborative Multi-Agent Resume Screening System
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'hsl(var(--text-muted))', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="pulse-indicator"></span> Agents Active
            </span>
            {status === 'completed' && (
              <button 
                onClick={handleReset} 
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', borderRadius: '10px', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', transition: 'all 0.2s' }}
                className="glass-panel-hover"
              >
                <RefreshCw size={16} /> New Screening
              </button>
            )}
          </div>
        </header>

        {/* State: Idle / Uploading Form */}
        {status === 'idle' && (
          <div style={{ animation: 'logFadeIn 0.3s ease-out' }}>
            <div className="glass-panel" style={{ padding: '2.5rem', marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '1.4rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={20} style={{ color: 'hsl(var(--primary))' }} /> Configure Screening Criteria
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem' }}>
                {/* Job Description Textarea */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'hsl(var(--text-secondary))', marginBottom: '0.5rem' }}>
                    Target Job Description (JD)
                  </label>
                  <textarea
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    className="text-area-custom"
                    placeholder="Paste the job description here..."
                  />
                </div>

                {/* Resume Upload Box */}
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'hsl(var(--text-secondary))', marginBottom: '0.5rem' }}>
                    Candidate Resumes (PDF, DOCX, TXT)
                  </label>
                  
                  <div
                    className="uploader-dropzone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    onClick={triggerUpload}
                    style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem' }}
                  >
                    <Upload size={32} style={{ color: 'hsl(var(--text-muted))' }} />
                    <div>
                      <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>Drag & drop resumes here</p>
                      <p style={{ fontSize: '0.8rem', color: 'hsl(var(--text-muted))', marginTop: '0.2rem' }}>or click to browse from files</p>
                    </div>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      multiple
                      accept=".pdf,.docx,.txt,.md"
                      style={{ display: 'none' }}
                    />
                  </div>

                  {/* Uploaded Files list */}
                  {selectedFiles.length > 0 && (
                    <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid hsl(var(--border-subtle))', maxHeight: '150px', overflowY: 'auto', padding: '0.5rem' }}>
                      {selectedFiles.map((file, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.4rem 0.6rem', borderBottom: idx < selectedFiles.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none', fontSize: '0.8rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                            <FileText size={14} style={{ color: 'hsl(var(--primary))', flexShrink: 0 }} />
                            <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{file.name}</span>
                            <span style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem' }}>({(file.size / 1024).toFixed(0)} KB)</span>
                          </div>
                          <button onClick={() => removeFile(idx)} style={{ background: 'none', border: 'none', color: 'hsl(var(--text-muted))', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                            <X size={14} className="hover:text-white" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Run Action */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid hsl(var(--border-subtle))' }}>
                <button
                  onClick={handleStartScreening}
                  disabled={selectedFiles.length === 0}
                  className="btn-primary"
                >
                  <Play size={16} /> Run Multi-Agent Screening
                </button>
              </div>
            </div>

            {/* Explanatory cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem' }}>
              <div className="glass-panel" style={{ padding: '1.25rem' }}>
                <div style={{ color: 'hsl(var(--primary))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Brain size={18} />
                  <h3 style={{ fontSize: '0.95rem' }}>1. Parse Agent</h3>
                </div>
                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', lineHeight: 1.4 }}>
                  Parses document formats (PDF/DOCX) extracting skills, experience history, and credentials into standard JSON.
                </p>
              </div>
              <div className="glass-panel" style={{ padding: '1.25rem' }}>
                <div style={{ color: 'hsl(var(--accent-cyan))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <TrendingUp size={18} />
                  <h3 style={{ fontSize: '0.95rem' }}>2. Review Agent</h3>
                </div>
                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', lineHeight: 1.4 }}>
                  Grades matching and missing skills, calculates scores out of 100 on role fit, and creates shortlist recommendations.
                </p>
              </div>
              <div className="glass-panel" style={{ padding: '1.25rem' }}>
                <div style={{ color: 'hsl(var(--warning))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CheckCircle size={18} />
                  <h3 style={{ fontSize: '0.95rem' }}>3. QA Agent</h3>
                </div>
                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', lineHeight: 1.4 }}>
                  Audits evaluations, checks work-history timelines for consistency, adjusts scores, and filters bias or hallucinations.
                </p>
              </div>
              <div className="glass-panel" style={{ padding: '1.25rem' }}>
                <div style={{ color: 'hsl(var(--success))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={18} />
                  <h3 style={{ fontSize: '0.95rem' }}>4. Ranking Agent</h3>
                </div>
                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', lineHeight: 1.4 }}>
                  Orders the shortlist pool, synthesizes global summaries, and designs specialized interview questions per candidate.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* State: Processing (Live Logs Console) */}
        {status === 'processing' && (
          <div className="glass-panel" style={{ padding: '2.5rem', animation: 'logFadeIn 0.3s ease-out' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <RefreshCw className="pulse-indicator" style={{ animation: 'spin 2s linear infinite' }} size={20} />
                  Multi-Agent Pipeline Screening...
                </h2>
                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                  Resumes processed: {completedCount} of {totalCount}
                </p>
              </div>
              <span style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'var(--font-display)', color: 'hsl(var(--primary))' }}>
                {Math.round(progress * 100)}%
              </span>
            </div>

            {/* Progress Bar */}
            <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '99px', overflow: 'hidden', marginBottom: '2rem' }}>
              <div style={{ width: `${progress * 100}%`, height: '100%', background: 'linear-gradient(90deg, hsl(var(--primary)) 0%, #06b6d4 100%)', transition: 'width 0.4s ease' }}></div>
            </div>

            {/* Log Terminal */}
            <h3 style={{ fontSize: '0.9rem', color: 'hsl(var(--text-secondary))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Brain size={14} /> Agent Workspace Stream Logs
            </h3>
            <div ref={logTerminalRef} className="log-terminal">
              {logs.map((log, idx) => (
                <div key={idx} className="log-line">
                  <span style={{ color: '#64748b' }}>[{new Date().toLocaleTimeString()}]</span> {log}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* State: Failed */}
        {status === 'failed' && (
          <div className="glass-panel" style={{ padding: '2.5rem', border: '1px solid rgba(244,63,94,0.3)', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
              <AlertTriangle size={32} style={{ color: 'hsl(var(--destructive))', flexShrink: 0 }} />
              <div>
                <h2 style={{ fontSize: '1.3rem', color: 'hsl(var(--destructive))', marginBottom: '0.5rem' }}>Screening Run Failed</h2>
                <p style={{ fontSize: '0.9rem', color: 'hsl(var(--text-secondary))' }}>
                  {errorMsg || "An unexpected error occurred while analyzing documents. Please verify your Gemini API key is configured correctly and restart the server."}
                </p>
                <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                  <button onClick={handleReset} className="btn-primary" style={{ background: 'hsl(var(--destructive))' }}>
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* State: Completed Results View */}
        {status === 'completed' && (
          <div style={{ animation: 'logFadeIn 0.4s ease-out' }}>
            {/* Quick Metrics Bar */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <div style={{ background: 'rgba(99, 102, 241, 0.1)', color: 'hsl(var(--primary))', borderRadius: '12px', padding: '0.75rem' }}>
                  <FileText size={24} />
                </div>
                <div>
                  <p style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Candidates Processed</p>
                  <p style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>{candidates.length}</p>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <div style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'hsl(var(--accent-cyan))', borderRadius: '12px', padding: '0.75rem' }}>
                  <TrendingUp size={24} />
                </div>
                <div>
                  <p style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Average Match Score</p>
                  <p style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-display)', marginTop: '0.1rem' }}>
                    {(candidates.reduce((acc, curr) => acc + curr.qa.adjusted_score, 0) / (candidates.length || 1)).toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                  <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'hsl(var(--success))', borderRadius: '12px', padding: '0.75rem' }}>
                    <Award size={24} />
                  </div>
                  <div>
                    <p style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Top Candidate</p>
                    <p style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '160px' }}>
                      {rankingReport?.candidates[0]?.name || "N/A"}
                    </p>
                  </div>
                </div>
                {rankingReport && (
                  <button 
                    onClick={downloadJSON}
                    style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', borderRadius: '10px', padding: '0.4rem 0.8rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', transition: 'all 0.2s' }}
                    className="glass-panel-hover"
                  >
                    <FileDown size={14} /> Export JSON
                  </button>
                )}
              </div>
            </div>

            {/* Batch Level Summary Block */}
            {rankingReport && (
              <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem', background: 'rgba(99, 102, 241, 0.03)' }}>
                <h3 style={{ fontSize: '1rem', color: 'hsl(var(--primary))', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={16} /> Global Batch Review Summary
                </h3>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.5, color: 'hsl(var(--text-secondary))' }}>
                  {rankingReport.overall_summary}
                </p>
              </div>
            )}

            {/* Main Interactive Screen Grid */}
            <div className="dashboard-grid">
              {/* Left Column - Candidate Rankings List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'hsl(var(--text-primary))', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  Candidates Sorted by Fit
                </h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', maxHeight: '550px' }}>
                  {rankingReport?.candidates.map((cand, idx) => {
                    const fullCandInfo = candidates.find(c => c.name === cand.name);
                    const isSelected = selectedCandidateName === cand.name;
                    const finalScore = cand.overall_score;

                    return (
                      <div
                        key={idx}
                        onClick={() => setSelectedCandidateName(cand.name)}
                        className={`glass-panel ${isSelected ? 'border-primary' : 'glass-panel-hover'}`}
                        style={{
                          padding: '1rem',
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(99, 102, 241, 0.1)' : 'rgba(15, 23, 42, 0.5)',
                          borderColor: isSelected ? 'hsl(var(--primary))' : 'rgba(255, 255, 255, 0.06)'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <div style={{ background: isSelected ? 'hsl(var(--primary))' : 'hsl(var(--border-subtle))', color: 'white', width: '24px', height: '24px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700 }}>
                              {cand.rank}
                            </div>
                            <div>
                              <p style={{ fontWeight: 600, fontSize: '0.95rem', color: isSelected ? 'white' : 'hsl(var(--text-primary))' }}>{cand.name}</p>
                              <p style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem', marginTop: '0.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>
                                {fullCandInfo?.file_name}
                              </p>
                            </div>
                          </div>
                          
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            {getRecommendationBadge(cand.recommendation)}
                            
                            <div style={{ width: '40px', height: '40px', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              <svg width="40" height="40">
                                <circle cx="20" cy="20" r="17" fill="transparent" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                                <circle cx="20" cy="20" r="17" fill="transparent" 
                                  stroke={getScoreStrokeColor(finalScore)} 
                                  strokeWidth="3" 
                                  strokeDasharray={2 * Math.PI * 17}
                                  strokeDashoffset={2 * Math.PI * 17 - (finalScore / 100) * 2 * Math.PI * 17}
                                  transform="rotate(-90 20 20)"
                                />
                              </svg>
                              <span style={{ position: 'absolute', fontSize: '0.75rem', fontWeight: 700 }}>{Math.round(finalScore)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Column - Selected Candidate Evaluation Panel */}
              <div className="glass-panel" style={{ padding: '2rem', minHeight: '500px', display: 'flex', flexDirection: 'column' }}>
                {selectedCandidate ? (
                  <>
                    {/* Header of Candidate Detail */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid hsl(var(--border-subtle))', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
                      <div>
                        <h2 style={{ fontSize: '1.5rem', color: 'white' }}>{selectedCandidate.name}</h2>
                        
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '0.5rem', color: 'hsl(var(--text-secondary))', fontSize: '0.85rem' }}>
                          {selectedCandidate.email && (
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              <Mail size={14} /> {selectedCandidate.email}
                            </span>
                          )}
                          {selectedCandidate.phone && (
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              <Phone size={14} /> {selectedCandidate.phone}
                            </span>
                          )}
                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <Briefcase size={14} /> {selectedCandidate.experience_years} Years Exp.
                          </span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ textAlign: 'right' }}>
                          <p style={{ fontSize: '0.7rem', color: 'hsl(var(--text-muted))', fontWeight: 600, textTransform: 'uppercase' }}>QA Adjusted Score</p>
                          <p style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)', lineHeight: 1 }} className={getScoreColorClass(selectedCandidate.qa.adjusted_score)}>
                            {Math.round(selectedCandidate.qa.adjusted_score)}
                            <span style={{ fontSize: '1rem', color: 'hsl(var(--text-muted))', fontWeight: 400 }}>/100</span>
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Tabs Headers */}
                    <div className="tab-header">
                      <button className={`tab-btn ${activeTab === 'match' ? 'active' : ''}`} onClick={() => setActiveTab('match')}>
                        Score Card & Fit
                      </button>
                      <button className={`tab-btn ${activeTab === 'questions' ? 'active' : ''}`} onClick={() => setActiveTab('questions')}>
                        Custom Interview Questions
                      </button>
                      <button className={`tab-btn ${activeTab === 'qa' ? 'active' : ''}`} onClick={() => setActiveTab('qa')}>
                        QA Agent Transcript {selectedCandidate.qa.changes_made && <span style={{ width: '6px', height: '6px', background: 'red', borderRadius: '50%', display: 'inline-block', verticalAlign: 'middle', marginLeft: '4px' }}></span>}
                      </button>
                      <button className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveTab('profile')}>
                        Extracted Profile
                      </button>
                    </div>

                    {/* Tab Body */}
                    <div style={{ flex: 1, overflowY: 'auto' }}>
                      {/* Tab 1: Match Scorecard */}
                      {activeTab === 'match' && (
                        <div style={{ animation: 'logFadeIn 0.2s ease-out' }}>
                          {/* Rank specific Summary */}
                          {selectedRankInfo && (
                            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', borderLeft: '3px solid hsl(var(--primary))', marginBottom: '1.5rem', fontSize: '0.9rem', color: 'hsl(var(--text-secondary))', lineHeight: 1.4 }}>
                              <strong>Rank Overview:</strong> {selectedRankInfo.summary}
                            </div>
                          )}

                          {/* 4 Scorecard Categories */}
                          <h4 style={{ fontSize: '0.95rem', color: 'hsl(var(--text-primary))', marginBottom: '1rem' }}>Category Ratings</h4>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '2rem' }}>
                            {selectedCandidate.evaluation.categories.map((cat, idx) => (
                              <div key={idx} style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.03)', borderRadius: '12px', padding: '1rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{cat.category}</span>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 700 }} className={getScoreColorClass(cat.score)}>{cat.score}/100</span>
                                </div>
                                <div style={{ width: '100%', height: '5px', background: 'rgba(255,255,255,0.05)', borderRadius: '99px', overflow: 'hidden', marginBottom: '0.6rem' }}>
                                  <div style={{ width: `${cat.score}%`, height: '100%', background: getScoreStrokeColor(cat.score) }}></div>
                                </div>
                                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.75rem', lineHeight: 1.3 }}>{cat.reasoning}</p>
                              </div>
                            ))}
                          </div>

                          {/* Skill Matching */}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
                            <div>
                              <h4 style={{ fontSize: '0.9rem', color: 'hsl(var(--success))', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <CheckCircle size={14} /> Matching Skills ({selectedCandidate.evaluation.matching_skills.length})
                              </h4>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {selectedCandidate.evaluation.matching_skills.length > 0 ? (
                                  selectedCandidate.evaluation.matching_skills.map((s, idx) => (
                                    <span key={idx} style={{ fontSize: '0.75rem', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.15)', color: 'hsl(var(--success))', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>{s}</span>
                                  ))
                                ) : (
                                  <span style={{ color: 'hsl(var(--text-muted))', fontSize: '0.8rem' }}>None listed</span>
                                )}
                              </div>
                            </div>

                            <div>
                              <h4 style={{ fontSize: '0.9rem', color: 'hsl(var(--destructive))', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <AlertTriangle size={14} /> Gaps & Missing Skills ({selectedCandidate.evaluation.missing_skills.length})
                              </h4>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {selectedCandidate.evaluation.missing_skills.length > 0 ? (
                                  selectedCandidate.evaluation.missing_skills.map((s, idx) => (
                                    <span key={idx} style={{ fontSize: '0.75rem', background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(244, 63, 94, 0.15)', color: 'hsl(var(--destructive))', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>{s}</span>
                                  ))
                                ) : (
                                  <span style={{ color: 'hsl(var(--success))', fontSize: '0.8rem' }}>None identified</span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Pros & Cons */}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                            <div>
                              <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem' }}>Key Strengths</h4>
                              <ul style={{ listStyleType: 'disc', paddingLeft: '1.2rem', color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                {selectedCandidate.evaluation.pros.map((pro, idx) => (
                                  <li key={idx}>{pro}</li>
                                ))}
                              </ul>
                            </div>

                            <div>
                              <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem' }}>Concerns / Red Flags</h4>
                              <ul style={{ listStyleType: 'disc', paddingLeft: '1.2rem', color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                {selectedCandidate.evaluation.cons.map((con, idx) => (
                                  <li key={idx}>{con}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Tab 2: Custom Interview Questions */}
                      {activeTab === 'questions' && (
                        <div style={{ animation: 'logFadeIn 0.2s ease-out' }}>
                          <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.85rem', marginBottom: '1.25rem', lineHeight: 1.4 }}>
                            The Ranking Agent generated these custom questions specifically tailored to address gaps, short tenures, or check technical claims found in {selectedCandidate.name}'s resume:
                          </p>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {selectedRankInfo?.interview_questions.map((q, idx) => (
                              <div key={idx} style={{ background: 'rgba(15, 23, 42, 0.4)', border: '1px solid hsl(var(--border-subtle))', borderRadius: '12px', padding: '1rem' }}>
                                <div style={{ display: 'flex', gap: '0.75rem' }}>
                                  <span style={{ color: 'hsl(var(--primary))', fontWeight: 800, fontSize: '0.95rem' }}>Q{idx + 1}</span>
                                  <div>
                                    <p style={{ fontSize: '0.9rem', fontWeight: 500, color: 'white', lineHeight: 1.4 }}>{q}</p>
                                    <p style={{ color: 'hsl(var(--text-muted))', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                                      Probes: {idx === 0 ? "Technical skill verification" : idx === 1 ? "Experience gap check" : "Behavioral/Fit validation"}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Tab 3: QA Agent Transcript */}
                      {activeTab === 'qa' && (
                        <div style={{ animation: 'logFadeIn 0.2s ease-out' }}>
                          {selectedCandidate.qa.changes_made ? (
                            <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                              <AlertTriangle size={18} style={{ color: 'hsl(var(--warning))', flexShrink: 0, marginTop: '2px' }} />
                              <div>
                                <h5 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'hsl(var(--warning))' }}>Score Adjusted by QA Agent</h5>
                                <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', marginTop: '0.2rem', lineHeight: 1.4 }}>
                                  <strong>Adjustment Summary:</strong> {selectedCandidate.qa.adjustments_summary}
                                </p>
                                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                                  <span>Original Score: <del>{selectedCandidate.qa.original_score}</del></span>
                                  <span style={{ fontWeight: 'bold' }}>New Score: {selectedCandidate.qa.adjusted_score}</span>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                              <CheckCircle size={18} style={{ color: 'hsl(var(--success))', flexShrink: 0 }} />
                              <span style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.85rem' }}>
                                QA Audit successful. Original score verified as accurate (no adjustments made).
                              </span>
                            </div>
                          )}

                          <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem' }}>QA Agent Justification</h4>
                          <p style={{ color: 'hsl(var(--text-secondary))', fontSize: '0.85rem', lineHeight: 1.5, background: 'rgba(255,255,255,0.01)', padding: '1rem', border: '1px solid rgba(255,255,255,0.03)', borderRadius: '12px' }}>
                            {selectedCandidate.qa.justification}
                          </p>
                        </div>
                      )}

                      {/* Tab 4: Parsed Profile */}
                      {activeTab === 'profile' && (
                        <div style={{ animation: 'logFadeIn 0.2s ease-out', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                          <div>
                            <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <Award size={14} style={{ color: 'hsl(var(--primary))' }} /> Skills Profile
                            </h4>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                              {selectedCandidate.skills.map((s, idx) => (
                                <span key={idx} style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', color: 'hsl(var(--text-primary))', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.08)' }}>{s}</span>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <Briefcase size={14} style={{ color: 'hsl(var(--accent-cyan))' }} /> Work History
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                              {selectedCandidate.work_history.map((job, idx) => (
                                <div key={idx} style={{ padding: '0.6rem 0.8rem', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '2px solid rgba(255,255,255,0.1)', fontSize: '0.8rem', color: 'hsl(var(--text-secondary))', lineHeight: 1.4 }}>
                                  {job}
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 style={{ fontSize: '0.9rem', color: 'white', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <Calendar size={14} style={{ color: 'hsl(var(--warning))' }} /> Education & Credentials
                            </h4>
                            <ul style={{ listStyleType: 'disc', paddingLeft: '1.2rem', color: 'hsl(var(--text-secondary))', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                              {selectedCandidate.education.map((edu, idx) => (
                                <li key={idx}>{edu}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'hsl(var(--text-muted))' }}>
                    <FileText size={48} />
                    <p style={{ marginTop: '1rem', fontSize: '0.95rem' }}>Select a candidate to view assessment details</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
