from dotenv import load_dotenv
load_dotenv()

import os
import shutil
import re
import datetime
from typing import Any
from pydantic import BaseModel, Field, validator

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from backend_full_pipeline import ResumeScreeningAI
from backend_step4_email import EmailSender
from email_queue import EmailTaskQueue
from session_manager import SessionManager
from contextlib import asynccontextmanager

# =====================================================
# VALIDATION MODELS
# =====================================================

class SetJDRequest(BaseModel):
    jd_text: str = Field(..., min_length=50, max_length=50000)
    session_id: str = None
    
    @validator('jd_text')
    def validate_jd_quality(cls, v):
        """Ensure JD has minimum quality (not just spaces)"""
        if len(v.strip()) < 50:
            raise ValueError("JD must be at least 50 characters (non-whitespace)")
        if len(v.split()) < 10:
            raise ValueError("JD must have at least 10 words")
        return v

class SendEmailRequest(BaseModel):
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    name: str = Field(..., min_length=1, max_length=200)
    decision: str = Field(..., pattern='^(confirm|reject)$')
    
    @validator('email')
    def validate_email_format(cls, v):
        if len(v) > 254:
            raise ValueError("Email too long")
        return v.lower()

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    session_id: str = Field(...)
    top_k: int = Field(5, ge=1, le=20)
    query_type: str = None

# =====================================================
# CONFIGURATION CONSTANTS
# =====================================================
MAX_FILE_SIZE_MB = 10  # 10MB per resume
MAX_SESSION_DURATION_HOURS = 24
ALLOWED_EXTENSIONS = {'.pdf'}
MAX_JD_LENGTH = 50000
MIN_JD_LENGTH = 50
MIN_JD_WORDS = 10
MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 1000
MIN_TOP_K = 1
MAX_TOP_K = 50
MAX_CHAT_HISTORY_ITEMS = 8
MAX_CHAT_MESSAGE_LENGTH = 1200
VALID_DECISIONS = {"confirm", "reject"}
VALID_QUERY_TYPES = {"meta", "aggregation", "content"}
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
EMAIL_PATTERN = re.compile(EMAIL_REGEX)
VALID_CHAT_ROLES = {"user", "assistant"}
TRANSIENT_EMAIL_ERROR_CODES = {"connection_error", "smtp_error", "auth_failed"}

UPLOAD_FOLDER = "uploaded_resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Replace global state with SessionManager
session_manager = SessionManager()

# Keep email sender at global level (stateless)
email_sender = EmailSender()
email_queue = EmailTaskQueue()  # Initialize retry queue


# =====================================================
# INTERNAL HELPERS
# =====================================================

def _validate_jd_text_or_raise(jd_text: str) -> None:
    if not jd_text or len(jd_text.strip()) < MIN_JD_LENGTH:
        raise HTTPException(status_code=400, detail="JD must be at least 50 characters")
    if len(jd_text) > MAX_JD_LENGTH:
        raise HTTPException(status_code=413, detail="JD too long (max 50KB)")
    if len(jd_text.split()) < MIN_JD_WORDS:
        raise HTTPException(status_code=400, detail="JD must have at least 10 words")


def _resolve_or_create_session(session_id: str | None) -> tuple[str, Any]:
    if not session_id:
        session_id = session_manager.create_session()
    else:
        is_valid, _ = session_manager.validate_session(session_id)
        if not is_valid:
            session_id = session_manager.create_session()

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Failed to create session")

    return session_id, session


def _set_session_jd_with_recovery(session_id: str, session: Any, jd_text: str) -> None:
    success, _ = session_manager.set_jd(session_id, jd_text)
    if success:
        return

    if session.jd_text == jd_text:
        return

    session_manager.reset_session(session_id)
    session_manager.set_jd(session_id, jd_text)


def _build_pipeline_for_jd(jd_text: str) -> ResumeScreeningAI:
    return ResumeScreeningAI(
        jd_text=jd_text,
        resume_folder=UPLOAD_FOLDER,
        sender_email=None,
        sender_password=None,
    )


def _validate_active_session_or_raise(session_id: str) -> None:
    is_valid, _ = session_manager.validate_session(session_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired session")


def _get_pipeline_or_raise(session_id: str) -> ResumeScreeningAI:
    pipeline = session_manager.get_pipeline(session_id)
    if pipeline is None:
        raise HTTPException(status_code=400, detail="Set JD first")
    return pipeline


def _validate_upload_file_or_raise(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Only PDF files allowed, got {file_ext}")


def _validate_upload_file_size_or_raise(file: UploadFile) -> None:
    try:
        current_pos = file.file.tell()
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(current_pos)

        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_FILE_SIZE_MB}MB)")
        if file_size < 1000:
            raise HTTPException(status_code=400, detail="File too small or corrupted")
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[FILE SIZE CHECK] Could not verify size: {exc}")


def _check_duplicate_upload(filename: str, resume_count: int) -> dict[str, Any] | None:
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return {
            "message": "File already uploaded",
            "is_duplicate": True,
            "resume_count": resume_count,
        }
    return None


def _save_uploaded_file_or_raise(file: UploadFile, path: str) -> None:
    try:
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(exc)}")


def _build_resume_payload(parser: Any, filename: str, text: str) -> dict[str, Any]:
    email = parser._extract_email(text)
    name = parser._extract_name(filename, text)
    experience = parser._extract_experience(text)
    skills = parser._extract_skills(text)

    base_resume = {
        "name": name,
        "email": email,
        "experience_years": experience,
        "skills": skills,
        "text": text,
    }

    if parser._is_weak_resume(text, skills, experience):
        print(f"[UPLOAD] Weak resume detected for {filename} -> using LLM")
        llm_data = parser._llm_structured_parse(text, filename)
        if llm_data:
            return {
                **base_resume,
                "name": llm_data.get("name", name),
                "email": llm_data.get("email", email),
                "experience_years": llm_data.get("experience_years", experience),
                "skills": llm_data.get("skills", skills),
                "projects_text": llm_data.get("projects_text", ""),
                "education_text": llm_data.get("education_text", ""),
                "degree_level": llm_data.get("degree_level", "unknown"),
            }

    return {
        **base_resume,
        "projects_text": parser._extract_projects(text),
        "education_text": parser._extract_education(text),
        "degree_level": "unknown",
    }


def _parse_resume_file_or_raise(pipeline: ResumeScreeningAI, path: str, filename: str) -> dict[str, Any]:
    parser = pipeline.parser
    text = parser._extract_text(path)

    if not text.strip():
        os.remove(path)
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    return _build_resume_payload(parser, filename, text)


def _validate_email_inputs_or_raise(email: str, name: str, decision: str) -> tuple[str, str, str]:
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(email) > 254:
        raise HTTPException(status_code=400, detail="Email too long")

    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) < 1:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if len(normalized_name) > 200:
        raise HTTPException(status_code=400, detail="Name too long (max 200 chars)")

    if decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail="Decision must be 'confirm' or 'reject'")

    return email.lower(), normalized_name, decision


def _parse_rag_post_body(body: Any, query: str | None, session_id: str | None, top_k: int, query_type: str | None) -> tuple[str | None, str | None, Any, str | None, list[Any]]:
    if not isinstance(body, dict):
        return query, session_id, top_k, query_type, []

    return (
        body.get("query", query),
        body.get("session_id", session_id),
        body.get("top_k", top_k),
        body.get("query_type", query_type),
        body.get("chat_history", []),
    )


def _normalize_rag_inputs(query: str | None, session_id: str | None) -> tuple[str, str]:
    return (query or "").strip(), (session_id or "").strip()


def _validate_rag_query_or_raise(query: str) -> None:
    if not query or len(query.strip()) < MIN_QUERY_LENGTH:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 chars)")


def _parse_top_k_or_raise(top_k: Any) -> int:
    try:
        parsed_top_k = int(top_k)
    except Exception:
        raise HTTPException(status_code=400, detail="top_k must be an integer")

    if parsed_top_k < MIN_TOP_K or parsed_top_k > MAX_TOP_K:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 50")

    return parsed_top_k


def _validate_query_type_or_raise(query_type: str | None) -> None:
    if query_type and query_type not in VALID_QUERY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid query_type")


def _sanitize_chat_history(chat_history: Any) -> list[dict[str, str]]:
    if not isinstance(chat_history, list):
        return []

    sanitized_history = []
    for item in chat_history[-MAX_CHAT_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in VALID_CHAT_ROLES and content:
            sanitized_history.append({"role": role, "content": content[:MAX_CHAT_MESSAGE_LENGTH]})
    return sanitized_history


def _cleanup_upload_folder() -> None:
    for dir_entry in os.scandir(UPLOAD_FOLDER):
        try:
            if dir_entry.is_file():
                os.remove(dir_entry.path)
        except Exception:
            pass


# =====================================================
# LIFESPAN EVENTS (Startup/Shutdown)
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle - startup and shutdown."""
    # STARTUP
    print("[STARTUP] Starting background services...")
    email_queue.start_worker(email_sender)
    print("[STARTUP] All services started ✅")
    
    yield
    
    # SHUTDOWN
    print("[SHUTDOWN] Stopping background services...")
    email_queue.stop_worker()
    print("[SHUTDOWN] All services stopped ✅")

app = FastAPI(
    title="Resume Screening AI Backend",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    _validate_jd_text_or_raise(jd_text)

    try:
        session_id, session = _resolve_or_create_session(session_id)
        _set_session_jd_with_recovery(session_id, session, jd_text)
        pipeline = _build_pipeline_for_jd(jd_text)

        session_manager.set_pipeline(session_id, pipeline)

        print(f"✅ JD SET — session: {session_id}")

        return {
            "message": "JD set successfully",
            "session_id": session_id,
        }
    
    except Exception as e:
        print(f"[SET_JD ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set JD: {str(e)}")



# =====================================================
# UPLOAD RESUME (IMPROVED WITH INCREMENTAL LOGIC)
# =====================================================

@app.post("/upload_resume")
async def upload_resume(
    session_id: str = Form(...),
    file: UploadFile = File(...)
):
    _validate_active_session_or_raise(session_id)
    pipeline = _get_pipeline_or_raise(session_id)

    _validate_upload_file_or_raise(file)
    _validate_upload_file_size_or_raise(file)

    count_before = len(pipeline.parsed_resumes)

    duplicate_result = _check_duplicate_upload(file.filename, count_before)
    if duplicate_result:
        return duplicate_result

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    _save_uploaded_file_or_raise(file, path)

    try:
        new_resume = _parse_resume_file_or_raise(pipeline, path, file.filename)
        success = pipeline.add_resume_incrementally(new_resume)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to process resume")

        count_after = len(pipeline.parsed_resumes)

        return {
            "message": "Resume uploaded and processed successfully",
            "is_duplicate": False,
            "resume_name": new_resume.get("name", "Unknown"),
            "resume_email": new_resume.get("email", "N/A"),
            "resume_count": count_after,
            "total_skills_found": len(new_resume.get("skills", [])),
            "experience_years": new_resume.get("experience_years", 0)
        }

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[UPLOAD ERROR] {file.filename}: {str(exc)}")
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(exc)}")


# =====================================================
# RANKED CANDIDATES
# =====================================================

@app.get("/ranked_candidates")
def get_ranked_candidates(session_id: str):
    _validate_active_session_or_raise(session_id)
    pipeline = _get_pipeline_or_raise(session_id)

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
    email, name, decision = _validate_email_inputs_or_raise(email, name, decision)

    try:
        success, message, error_code = email_sender.send_email(
            email,
            name,
            decision
        )

        if success:
            return {
                "success": True,
                "message": message,
                "queued": False
            }
        else:
            # Try to queue for retry if it's a transient error
            if error_code in TRANSIENT_EMAIL_ERROR_CODES:
                task_id = email_queue.queue_email(
                    email,
                    name,
                    decision
                )
                return {
                    "success": False,
                    "message": f"{message} (Queued for retry: {task_id})",
                    "queued": True,
                    "task_id": task_id
                }
            else:
                # Permanent error
                raise HTTPException(status_code=400, detail=message)
                
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[EMAIL ENDPOINT ERROR] {str(exc)}")
        raise HTTPException(status_code=500, detail=f"Email service error: {str(exc)}")


# =====================================================
# CHAT
# =====================================================

@app.api_route("/rag_query", methods=["GET", "POST"])
async def rag_query(
    request: Request,
    query: str | None = None,
    session_id: str | None = None,
    top_k: int = 5,
    query_type: str | None = None,
):
    chat_history: list[Any] = []

    if request.method == "POST":
        try:
            body = await request.json()
            query, session_id, top_k, query_type, chat_history = _parse_rag_post_body(
                body, query, session_id, top_k, query_type
            )
        except Exception:
            chat_history = []

    query, session_id = _normalize_rag_inputs(query, session_id)

    _validate_active_session_or_raise(session_id)
    pipeline = _get_pipeline_or_raise(session_id)

    _validate_rag_query_or_raise(query)
    top_k = _parse_top_k_or_raise(top_k)
    _validate_query_type_or_raise(query_type)
    sanitized_history = _sanitize_chat_history(chat_history)

    try:
        response = pipeline.ask_chatbot(
            query,
            top_k=top_k,
            chat_history=sanitized_history,
            query_type=query_type,
        )
        return {"response": response}
    except Exception as exc:
        print(f"[RAG ERROR] {str(exc)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(exc)}")



# =====================================================
# RESET SESSION (MATCH FRONTEND)
# =====================================================

@app.post("/reset")
def reset_system(session_id: str = None):
    if session_id:
        # Clean up specific session
        session_manager.cleanup_session(session_id)
        return {"message": "Session reset successful"}
    else:
        # Backward compatibility - hard reset
        _hard_reset()
        return {"message": "System reset successful"}


# =====================================================
# HARD RESET FUNCTION
# =====================================================

def _hard_reset():
    session_manager.cleanup_all_sessions()
    _cleanup_upload_folder()


# =====================================================
# SYSTEM MONITORING & ADMIN (for debugging/health)
# =====================================================

@app.get("/system/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


@app.get("/system/status")
def system_status():
    """Get comprehensive system status."""
    return {
        "uptime_seconds": (datetime.datetime.utcnow() - datetime.datetime.utcnow()).total_seconds(),
        "sessions": {
            "active": session_manager.get_active_sessions_count(),
            "stats": session_manager.get_stats()
        },
        "email_queue": {
            "pending_tasks": len(email_queue.get_pending_tasks()),
            "worker_running": email_queue.running
        },
        "upload_folder": {
            "file_count": len(os.listdir(UPLOAD_FOLDER)) if os.path.exists(UPLOAD_FOLDER) else 0,
            "path": UPLOAD_FOLDER
        }
    }


@app.get("/system/email_queue")
def get_email_queue_status():
    """Get detailed email queue status."""
    pending = email_queue.get_pending_tasks()
    
    return {
        "worker_running": email_queue.running,
        "pending_count": len(pending),
        "max_retries": email_queue.max_retries,
        "retry_delay_minutes": email_queue.retry_delay_minutes,
        "pending_tasks": [
            {
                "id": task["id"],
                "to_email": task["to_email"],
                "candidate_name": task["candidate_name"],
                "decision": task["decision"],
                "retry_count": task.get("retry_count", 0),
                "created_at": task.get("created_at"),
                "last_error": task.get("last_error"),
            }
            for _, task in pending
        ]
    }


@app.get("/system/sessions")
def get_sessions():
    """Get active sessions info."""
    return session_manager.get_stats()


@app.post("/system/email_queue/retry_now")
def force_email_queue_retry():
    """Force immediate processing of email queue (for testing)."""
    if not email_queue.running:
        return {
            "error": "Email worker not running",
            "status": "failed"
        }
    
    # Trigger immediate check by processing pending tasks
    pending = email_queue.get_pending_tasks()
    
    if not pending:
        return {
            "message": "No pending tasks in queue",
            "status": "ok"
        }
    
    return {
        "message": f"Triggered processing of {len(pending)} pending tasks",
        "status": "ok",
        "task_ids": [task["id"] for _, task in pending]
    }
