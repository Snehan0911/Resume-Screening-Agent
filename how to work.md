The Challenge
You have 24 hours to design, build, and ship a working AI agent.

Choose any one of the twelve agents listed in this document.

We care about a functioning end-to-end agent, clear thinking, and honest engineering—not polish.

Use any language, framework, model, or API you like.

---

How It Works
Pick your agent
Select one of the 12 agents.
Read its expected capabilities and deliverables carefully.
Plan & scope (first 2–3 hrs)
Decide your approach, data, and model.
Scope to what you can finish and demo in 24 hours.
Build the agent
Implement a working, runnable agent.
Commit early and often to your public repository.
Document & test
Write a clear README.
Add sample inputs/outputs.
Note your design tradeoffs.
Submit
Share your public GitHub URL before the 24-hour deadline.
Late commits are not evaluated.
Review
We run your agent from your README.
Your submission is scored using the universal rubric below.
---

What Is an "AI Agent"? (Start Here)
An AI agent is a small program that:

Takes an input from a user.
Uses an AI language model (like GPT or Claude) to understand and think about it.
Optionally looks something up or performs an action (reads a document, saves to a database, checks a calendar).
Returns a useful output.
That's it.

You are writing the "glue" code around an AI model so it can do one specific job well.

A recommended, beginner-friendly setup
Language: Python (easiest for beginners and for AI)
The brain: An LLM API (OpenAI, Anthropic Claude, or a free model via Groq/Ollama)
Your instructions: A system prompt describing the AI's job and rules
Tools (if needed): Python functions to read files, save records, search, etc.
Storage (if needed): SQLite, JSON, or CSV
Run it: A command-line script is perfectly fine. A UI is optional.
---

How to Build Your Agent — Step by Step
Follow these six steps in order.

Each one is small.

By the end you'll have a working agent.

---

STEP 1
Understand the one job
Re-read your chosen agent's Expected Capabilities.

Write one sentence:

> "My agent takes _____ and produces _____."

If you can't fill that in, you're not ready to code yet.

Example
> "My HR agent takes an employee question and produces an answer based on the company policy PDF."

---

STEP 2
Get access to an AI model
Sign up for an LLM API (OpenAI, Anthropic, or a free option like Groq).
Get an API key.
Install the Python SDK using pip.
Send one test message.
Verify you receive a response.
If you get a reply printed to your screen, the hardest setup is already done.

---

STEP 3
Write the system prompt (the agent's instructions)
In plain English, tell the model:

Who it is.
What its job is.
What rules it should follow.
Most of your agent's intelligence comes from this prompt—no machine learning training required.

Example
> "You are an HR assistant. Answer only using the policy text provided. If the answer isn't there, say you don't know."

---

STEP 4
Add data or tools if your agent needs them
Does your agent need to:

Read documents?
Save data?
Check a calendar?
Write small Python functions for those tasks.

For document-answering agents:

Load the text.
Include the relevant parts inside the prompt (RAG — Retrieval-Augmented Generation).
For agents that store things:

Use a simple database.
Keep it simple.

Reading a PDF and pasting the text into the prompt counts.

---

STEP 5
Connect it into a loop
Wire everything together.

User Input

↓

Fetch any needed data

↓

Send prompt + context to the AI model

↓

Receive answer

↓

Display the answer

↓

(Optional) Save the result

A simple loop that repeatedly asks:

> "What's your question?"

is enough.

This Input → Think → Act → Output cycle is your AI agent.

STEP 6
Test, then write the README
Run your agent with 5–10 real examples and save the results.

Then write a README that tells us:

Exactly how to install the project
How to configure API keys
How to run the agent end to end
The design choices you made
Any tradeoffs or limitations
If a stranger can run your project from the README, you're done.

> Reviewers score what they can actually run. Make setup foolproof.

---

What to Submit (All Agents)
Every submission must include:

Public GitHub repository URL — all code committed within the 24-hour window
README with setup instructions — how to install, configure keys, and run the agent end to end
A runnable agent — scripts or app that reviewers can execute by following the README
Sample inputs and outputs — enough for reviewers to reproduce a working demo (data, transcripts, or screenshots)
Tradeoff notes — a short section explaining your model/approach choices and what you'd improve with more time
Agent-specific deliverables — as listed for your chosen agent
---

Ground Rules
Work individually unless told otherwise.
Use of AI coding assistants, open-source models, and public APIs is encouraged.
The design decisions and integration must be your own.
You must be able to explain every part of your code.
A UI is welcome but not required.
A clean backend or CLI that clearly demonstrates the agent is enough.
---

Scoring (out of 100)
Working end-to-end resume screening agent: 30
Approach, NLP similarity method, and model choice: 25
Code quality and organization: 20
README clarity and reproducibility: 15
Tradeoff notes and reasoning: 10
The same rubric applies to every agent, so choose the one that best shows your strengths.

Functionality is judged against that agent's expected capabilities.

---

The 12 Agents — Pick One
Each agent below lists:

Difficulty
Expected capabilities
Agent-specific deliverables
Choose whichever best shows your strengths.

An excellent Beginner build scores just as well as an Advanced build.

Difficulty Guide
Beginner — Great first agent
Intermediate — Some logic or data handling
Advanced — Real computation or multi-step work
---

CATEGORY 1 — HR & Recruitment
Resume Screening Agent (Intermediate)
Ranks a set of resumes against a given job description and outputs an ordered shortlist.

Expected Capabilities
Parse resumes (PDF/DOCX/Text) and extract skills, experience, and education
Compute a relevance score against the Job Description using NLP similarity
Rank candidates and output a scored, ordered list with reasoning
Handle 10+ resumes in a single run
Agent-Specific Deliverables
A Job Description (JD)
A folder of sample resumes
Ranked output (CSV/JSON)
A note explaining the scoring method
---

Interview Agent (Intermediate)
Conducts a structured Q&A, asks role-relevant questions, and evaluates the candidate's answers.

Expected Capabilities
Generate role-specific interview questions from a role/skill input
Accept candidate answers (typed or transcribed) and score each
Produce an overall evaluation with strengths and gaps
Support at least 5 questions in a session
Agent-Specific Deliverables
A transcript of one full mock interview
Scores for each question
Final evaluation summary
---

Course Recommendation Agent (Beginner)
Suggests a personalised learning path from a student's background, goals, and current skills.

Expected Capabilities
Take a student profile (background, goals, known skills) as input
Model a small catalogue of courses/skills with prerequisites
Recommend an ordered learning path with reasons for each step
Explain why each course was chosen
Agent-Specific Deliverables
A course catalogue
3–4 sample student profiles
Recommended learning paths
Rationale for every recommendation
CATEGORY 2 — Data & Documents
Document Data Extractor (Advanced)
Pulls structured fields from messy documents (invoices, receipts, purchase orders) into clean JSON.

Expected Capabilities
Read a document (PDF/Image/Text) and extract key fields (dates, amounts, line items, IDs)
Output validated, well-structured JSON
Add sanity checks (e.g., line items sum to the total; dates are valid)
Handle at least two different document layouts
Agent-Specific Deliverables
Sample documents with varied layouts
Extracted JSON for each document
A note explaining validation logic and known failure cases
---

CSV / Data Q&A Agent (Advanced)
Answers plain-English questions about a spreadsheet by actually computing over the data.

Expected Capabilities
Load a CSV/Excel file and understand its columns
Answer questions like "Which region grew fastest last quarter?" with correct numbers
Use real computation (not guesses), such as generating and running code or querying the data
Show the figure or table behind each answer
Agent-Specific Deliverables
A sample dataset
8–10 questions with the agent's answers
A note explaining how numbers are computed (to avoid hallucination)
---

Meeting Notes to Action Items (Intermediate)
Turns a meeting transcript into a clean summary plus assigned, dated action items.

Expected Capabilities
Accept a transcript (text) as input
Produce a concise structured summary of decisions and discussion
Extract action items with owner and due date where stated
Output in a structured format (JSON/Table)
Agent-Specific Deliverables
A sample meeting transcript
Generated meeting summary
Structured action-item list
---

CATEGORY 3 — Customer & Growth
Product Recommendation Agent (Intermediate)
Suggests products to a user based on their stated preferences and behaviour.

Expected Capabilities
Model a product catalogue with attributes
Take user preferences and return ranked recommendations with reasons
Use a sensible similarity or filtering approach (content-based is fine)
Handle cold-start (no history) gracefully
Agent-Specific Deliverables
Product catalogue
3–4 sample user profiles
Recommendation output
Rationale for every recommendation
---

Social Media Agent (Beginner)
Generates content ideas, daily captions, and a posting plan for a brand.

Expected Capabilities
Take a brand brief (voice, audience, themes) as input
Generate a week of content ideas with captions and hashtags
Produce a structured posting calendar (day/time/platform)
Keep output on-brand and non-repetitive
Agent-Specific Deliverables
Brand brief
Generated 7-day content calendar
Sample captions
---

Lead Qualification Agent (Intermediate)
Scores and summarises inbound leads so a sales team knows who to call first.

Expected Capabilities
Take lead details (form data, notes, or email text) as input
Score each lead on fit and intent with a clear rationale
Classify leads into tiers (Hot / Warm / Cold) with a suggested next action
Output a ranked, summarised lead list
Agent-Specific Deliverables
A set of sample leads
Scored and ranked output
A note explaining the scoring logic
CATEGORY 4 — Voice & Agentic
Reception (Voice) Agent (Intermediate)
Answers voice calls, converts speech to text, and stores structured call records in a database.

Expected Capabilities
Accept an audio input (file or microphone) and transcribe it to text
Extract key fields (caller intent, caller name, callback number if present)
Store each call as a structured record in a database (SQLite is sufficient)
Retrieve and list stored calls
Agent-Specific Deliverables
Sample audio clips
Populated database
A query demonstrating the stored call records
---

Support Ticket Triage Agent (Intermediate)
Classifies incoming support tickets by category and urgency, then routes them.

Expected Capabilities
Take a support ticket (subject + body) as input
Classify each ticket by category and urgency with a confidence score
Decide routing (which team) and flag "unsure" cases for human review
Process a batch of tickets and output the routing decisions
Agent-Specific Deliverables
A set of sample support tickets
Classified and routed output
A note explaining the decision boundary
---

Research Agent (with Citations) (Advanced)
Takes a question, reads provided sources (or searches), and returns a cited summary.

Expected Capabilities
Accept a question and a set of source documents (or a search tool)
Retrieve the relevant passages and synthesise an answer
Cite which source each claim came from
Clearly state when the provided sources do not contain the answer
Agent-Specific Deliverables
A question set
Source documents
Cited answers
A note explaining the retrieval/tool approach
---

Tips to Score Well
Ship something that runs. A small working agent beats an ambitious broken one. Get the end-to-end workflow working first, then improve it.
Make setup foolproof. Pin dependencies, document environment variables, and include sample data so reviewers can run your project in minutes.
Show your reasoning. The tradeoff notes are easy points and help reviewers understand how you think.
Be honest about limitations. Clearly stating what doesn't work yet scores better than trying to hide it.
Commit throughout the challenge. A steady commit history within the 24-hour window demonstrates genuine work completed during the challenge.
------
