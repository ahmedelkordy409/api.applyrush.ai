"""
Interview Management API endpoints
Handles AI-powered interview sessions, conversation, and evaluation
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, validator
import json
import logging

from app.core.database import database
from app.api.endpoints.auth import get_current_user
from app.core.security import PermissionChecker
from app.services.ai_client import get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter()
permission_checker = PermissionChecker()


class InterviewCreateRequest(BaseModel):
    workflow: Dict[str, Any]


class InterviewMessageRequest(BaseModel):
    interviewId: Optional[str] = None
    workflow: Optional[Dict[str, Any]] = None
    userMessage: Optional[str] = None


class InterviewResponse(BaseModel):
    assistant: str
    interviewId: str
    done: bool
    evaluation: Optional[Dict[str, Any]] = None
    current_stage: int
    current_question: int


class InterviewListItem(BaseModel):
    id: str
    workflow_type: str
    status: str
    current_stage: int
    current_question: int
    created_at: datetime
    updated_at: datetime
    evaluation: Optional[Dict[str, Any]] = None


def get_enterprise_system_prompt(company_name: Optional[str] = None) -> str:
    """Get the system prompt for the AI interviewer"""
    company_part = f" at {company_name}" if company_name else ""

    return f"""You are an expert AI interviewer{company_part}. Your role is to conduct professional, structured interviews based on the provided workflow JSON.

CORE RESPONSIBILITIES:
1. Follow the interview workflow stages and questions exactly as provided
2. Ask questions one at a time in the specified order
3. Provide constructive feedback and follow-up questions
4. Maintain a professional, encouraging tone
5. Evaluate candidate responses objectively

WORKFLOW INSTRUCTIONS:
- The WORKFLOW_JSON contains stages with questions
- Progress through stages and questions systematically
- When you reach the end of all stages/questions, conclude with "Interview complete" followed by a JSON evaluation

EVALUATION FORMAT (when interview is complete):
Interview complete
{{
  "overall_score": 85,
  "strengths": ["Strong technical knowledge", "Good communication"],
  "areas_for_improvement": ["Could elaborate more on examples"],
  "recommendation": "Strong candidate, recommend for next round",
  "detailed_scores": {{
    "technical_skills": 90,
    "communication": 80,
    "problem_solving": 85,
    "cultural_fit": 80
  }}
}}

GUIDELINES:
- Keep responses concise but thorough
- Provide specific feedback on answers
- Ask follow-up questions when appropriate
- Be encouraging but honest in assessment
- Stay within the 800 token limit for responses"""


def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON text, returning None if invalid"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


@router.post("/", response_model=InterviewResponse)
async def conduct_interview(
    request: InterviewMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Conduct an interview session with AI"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to conduct interviews"
            )

        interview = None
        interview_id = request.interviewId

        # Get or create interview
        if interview_id:
            # Get existing interview
            query = """
                SELECT id, user_id, workflow, current_stage, current_question, status, created_at, updated_at
                FROM interviews
                WHERE id = :interview_id AND user_id = :user_id
            """
            interview = await database.fetch_one(
                query=query,
                values={"interview_id": interview_id, "user_id": current_user["id"]}
            )

            if not interview:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Interview not found"
                )
        else:
            # Create new interview
            if not request.workflow:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing workflow for new interview"
                )

            insert_query = """
                INSERT INTO interviews (
                    user_id, workflow, current_stage, current_question, status, created_at, updated_at
                ) VALUES (
                    :user_id, :workflow, :current_stage, :current_question, :status, :created_at, :updated_at
                ) RETURNING id, user_id, workflow, current_stage, current_question, status, created_at, updated_at
            """

            values = {
                "user_id": current_user["id"],
                "workflow": json.dumps(request.workflow),
                "current_stage": 0,
                "current_question": 0,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            interview = await database.fetch_one(query=insert_query, values=values)
            interview_id = str(interview["id"])

        # Save user message if provided
        if request.userMessage:
            message_query = """
                INSERT INTO interview_messages (interview_id, role, content, created_at)
                VALUES (:interview_id, :role, :content, :created_at)
            """
            await database.execute(
                query=message_query,
                values={
                    "interview_id": interview["id"],
                    "role": "user",
                    "content": request.userMessage,
                    "created_at": datetime.utcnow()
                }
            )

        # Get conversation history
        history_query = """
            SELECT role, content
            FROM interview_messages
            WHERE interview_id = :interview_id
            ORDER BY created_at ASC
        """
        history = await database.fetch_all(
            query=history_query,
            values={"interview_id": interview["id"]}
        )

        # Parse workflow from database
        workflow_data = json.loads(interview["workflow"]) if isinstance(interview["workflow"], str) else interview["workflow"]

        # Prepare messages for AI
        system_prompt = get_enterprise_system_prompt("ApplyRush")
        workflow_message = f"WORKFLOW_JSON:{json.dumps(workflow_data)}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": workflow_message},
        ]

        # Add conversation history
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Generate AI response
        ai_client = get_ai_client()
        assistant_response = await ai_client.generate_chat_completion(
            messages=messages,
            max_tokens=800,
            temperature=0
        )

        if not assistant_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate AI response"
            )

        # Save assistant message
        await database.execute(
            query="""
                INSERT INTO interview_messages (interview_id, role, content, created_at)
                VALUES (:interview_id, :role, :content, :created_at)
            """,
            values={
                "interview_id": interview["id"],
                "role": "assistant",
                "content": assistant_response,
                "created_at": datetime.utcnow()
            }
        )

        # Check if interview is complete and extract evaluation
        done = False
        evaluation = None

        trimmed = assistant_response.strip()
        completion_idx = trimmed.find("Interview complete")

        if completion_idx != -1:
            # Look for JSON evaluation after "Interview complete"
            json_start = trimmed.find("{", completion_idx)
            json_end = trimmed.rfind("}")

            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_block = trimmed[json_start:json_end + 1]
                evaluation = safe_json_parse(json_block)

                if evaluation:
                    done = True
                    # Save evaluation
                    eval_query = """
                        INSERT INTO interview_evaluations (interview_id, evaluation, created_at)
                        VALUES (:interview_id, :evaluation, :created_at)
                    """
                    await database.execute(
                        query=eval_query,
                        values={
                            "interview_id": interview["id"],
                            "evaluation": json.dumps(evaluation),
                            "created_at": datetime.utcnow()
                        }
                    )

        # Update interview progress
        next_stage = interview["current_stage"]
        next_question = interview["current_question"]

        if not done:
            # Advance to next question/stage
            stages = workflow_data.get("stages", [])
            current_stage = next_stage
            current_question = next_question

            if current_stage < len(stages):
                current_stage_obj = stages[current_stage]
                questions = current_stage_obj.get("questions", [])
                next_question_index = current_question + 1

                if next_question_index >= len(questions):
                    # Move to next stage
                    next_stage_index = current_stage + 1
                    if next_stage_index >= len(stages):
                        done = True
                    else:
                        next_stage = next_stage_index
                        next_question = 0
                else:
                    next_question = next_question_index

        # Update interview status
        status_value = "completed" if done else "active"
        update_query = """
            UPDATE interviews
            SET current_stage = :current_stage, current_question = :current_question,
                status = :status, updated_at = :updated_at
            WHERE id = :interview_id
        """
        await database.execute(
            query=update_query,
            values={
                "current_stage": next_stage,
                "current_question": next_question,
                "status": status_value,
                "updated_at": datetime.utcnow(),
                "interview_id": interview["id"]
            }
        )

        return InterviewResponse(
            assistant=assistant_response,
            interviewId=str(interview["id"]),
            done=done,
            evaluation=evaluation,
            current_stage=next_stage,
            current_question=next_question
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error conducting interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to conduct interview"
        )


@router.get("/list", response_model=List[InterviewListItem])
async def get_interviews(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get user's interview history"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read interviews"
            )

        query = """
            SELECT i.id, i.workflow, i.current_stage, i.current_question, i.status,
                   i.created_at, i.updated_at, ie.evaluation
            FROM interviews i
            LEFT JOIN interview_evaluations ie ON i.id = ie.interview_id
            WHERE i.user_id = :user_id
            ORDER BY i.created_at DESC
        """

        interviews = await database.fetch_all(
            query=query,
            values={"user_id": current_user["id"]}
        )

        result = []
        for interview in interviews:
            workflow_data = json.loads(interview["workflow"]) if isinstance(interview["workflow"], str) else interview["workflow"]
            workflow_type = workflow_data.get("type", "unknown")

            evaluation_data = None
            if interview["evaluation"]:
                evaluation_data = json.loads(interview["evaluation"]) if isinstance(interview["evaluation"], str) else interview["evaluation"]

            result.append(InterviewListItem(
                id=str(interview["id"]),
                workflow_type=workflow_type,
                status=interview["status"],
                current_stage=interview["current_stage"],
                current_question=interview["current_question"],
                created_at=interview["created_at"],
                updated_at=interview["updated_at"],
                evaluation=evaluation_data
            ))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch interviews"
        )


@router.get("/{interview_id}")
async def get_interview(
    interview_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get detailed interview information"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read interviews"
            )

        # Get interview details
        interview_query = """
            SELECT i.*, ie.evaluation
            FROM interviews i
            LEFT JOIN interview_evaluations ie ON i.id = ie.interview_id
            WHERE i.id = :interview_id AND i.user_id = :user_id
        """

        interview = await database.fetch_one(
            query=interview_query,
            values={"interview_id": interview_id, "user_id": current_user["id"]}
        )

        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )

        # Get messages
        messages_query = """
            SELECT role, content, created_at
            FROM interview_messages
            WHERE interview_id = :interview_id
            ORDER BY created_at ASC
        """

        messages = await database.fetch_all(
            query=messages_query,
            values={"interview_id": interview_id}
        )

        # Format response
        interview_dict = dict(interview)
        interview_dict["workflow"] = json.loads(interview_dict["workflow"]) if isinstance(interview_dict["workflow"], str) else interview_dict["workflow"]

        if interview_dict["evaluation"]:
            interview_dict["evaluation"] = json.loads(interview_dict["evaluation"]) if isinstance(interview_dict["evaluation"], str) else interview_dict["evaluation"]

        interview_dict["messages"] = [
            {
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"]
            }
            for msg in messages
        ]

        return JSONResponse(content=interview_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch interview"
        )


@router.get("/{interview_id}/results")
async def get_interview_results(
    interview_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get interview evaluation results"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to read interview results"
            )

        query = """
            SELECT ie.evaluation, i.status
            FROM interview_evaluations ie
            JOIN interviews i ON ie.interview_id = i.id
            WHERE ie.interview_id = :interview_id AND i.user_id = :user_id
        """

        result = await database.fetch_one(
            query=query,
            values={"interview_id": interview_id, "user_id": current_user["id"]}
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview results not found"
            )

        evaluation = json.loads(result["evaluation"]) if isinstance(result["evaluation"], str) else result["evaluation"]

        return JSONResponse(content={
            "evaluation": evaluation,
            "status": result["status"]
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interview results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch interview results"
        )


class SmartConversationRequest(BaseModel):
    interviewId: str
    message: str


class SmartConversationResponse(BaseModel):
    response: str
    score: int
    feedback: str
    metrics: Dict[str, Any]
    session: Dict[str, Any]
    isComplete: bool
    fallbackMode: Optional[bool] = False


@router.post("/smart-conversation", response_model=SmartConversationResponse)
async def smart_conversation(
    request: SmartConversationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Advanced AI conversation for interviews with intelligent follow-ups"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for smart conversation"
            )

        # Get interview session
        interview_query = """
            SELECT * FROM interviews
            WHERE id = :interview_id AND user_id = :user_id
        """
        interview = await database.fetch_one(
            query=interview_query,
            values={"interview_id": request.interviewId, "user_id": current_user["id"]}
        )

        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found"
            )

        # Try to get AI client
        try:
            ai_client = get_ai_client()
        except Exception:
            # Fallback mode
            return await handle_smart_conversation_fallback(request, interview, current_user)

        # Get conversation history
        messages_query = """
            SELECT role, content FROM interview_messages
            WHERE interview_id = :interview_id
            ORDER BY created_at ASC
        """
        messages = await database.fetch_all(
            query=messages_query,
            values={"interview_id": request.interviewId}
        )

        # Save user message
        await database.execute(
            query="""
                INSERT INTO interview_messages (interview_id, role, content, created_at)
                VALUES (:interview_id, :role, :content, :created_at)
            """,
            values={
                "interview_id": request.interviewId,
                "role": "user",
                "content": request.message,
                "created_at": datetime.utcnow()
            }
        )

        # Build AI conversation context
        workflow_data = json.loads(interview["workflow"]) if isinstance(interview["workflow"], str) else interview["workflow"]

        ai_messages = [
            {
                "role": "system",
                "content": f"""You are an intelligent AI interviewer conducting a {workflow_data.get('role', 'Software Engineer')} interview.

INSTRUCTIONS:
1. Analyze the candidate's response and provide thoughtful follow-up questions
2. Give constructive feedback and scores (0-100)
3. Adapt difficulty based on candidate performance
4. Track interview progress and determine when to conclude

Current interview stage: {interview['current_stage']}/{workflow_data.get('total_stages', 5)}
Role: {workflow_data.get('role', 'Software Engineer')}
Company: {workflow_data.get('company', 'TechCorp')}
Experience Level: {workflow_data.get('experience_level', 'mid')}

Respond with intelligent questions and provide detailed metrics."""
            }
        ]

        # Add conversation history
        for msg in messages:
            ai_messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current user message
        ai_messages.append({"role": "user", "content": request.message})

        # Generate AI response
        ai_response = await ai_client.generate_chat_completion(
            messages=ai_messages,
            max_tokens=600,
            temperature=0.7
        )

        # Evaluate response and generate metrics
        evaluation_prompt = f"""
        Evaluate this interview response:
        Question context: Previous conversation
        Candidate answer: {request.message}

        Provide JSON with: score (0-100), feedback (2 sentences), and performance metrics.
        """

        evaluation_response = await ai_client.generate_text(evaluation_prompt)

        # Parse evaluation or use fallback
        try:
            evaluation_data = json.loads(evaluation_response)
            score = evaluation_data.get("score", 75)
            feedback = evaluation_data.get("feedback", "Good response. Please continue.")
            metrics = evaluation_data.get("metrics", {
                "confidence_level": 75,
                "technical_depth": 70,
                "communication_clarity": 80,
                "response_time_avg": 0,
                "engagement_score": 75
            })
        except:
            score = 75
            feedback = "Good response. Please continue."
            metrics = {
                "confidence_level": 75,
                "technical_depth": 70,
                "communication_clarity": 80,
                "response_time_avg": 0,
                "engagement_score": 75
            }

        # Check if interview should be completed
        questions_answered = len([m for m in messages if m["role"] == "user"])
        max_questions = workflow_data.get("duration_minutes", 30) // 3
        is_complete = questions_answered >= max_questions

        # Save AI response
        await database.execute(
            query="""
                INSERT INTO interview_messages (interview_id, role, content, metadata, created_at)
                VALUES (:interview_id, :role, :content, :metadata, :created_at)
            """,
            values={
                "interview_id": request.interviewId,
                "role": "assistant",
                "content": ai_response,
                "metadata": json.dumps({"score": score, "feedback": feedback, "metrics": metrics}),
                "created_at": datetime.utcnow()
            }
        )

        # Update interview progress
        await database.execute(
            query="""
                UPDATE interviews
                SET current_question = current_question + 1,
                    status = :status,
                    updated_at = :updated_at
                WHERE id = :interview_id
            """,
            values={
                "status": "completed" if is_complete else "active",
                "updated_at": datetime.utcnow(),
                "interview_id": request.interviewId
            }
        )

        # Build session info
        session_info = {
            "id": request.interviewId,
            "role": workflow_data.get("role", "Software Engineer"),
            "company": workflow_data.get("company", "TechCorp"),
            "status": "completed" if is_complete else "active",
            "current_stage": interview["current_stage"],
            "current_question": interview["current_question"] + 1,
            "total_questions": max_questions,
            "questions_answered": questions_answered + 1,
            "performance_score": score,
            "difficulty_level": workflow_data.get("difficulty_level", 3),
            "started_at": interview["created_at"],
            "duration_minutes": workflow_data.get("duration_minutes", 30)
        }

        return SmartConversationResponse(
            response=ai_response,
            score=score,
            feedback=feedback,
            metrics=metrics,
            session=session_info,
            isComplete=is_complete,
            fallbackMode=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in smart conversation: {str(e)}")
        # Fallback to simple conversation
        return await handle_smart_conversation_fallback(request, interview, current_user)


async def handle_smart_conversation_fallback(
    request: SmartConversationRequest,
    interview: Dict[str, Any],
    current_user: Dict[str, Any]
):
    """Fallback conversation handling when AI is unavailable"""
    try:
        workflow_data = json.loads(interview["workflow"]) if isinstance(interview["workflow"], str) else interview["workflow"]

        # Simple fallback questions
        fallback_questions = [
            f"Thank you for that response. Can you tell me about your experience with {workflow_data.get('role', 'software').lower()} development?",
            "That's interesting. How do you approach problem-solving in your work?",
            "Great! What technologies are you most comfortable working with?",
            "Can you describe a challenging project you've worked on?",
            "How do you stay current with new technologies?",
            "What motivates you in your career?",
            "How do you handle working in a team environment?",
            "Thank you for participating in this interview. Your responses show good engagement."
        ]

        # Get message count to determine which question to ask
        message_count_query = """
            SELECT COUNT(*) as count FROM interview_messages
            WHERE interview_id = :interview_id AND role = 'assistant'
        """
        count_result = await database.fetch_one(
            query=message_count_query,
            values={"interview_id": request.interviewId}
        )

        question_index = (count_result["count"] if count_result else 0) % len(fallback_questions)
        response = fallback_questions[question_index]
        is_complete = question_index >= len(fallback_questions) - 1

        # Save user message
        await database.execute(
            query="""
                INSERT INTO interview_messages (interview_id, role, content, created_at)
                VALUES (:interview_id, :role, :content, :created_at)
            """,
            values={
                "interview_id": request.interviewId,
                "role": "user",
                "content": request.message,
                "created_at": datetime.utcnow()
            }
        )

        # Save AI response
        await database.execute(
            query="""
                INSERT INTO interview_messages (interview_id, role, content, metadata, created_at)
                VALUES (:interview_id, :role, :content, :metadata, :created_at)
            """,
            values={
                "interview_id": request.interviewId,
                "role": "assistant",
                "content": response,
                "metadata": json.dumps({"fallback_mode": True}),
                "created_at": datetime.utcnow()
            }
        )

        session_info = {
            "id": request.interviewId,
            "role": workflow_data.get("role", "Software Engineer"),
            "company": workflow_data.get("company", "TechCorp"),
            "status": "completed" if is_complete else "active",
            "current_stage": interview["current_stage"],
            "current_question": question_index + 1,
            "total_questions": len(fallback_questions),
            "questions_answered": question_index + 1,
            "performance_score": 75,
            "difficulty_level": workflow_data.get("difficulty_level", 3),
            "started_at": interview["created_at"],
            "duration_minutes": workflow_data.get("duration_minutes", 30)
        }

        return SmartConversationResponse(
            response=response,
            score=75,
            feedback="Good response, please continue.",
            metrics={
                "confidence_level": 70,
                "technical_depth": 65,
                "communication_clarity": 80,
                "response_time_avg": 0,
                "engagement_score": 75
            },
            session=session_info,
            isComplete=is_complete,
            fallbackMode=True
        )

    except Exception as e:
        logger.error(f"Error in fallback conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process conversation"
        )


class InterviewSessionAction(BaseModel):
    action: str  # pause, resume, complete


@router.post("/session/{session_id}/pause")
async def pause_interview_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Pause an interview session"""
    try:
        await database.execute(
            query="UPDATE interviews SET status = 'paused', updated_at = :updated_at WHERE id = :session_id AND user_id = :user_id",
            values={
                "updated_at": datetime.utcnow(),
                "session_id": session_id,
                "user_id": current_user["id"]
            }
        )

        return {"success": True, "message": "Interview session paused", "status": "paused"}

    except Exception as e:
        logger.error(f"Error pausing interview session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause interview session"
        )


@router.post("/session/{session_id}/resume")
async def resume_interview_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Resume a paused interview session"""
    try:
        await database.execute(
            query="UPDATE interviews SET status = 'active', updated_at = :updated_at WHERE id = :session_id AND user_id = :user_id",
            values={
                "updated_at": datetime.utcnow(),
                "session_id": session_id,
                "user_id": current_user["id"]
            }
        )

        return {"success": True, "message": "Interview session resumed", "status": "active"}

    except Exception as e:
        logger.error(f"Error resuming interview session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume interview session"
        )


@router.post("/session/{session_id}/complete")
async def complete_interview_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Complete an interview session"""
    try:
        # Update session status
        await database.execute(
            query="UPDATE interviews SET status = 'completed', updated_at = :updated_at WHERE id = :session_id AND user_id = :user_id",
            values={
                "updated_at": datetime.utcnow(),
                "session_id": session_id,
                "user_id": current_user["id"]
            }
        )

        # Generate final evaluation if not exists
        eval_check = await database.fetch_one(
            query="SELECT id FROM interview_evaluations WHERE interview_id = :session_id",
            values={"session_id": session_id}
        )

        if not eval_check:
            final_evaluation = {
                "overall_score": 75,
                "strengths": ["Good communication", "Technical knowledge"],
                "areas_for_improvement": ["Could provide more specific examples"],
                "recommendation": "Consider for next round",
                "completed_at": datetime.utcnow().isoformat()
            }

            await database.execute(
                query="""
                    INSERT INTO interview_evaluations (interview_id, evaluation, created_at)
                    VALUES (:interview_id, :evaluation, :created_at)
                """,
                values={
                    "interview_id": session_id,
                    "evaluation": json.dumps(final_evaluation),
                    "created_at": datetime.utcnow()
                }
            )

        return {"success": True, "message": "Interview session completed", "status": "completed"}

    except Exception as e:
        logger.error(f"Error completing interview session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete interview session"
        )


@router.get("/session/{session_id}")
async def get_interview_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get interview session details"""
    try:
        # Get session details - using the existing get_interview function logic
        return await get_interview(session_id, current_user)

    except Exception as e:
        logger.error(f"Error fetching interview session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch interview session"
        )


@router.post("/create")
async def create_interview_session(
    workflow: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new interview session"""
    try:
        if not permission_checker.has_permission(current_user, "interviews", "create"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create interview sessions"
            )

        # Create new interview session
        insert_query = """
            INSERT INTO interviews (
                user_id, workflow, current_stage, current_question, status, created_at, updated_at
            ) VALUES (
                :user_id, :workflow, :current_stage, :current_question, :status, :created_at, :updated_at
            ) RETURNING *
        """

        values = {
            "user_id": current_user["id"],
            "workflow": json.dumps(workflow),
            "current_stage": 0,
            "current_question": 0,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        interview = await database.fetch_one(query=insert_query, values=values)

        # Format response
        interview_dict = dict(interview)
        interview_dict["id"] = str(interview_dict["id"])
        interview_dict["workflow"] = workflow

        return {
            "success": True,
            "interview": interview_dict,
            "message": "Interview session created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating interview session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create interview session"
        )