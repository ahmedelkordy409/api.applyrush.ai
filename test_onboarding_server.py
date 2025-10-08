"""
Simple FastAPI server to test onboarding endpoints
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import uvicorn
from datetime import datetime
import secrets
import string

app = FastAPI(title="Onboarding Test Server", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory storage for testing
guest_sessions = {}
guest_answers = {}

def generate_session_id() -> str:
    """Generate a unique session ID"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

@app.post("/api/onboarding/guest/create")
async def create_guest_session(request: Dict[str, Any] = None):
    """Create a new guest session"""
    try:
        session_id = generate_session_id()
        created_at = datetime.utcnow().isoformat()
        expires_at = datetime.utcnow().replace(hour=23, minute=59, second=59).isoformat()

        session_data = {
            "session_id": session_id,
            "created_at": created_at,
            "expires_at": expires_at,
            "status": "in_progress",
            "current_step": 0,
            "completed_steps": [],
            "answers": {},
            "referrer": request.get("referrer") if request else None,
            "utm_source": request.get("utm_source") if request else None,
            "utm_medium": request.get("utm_medium") if request else None,
            "utm_campaign": request.get("utm_campaign") if request else None,
        }

        guest_sessions[session_id] = session_data
        guest_answers[session_id] = {}

        return {
            "session_id": session_id,
            "created_at": created_at,
            "expires_at": expires_at,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@app.post("/api/onboarding/guest/answer")
async def save_guest_answer(request: Dict[str, Any]):
    """Save an answer for a guest session"""
    try:
        session_id = request.get("session_id")
        step_id = request.get("step_id")
        answer = request.get("answer")
        time_spent_seconds = request.get("time_spent_seconds", 0)

        if not session_id or not step_id:
            raise HTTPException(status_code=400, detail="session_id and step_id are required")

        if session_id not in guest_sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        # Store the answer
        if session_id not in guest_answers:
            guest_answers[session_id] = {}

        guest_answers[session_id][step_id] = {
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat(),
            "time_spent_seconds": time_spent_seconds
        }

        # Update session data
        session = guest_sessions[session_id]
        session["answers"][step_id] = answer

        if step_id not in session["completed_steps"]:
            session["completed_steps"].append(step_id)

        # Update current step
        session["current_step"] = len(session["completed_steps"])

        # Special handling for email collection
        if step_id == "email-collection" and answer and answer.get("email"):
            session["status"] = "email_provided"
            session["email"] = answer.get("email")

        print(f"💾 Saved answer for session {session_id}, step {step_id}: {answer}")

        return {
            "success": True,
            "step_id": step_id,
            "current_step": session["current_step"],
            "completed_steps": session["completed_steps"],
            "status": session["status"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error saving answer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save answer: {str(e)}")

@app.get("/api/onboarding/guest/{session_id}")
async def get_guest_session(session_id: str):
    """Get guest session data"""
    if session_id not in guest_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return guest_sessions[session_id]

@app.get("/api/onboarding/guest/{session_id}/answers")
async def get_guest_answers(session_id: str):
    """Get all answers for a guest session"""
    if session_id not in guest_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return guest_answers.get(session_id, {})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(guest_sessions)
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Onboarding Test Server",
        "endpoints": [
            "POST /api/onboarding/guest/create",
            "POST /api/onboarding/guest/answer",
            "GET /api/onboarding/guest/{session_id}",
            "GET /api/onboarding/guest/{session_id}/answers",
            "GET /health"
        ]
    }

if __name__ == "__main__":
    print("🚀 Starting Onboarding Test Server...")
    print("📍 Server will run at: http://localhost:8000")
    print("🔍 Health Check: http://localhost:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000)