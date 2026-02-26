# ⚡ Resume Screening AI — Frontend

A production-style React interface for the AI-powered Resume Screening System.  
This frontend enables recruiters to structure job descriptions, upload resumes, view ranked candidates, and interact with an AI hiring copilot — all within a clean, session-safe workflow.

Built using **React + Vite** for high performance and smooth user experience.

---

## ✨ Core Features

🔹 Job Description locking with session consistency  
🔹 Secure resume upload pipeline  
🔹 Live ATS-style candidate ranking table  
🔹 AI Recruiter Copilot (RAG chatbot)  
🔹 One-click system reset  
🔹 Real-time system status tracking (idle → processing → ready)  

The UI is designed to mimic **real recruiter workflows**, not just a demo interface.

---

## 🧠 Application Flow

The frontend follows a guarded multi-stage pipeline:

1️⃣ Recruiter sets the Job Description  
2️⃣ Backend session is generated and locked  
3️⃣ Resumes are uploaded under the active session  
4️⃣ Candidates are ranked automatically  
5️⃣ Recruiter queries insights via AI chatbot  
6️⃣ System can be safely reset anytime  

Session integrity is strictly maintained to prevent cross-session data leakage.

---

## 🛠 Tech Stack

- ⚛️ React (Vite)
- 🔗 Axios API integration
- 🎨 Modular component architecture
- 🤖 FastAPI backend connectivity

---

## ▶️ Running the Frontend

### Install dependencies

npm install

Start development server

npm run dev

App runs at:

http://localhost:5173
