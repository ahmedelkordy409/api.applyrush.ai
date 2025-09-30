"""
Cover Letter API endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.security import HTTPBearer

from jobhire.config.settings import get_settings

# Mock dependencies for demo
def get_current_user():
    """Mock current user dependency."""
    return {"user_id": "demo_user", "email": "demo@applyrush.ai"}

def get_event_bus():
    """Mock event bus dependency."""
    class MockEventBus:
        async def publish(self, event): pass
    return MockEventBus()

from ...application.dto.cover_letter_dto import (
    CreateCoverLetterDTO, CoverLetterResponseDTO, SaveCoverLetterDTO,
    ExportCoverLetterDTO, ExportResponseDTO, CoverLetterHistoryResponseDTO,
    CoverLetterFeedbackDTO, CoverLetterAnalyticsDTO, CustomizeCoverLetterDTO,
    WritingStyleOptionDTO
)
from ...application.services.cover_letter_service import CoverLetterService
from ...infrastructure.ai.cover_letter_ai_service import CoverLetterAIService
from ...infrastructure.export.cover_letter_export_service import CoverLetterExportService

# Create router
router = APIRouter(prefix="/cover-letter", tags=["📝 AI Cover Letter Generator"])

# Security
security = HTTPBearer()


def get_cover_letter_service() -> CoverLetterService:
    """Dependency to get cover letter service."""
    settings = get_settings()
    ai_service = CoverLetterAIService(
        openai_api_key=settings.ai.openai_api_key,
        model="gpt-4o"
    )
    event_bus = get_event_bus()

    return CoverLetterService(
        ai_service=ai_service,
        event_bus=event_bus,
        openai_api_key=settings.ai.openai_api_key
    )


def get_export_service() -> CoverLetterExportService:
    """Dependency to get cover letter export service."""
    return CoverLetterExportService()


@router.post(
    "/generate",
    response_model=CoverLetterResponseDTO,
    summary="Generate AI Cover Letter",
    description="""
    Generate a personalized AI cover letter tailored to the specific job and company.

    **Features:**
    - AI-powered content generation using GPT-4o
    - Multiple writing styles (Professional, Creative, Executive, etc.)
    - Industry-specific optimization
    - Company culture analysis
    - Keyword optimization for ATS systems
    - Customizable tone and length

    **Writing Styles:**
    - `professional`: Traditional business writing
    - `creative`: Unique and engaging approach
    - `executive`: Senior leadership tone
    - `technical`: Technical competency focus
    - `enthusiastic`: High-energy and passionate
    - `casual`: Friendly yet professional

    **Length Options:**
    - `short`: 150-250 words, concise
    - `medium`: 250-400 words, balanced
    - `long`: 400-600 words, comprehensive

    **Focus Areas:**
    - `experience`: Professional background
    - `skills`: Technical competencies
    - `achievements`: Measurable results
    - `passion`: Industry enthusiasm
    - `leadership`: Management experience
    """,
    status_code=status.HTTP_201_CREATED
)
async def generate_cover_letter(
    request: CreateCoverLetterDTO,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> CoverLetterResponseDTO:
    """Generate AI-powered cover letter."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.generate_cover_letter(user_id, request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/save",
    summary="Save Cover Letter",
    description="""
    Save a generated cover letter to user's history for future reference.

    **Features:**
    - Add to personal cover letter library
    - Tag for easy categorization
    - Track usage analytics
    - Enable future customization
    """,
    status_code=status.HTTP_200_OK
)
async def save_cover_letter(
    request: SaveCoverLetterDTO,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> Dict[str, str]:
    """Save cover letter to user's history."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.save_cover_letter(user_id, request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/history",
    response_model=CoverLetterHistoryResponseDTO,
    summary="Get Cover Letter History",
    description="""
    Retrieve user's previously generated cover letters with pagination.

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 10, max: 50)
    - `company`: Filter by company name
    - `position`: Filter by job position
    - `style`: Filter by writing style

    **Response includes:**
    - Cover letter metadata
    - Quality scores
    - Tags and categorization
    - Creation timestamps
    """
)
async def get_cover_letter_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    company: Optional[str] = Query(None, description="Filter by company"),
    position: Optional[str] = Query(None, description="Filter by position"),
    style: Optional[str] = Query(None, description="Filter by writing style"),
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> CoverLetterHistoryResponseDTO:
    """Get user's cover letter history."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.get_cover_letter_history(user_id, page, page_size)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{cover_letter_id}",
    summary="Get Cover Letter by ID",
    description="""
    Retrieve a specific cover letter by its ID.

    **Returns:**
    - Complete cover letter content
    - Generation metadata
    - Quality assessment
    - Edit history
    """
)
async def get_cover_letter_by_id(
    cover_letter_id: str,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> Dict[str, Any]:
    """Get specific cover letter by ID."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.get_cover_letter_by_id(user_id, cover_letter_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/customize",
    response_model=CoverLetterResponseDTO,
    summary="Customize Existing Cover Letter",
    description="""
    Customize an existing cover letter for a new job opportunity.

    **Features:**
    - Adapt content for new company/role
    - Maintain original writing style
    - Update relevant keywords
    - Preserve core value proposition
    - Fast customization process

    **Use Cases:**
    - Similar roles at different companies
    - Career progression (same field, higher level)
    - Industry transitions
    - Company culture adaptations
    """,
    status_code=status.HTTP_201_CREATED
)
async def customize_cover_letter(
    request: CustomizeCoverLetterDTO,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> CoverLetterResponseDTO:
    """Customize existing cover letter for new role."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.customize_cover_letter(user_id, request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/export",
    response_model=ExportResponseDTO,
    summary="Export Cover Letter",
    description="""
    Export cover letter in various formats for download or sharing.

    **Supported Formats:**
    - `pdf`: Professional PDF with formatting
    - `docx`: Microsoft Word document
    - `txt`: Plain text file
    - `html`: HTML with styling

    **Features:**
    - Professional formatting
    - Custom letterhead options
    - Contact information inclusion
    - Branded templates
    """,
    status_code=status.HTTP_201_CREATED
)
async def export_cover_letter(
    request: ExportCoverLetterDTO,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service),
    export_service: CoverLetterExportService = Depends(get_export_service)
) -> ExportResponseDTO:
    """Export cover letter in specified format."""
    try:
        user_id = current_user.get("user_id", "demo_user")

        # Get the cover letter content first
        cover_letter_data = await service.get_cover_letter_by_id(user_id, request.cover_letter_id)

        # Extract content and personal info for export
        cover_letter_content = cover_letter_data.get("content", "")
        personal_info = {
            "full_name": current_user.get("full_name", "Demo User"),
            "email_address": current_user.get("email", "demo@applyrush.ai"),
            "phone_number": current_user.get("phone", "+1 (555) 123-4567"),
            "city": current_user.get("city", "San Francisco, CA"),
            "company_name": cover_letter_data.get("company_name", "Target Company")
        }

        # Export using the actual export service
        export_result = await export_service.export_cover_letter(
            cover_letter_content=cover_letter_content,
            personal_info=personal_info,
            export_format=request.format,
            include_contact_info=request.include_contact_info,
            letterhead_style=request.letterhead_style
        )

        return ExportResponseDTO(
            export_id=export_result["export_id"],
            download_url=export_result["download_url"],
            file_name=export_result["file_name"],
            file_size_bytes=export_result["file_size_bytes"],
            format=export_result["format"],
            expires_at=export_result["expires_at"].isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/feedback",
    summary="Submit Cover Letter Feedback",
    description="""
    Submit feedback and rating for a generated cover letter.

    **Feedback helps improve:**
    - AI generation quality
    - Content relevance
    - Writing style effectiveness
    - User experience optimization

    **Rating Scale:** 1-10 (1=Poor, 10=Excellent)
    """,
    status_code=status.HTTP_200_OK
)
async def submit_feedback(
    request: CoverLetterFeedbackDTO,
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> Dict[str, str]:
    """Submit feedback for cover letter."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.submit_feedback(user_id, request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/analytics",
    response_model=CoverLetterAnalyticsDTO,
    summary="Get Cover Letter Analytics",
    description="""
    Retrieve user's cover letter usage analytics and insights.

    **Analytics Include:**
    - Total cover letters generated
    - Monthly usage trends
    - Quality score averages
    - Most used writing styles
    - Top target industries
    - Success metrics tracking

    **Use for:**
    - Usage tracking
    - Performance optimization
    - Trend identification
    - Success measurement
    """
)
async def get_analytics(
    current_user: dict = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> CoverLetterAnalyticsDTO:
    """Get user's cover letter analytics."""
    try:
        user_id = current_user.get("user_id", "demo_user")
        result = await service.get_user_analytics(user_id)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/options/writing-styles",
    response_model=List[WritingStyleOptionDTO],
    summary="Get Writing Style Options",
    description="""
    Retrieve available writing style options for cover letter generation.

    **Available Styles:**
    - **Professional**: Traditional business writing
    - **Creative**: Unique and memorable approach
    - **Executive**: Senior leadership tone
    - **Technical**: Technical competency focus
    - **Enthusiastic**: High-energy and passionate
    - **Casual**: Friendly yet professional

    Each style includes description and tone guidance.
    """
)
async def get_writing_styles(
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> List[Dict[str, str]]:
    """Get available writing style options."""
    return service.get_writing_styles()


@router.get(
    "/options/configuration",
    summary="Get All Configuration Options",
    description="""
    Retrieve all available configuration options for the cover letter generator.

    **Includes:**
    - Writing styles with descriptions
    - Length options (short/medium/long)
    - Tone options (professional/enthusiastic/etc.)
    - Focus areas (experience/skills/achievements/etc.)

    **Use for:**
    - Populating UI dropdowns
    - Validation rules
    - User guidance
    """
)
async def get_configuration_options(
    service: CoverLetterService = Depends(get_cover_letter_service)
) -> Dict[str, Any]:
    """Get all configuration options."""
    return service.get_configuration_options()