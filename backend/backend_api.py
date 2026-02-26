from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import shutil

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend_full_pipeline import ResumeScreeningAI
from backend_step4_email import EmailSender

app = FastAPI(title="Resume Screening AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploaded_resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pipeline: ResumeScreeningAI | None = None
jd_locked = False
active_session_id = None

email_sender = EmailSender()

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {"status": "Resume Screening AI Backend running"}


# =====================================================
# SET JD (SESSION CONSISTENT)
# =====================================================
@app.post("/set_jd")
async def set_jd(
    jd_text: str = Form(...),
    session_id: str | None = Form(None),
):
    global pipeline, jd_locked, active_session_id

    # 🔥 If frontend did not send session → generate one
    if not session_id:
        session_id = str(uuid.uuid4())

    # If JD already locked for same session
    if jd_locked and session_id == active_session_id:
        return {
            "message": "JD already set",
            "session_id": active_session_id,
        }

    # If new session → hard reset first
    if session_id != active_session_id:
        _hard_reset()

    active_session_id = session_id
    jd_locked = True

    pipeline = ResumeScreeningAI(
        jd_text=jd_text,
        resume_folder=UPLOAD_FOLDER,
        sender_email=None,
        sender_password=None,
    )

    print("✅ JD SET — session:", active_session_id)

    return {
        "message": "JD set successfully",
        "session_id": active_session_id,
    }



# =====================================================
# UPLOAD RESUME
# =====================================================

@app.post("/upload_resume")
async def upload_resume(
    session_id: str = Form(...),
    file: UploadFile = File(...)
):
    global pipeline, active_session_id

    if pipeline is None or not jd_locked:
        raise HTTPException(status_code=400, detail="Set JD first")

    if session_id != active_session_id:
        raise HTTPException(status_code=400, detail="Invalid session")

    # Prevent duplicate upload by filename
    existing_files = os.listdir(UPLOAD_FOLDER)
    if file.filename in existing_files:
        return {"message": "File already uploaded"}

    path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    pipeline.refresh_resumes()

    return {"message": "Resume uploaded successfully"}


# =====================================================
# RANKED CANDIDATES
# =====================================================

@app.get("/ranked_candidates")
def get_ranked_candidates(session_id: str):
    global pipeline, active_session_id

    if pipeline is None:
        raise HTTPException(status_code=400, detail="Set JD first")

    if session_id != active_session_id:
        raise HTTPException(status_code=400, detail="Invalid session")

    df = pipeline.rank_resumes()
    return df.to_dict(orient="records")


# =====================================================
# SEND EMAIL
# =====================================================

@app.post("/send_email")
async def send_email_endpoint(
    email: str = Form(...),
    name: str = Form(...),
    decision: str = Form(...)
):
    success, message = email_sender.send_email(
        email,
        name,
        decision
    )

    return {
        "success": success,
        "message": message
    }


# =====================================================
# CHAT
# =====================================================

@app.api_route("/rag_query", methods=["GET", "POST"])
async def rag_query(
    query: str,
    session_id: str,
    top_k: int = 5,
    query_type: str | None = None,
):
    global pipeline, active_session_id

    if session_id != active_session_id:
        raise HTTPException(status_code=400, detail="Invalid session")

    if pipeline is None:
        raise HTTPException(status_code=400, detail="Pipeline not ready")

    response = pipeline.ask_chatbot(query, top_k)
    return {"response": response}



# =====================================================
# RESET SESSION (MATCH FRONTEND)
# =====================================================

@app.post("/reset")
def reset_system():
    _hard_reset()
    return {"message": "System reset successful"}


# =====================================================
# HARD RESET FUNCTION
# =====================================================

def _hard_reset():
    global pipeline, jd_locked, active_session_id

    pipeline = None
    jd_locked = False
    active_session_id = None

    for f in os.listdir(UPLOAD_FOLDER):
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, f))
        except:
            pass
