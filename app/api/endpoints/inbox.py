"""
Inbox API endpoints for managing user messages/emails
Handles forwarded emails, application confirmations, interview invites, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import BaseModel, Field

from app.core.database_new import get_async_db
from app.core.security import get_current_user

router = APIRouter()


# Helper to get user ID from current user
def get_user_id(current_user: dict) -> str:
    """Extract user_id from current_user dict"""
    return str(current_user.get("id") or current_user.get("_id"))


# =========================================
# PYDANTIC MODELS
# =========================================

class MessageBase(BaseModel):
    """Base message model"""
    sender_email: str
    sender_name: Optional[str] = None
    subject: str
    body: str
    category: str  # Application Confirmed, Interview Invite, Follow-up, etc.
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Email metadata
    raw_headers: Optional[dict] = None
    thread_id: Optional[str] = None

    # Application tracking
    related_application_id: Optional[str] = None
    related_job_id: Optional[str] = None
    company_name: Optional[str] = None

    # Auto-apply tracking
    is_auto_applied: bool = False
    ats_type: Optional[str] = None  # greenhouse, lever, workday, etc.
    confirmation_number: Optional[str] = None
    application_status: Optional[str] = None

    # Scam detection
    is_scam: bool = False
    scam_score: Optional[float] = None
    scam_indicators: Optional[List[str]] = None


class MessageCreate(MessageBase):
    """Model for creating a new message"""
    pass


class MessageResponse(MessageBase):
    """Model for message response"""
    id: str = Field(alias="_id")
    user_id: str
    is_read: bool = False
    is_marked_as_scam: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class MessageUpdate(BaseModel):
    """Model for updating message"""
    is_read: Optional[bool] = None
    is_marked_as_scam: Optional[bool] = None
    category: Optional[str] = None


class MessagesListResponse(BaseModel):
    """Response model for list of messages"""
    messages: List[MessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# =========================================
# ENDPOINTS
# =========================================

@router.get("/messages", response_model=MessagesListResponse)
async def get_user_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    is_read: Optional[bool] = None,
    is_scam: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Get user's inbox messages with filtering and pagination
    """
    try:
        collection = db.messages

        # Build filter query
        query_filter = {"user_id": get_user_id(current_user)}

        if category:
            query_filter["category"] = category

        if is_read is not None:
            query_filter["is_read"] = is_read

        if is_scam is not None:
            if is_scam:
                query_filter["$or"] = [
                    {"is_scam": True},
                    {"is_marked_as_scam": True}
                ]
            else:
                query_filter["is_scam"] = False
                query_filter["is_marked_as_scam"] = False

        # Get total count
        total = await collection.count_documents(query_filter)

        # Get paginated messages
        skip = (page - 1) * page_size
        cursor = collection.find(query_filter).sort("received_at", -1).skip(skip).limit(page_size)
        messages = await cursor.to_list(length=page_size)

        # Convert to response models
        message_responses = []
        for msg in messages:
            msg["_id"] = str(msg["_id"])
            message_responses.append(MessageResponse(**msg))

        has_more = (skip + page_size) < total

        return MessagesListResponse(
            messages=message_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Get a specific message by ID
    """
    try:
        collection = db.messages

        message = await collection.find_one({
            "_id": ObjectId(message_id),
            "user_id": get_user_id(current_user)
        })

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Mark as read
        await collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"is_read": True, "updated_at": datetime.now(timezone.utc)}}
        )

        message["_id"] = str(message["_id"])
        message["is_read"] = True

        return MessageResponse(**message)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch message: {str(e)}")


@router.post("/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Create a new message (typically from forwarded email)
    """
    try:
        collection = db.messages

        message_dict = message_data.dict()
        message_dict.update({
            "user_id": get_user_id(current_user),
            "is_read": False,
            "is_marked_as_scam": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })

        result = await collection.insert_one(message_dict)

        # Fetch the created message
        created_message = await collection.find_one({"_id": result.inserted_id})
        created_message["_id"] = str(created_message["_id"])

        return MessageResponse(**created_message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create message: {str(e)}")


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    update_data: MessageUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Update a message (mark as read, mark as scam, etc.)
    """
    try:
        collection = db.messages

        # Verify message belongs to user
        message = await collection.find_one({
            "_id": ObjectId(message_id),
            "user_id": get_user_id(current_user)
        })

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Build update dict
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

        if update_dict:
            update_dict["updated_at"] = datetime.now(timezone.utc)

            await collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": update_dict}
            )

        # Fetch updated message
        updated_message = await collection.find_one({"_id": ObjectId(message_id)})
        updated_message["_id"] = str(updated_message["_id"])

        return MessageResponse(**updated_message)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update message: {str(e)}")


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Delete a message
    """
    try:
        collection = db.messages

        # Verify message belongs to user
        message = await collection.find_one({
            "_id": ObjectId(message_id),
            "user_id": get_user_id(current_user)
        })

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        await collection.delete_one({"_id": ObjectId(message_id)})

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")


@router.get("/messages/stats/summary")
async def get_messages_stats(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_async_db)
):
    """
    Get summary statistics for user's messages
    """
    try:
        collection = db.messages

        total_messages = await collection.count_documents({"user_id": get_user_id(current_user)})
        unread_messages = await collection.count_documents({"user_id": get_user_id(current_user), "is_read": False})
        scam_messages = await collection.count_documents({
            "user_id": get_user_id(current_user),
            "$or": [{"is_scam": True}, {"is_marked_as_scam": True}]
        })

        # Count by category
        pipeline = [
            {"$match": {"user_id": get_user_id(current_user)}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        category_counts = await collection.aggregate(pipeline).to_list(None)

        return {
            "total": total_messages,
            "unread": unread_messages,
            "scam": scam_messages,
            "by_category": {item["_id"]: item["count"] for item in category_counts}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
