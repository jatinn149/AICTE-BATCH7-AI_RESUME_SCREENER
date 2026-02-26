# 🚀 Resume Screening AI

An intelligent ATS-style resume screening system that automatically evaluates and ranks candidates based on job description relevance.  
Built to simulate real-world recruiter workflows with semantic matching, structured parsing, and AI-powered insights.

---

## ✨ Key Features

🔹 Automated Job Description structuring  
🔹 Hybrid resume parsing (text + OCR fallback)  
🔹 ATS-style candidate ranking engine  
🔹 Semantic similarity matching using transformers  
🔹 Recruiter copilot chatbot (RAG-based)  
🔹 One-click candidate email notification  
🔹 Session-safe FastAPI backend  

The system is designed for **speed, accuracy, and production readiness**.

---

## 🧠 How It Works

The pipeline follows a multi-stage intelligent flow:

1️⃣ Job Description is structured into skills and requirements  
2️⃣ Resumes are parsed and normalized  
3️⃣ Embeddings are generated using MiniLM  
4️⃣ Candidates are ranked using a weighted scoring engine  
5️⃣ Recruiters can query insights via RAG chatbot  
6️⃣ Decision emails can be sent automatically  

This ensures recruiter-grade evaluation rather than simple keyword matching.

---

## 🛠 Tech Stack

**Backend:** FastAPI, Python  
**AI/NLP:** Sentence Transformers, FAISS  
**Parsing:** PyMuPDF, Tesseract OCR  
**LLM Integration:** Groq (LLaMA 3.3)  
**Email Service:** SMTP automation  

---

## 📂 Project Structure
resume-screener/
├── backend/
├── frontend/
├── uploaded_resumes/
└── README.md


---

## ▶️ Running the Project

### Backend

cd backend
pip install -r requirements.txt
uvicorn backend_api:app --reload

### Frontend

cd frontend
npm install
npm start
