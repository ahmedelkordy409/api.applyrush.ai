"""
Cover Letter application service - orchestrates business logic.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import structlog

from jobhire.shared.domain.base import EntityId
from jobhire.shared.infrastructure.events import EventBus
from ..dto.cover_letter_dto import (
    CreateCoverLetterDTO, CoverLetterResponseDTO, SaveCoverLetterDTO,
    ExportCoverLetterDTO, ExportResponseDTO, CoverLetterHistoryDTO,
    CoverLetterHistoryResponseDTO, CoverLetterFeedbackDTO, CoverLetterAnalyticsDTO,
    CustomizeCoverLetterDTO
)
from ...domain.entities.cover_letter import (
    CoverLetter, PersonalInfo, JobContext, GenerationSettings
)
from ...domain.value_objects.cover_letter_config import (
    WritingStyle, WRITING_STYLE_TEMPLATES, get_writing_style_options,
    get_length_options, get_tone_options, get_focus_area_options
)
from ...infrastructure.ai.cover_letter_ai_service import CoverLetterAIService

logger = structlog.get_logger(__name__)


class CoverLetterService:
    """Application service for cover letter operations."""

    def __init__(
        self,
        ai_service: CoverLetterAIService,
        event_bus: EventBus,
        openai_api_key: str
    ):
        self.ai_service = ai_service
        self.event_bus = event_bus
        self.openai_api_key = openai_api_key

        # In-memory storage for demo (replace with proper repository)
        self.cover_letters: Dict[str, CoverLetter] = {}
        self.user_history: Dict[str, List[str]] = {}

    async def generate_cover_letter(
        self,
        user_id: str,
        request: CreateCoverLetterDTO
    ) -> CoverLetterResponseDTO:
        """Generate a new AI-powered cover letter."""
        try:
            start_time = datetime.now()

            # Create domain objects
            personal_info = PersonalInfo(
                full_name=request.full_name,
                email_address=request.email_address,
                phone_number=request.phone_number,
                city=request.city,
                linkedin_profile=request.linkedin_profile,
                website=request.website
            )

            job_context = JobContext(
                desired_position=request.desired_position,
                company_name=request.company_name,
                job_details=request.job_details,
                hiring_manager_name=request.hiring_manager_name,
                department=request.department,
                job_source=request.job_source
            )

            # Validate and convert writing style
            try:
                writing_style = WritingStyle(request.writing_style)
            except ValueError:
                writing_style = WritingStyle.PROFESSIONAL

            generation_settings = GenerationSettings(
                writing_style=writing_style,
                tone=request.tone,
                length=request.length,
                focus_areas=request.focus_areas,
                include_salary_expectations=request.include_salary_expectations,
                custom_instructions=request.custom_instructions
            )

            # Create cover letter entity
            cover_letter_id = EntityId(str(uuid.uuid4()))
            cover_letter = CoverLetter(
                cover_letter_id=cover_letter_id,
                user_id=user_id,
                personal_info=personal_info,
                job_context=job_context,
                generation_settings=generation_settings
            )

            # Analyze job description
            job_analysis = await self.ai_service.analyze_job_description(
                job_description=request.job_details,
                company_name=request.company_name
            )

            # Generate cover letter content
            personal_info_dict = {
                "full_name": request.full_name,
                "email_address": request.email_address,
                "phone_number": request.phone_number,
                "city": request.city,
                "desired_position": request.desired_position,
                "company_name": request.company_name
            }

            generation_result = await self.ai_service.generate_cover_letter(
                personal_info=personal_info_dict,
                job_analysis=job_analysis,
                writing_style=writing_style,
                length=request.length,
                tone=request.tone,
                focus_areas=request.focus_areas,
                custom_instructions=request.custom_instructions
            )

            # Calculate generation time
            generation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update cover letter with generated content
            cover_letter.generate_content(
                content=generation_result.cover_letter_content,
                ai_model="gpt-4o",
                generation_time_ms=generation_time_ms,
                key_highlights=generation_result.key_highlights
            )

            # Store cover letter
            self.cover_letters[str(cover_letter_id)] = cover_letter

            # Publish domain events
            for event in cover_letter.get_domain_events():
                await self.event_bus.publish(event)

            cover_letter.clear_domain_events()

            # Return response
            return CoverLetterResponseDTO(
                cover_letter_id=str(cover_letter_id),
                cover_letter=generation_result.cover_letter_content,
                generation_id=cover_letter.generation_id,
                word_count=generation_result.word_count,
                paragraph_count=generation_result.paragraph_count,
                key_highlights=generation_result.key_highlights,
                confidence_score=generation_result.confidence_score,
                generation_time_ms=generation_time_ms,
                timestamp=cover_letter.generated_at
            )

        except Exception as e:
            logger.error("Error generating cover letter", error=str(e), user_id=user_id)
            raise

    async def save_cover_letter(
        self,
        user_id: str,
        request: SaveCoverLetterDTO
    ) -> Dict[str, str]:
        """Save cover letter to user's history."""
        try:
            cover_letter = self.cover_letters.get(request.cover_letter_id)
            if not cover_letter:
                raise ValueError("Cover letter not found")

            if cover_letter.user_id != user_id:
                raise ValueError("Unauthorized access to cover letter")

            # Save to history
            cover_letter.save_cover_letter(save_to_history=request.save_to_history)

            # Add tags if provided
            if request.tags:
                cover_letter.add_tags(request.tags)

            # Update user history
            if user_id not in self.user_history:
                self.user_history[user_id] = []

            if request.cover_letter_id not in self.user_history[user_id]:
                self.user_history[user_id].append(request.cover_letter_id)

            # Publish domain events
            for event in cover_letter.get_domain_events():
                await self.event_bus.publish(event)

            cover_letter.clear_domain_events()

            return {"message": "Cover letter saved successfully", "status": "saved"}

        except Exception as e:
            logger.error("Error saving cover letter", error=str(e), user_id=user_id)
            raise

    async def get_cover_letter_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> CoverLetterHistoryResponseDTO:
        """Get user's cover letter history."""
        try:
            user_cover_letters = self.user_history.get(user_id, [])

            # Calculate pagination
            total_count = len(user_cover_letters)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            # Get paginated cover letters
            paginated_ids = user_cover_letters[start_idx:end_idx]

            history_items = []
            for cover_letter_id in paginated_ids:
                cover_letter = self.cover_letters.get(cover_letter_id)
                if cover_letter and cover_letter.status in ["saved", "exported"]:
                    history_items.append(CoverLetterHistoryDTO(
                        cover_letter_id=cover_letter_id,
                        position=cover_letter.job_context.desired_position,
                        company=cover_letter.job_context.company_name,
                        writing_style=cover_letter.generation_settings.writing_style.value,
                        word_count=cover_letter.content.word_count if cover_letter.content else 0,
                        quality_score=cover_letter.quality_score,
                        tags=cover_letter.tags,
                        created_at=cover_letter.created_at,
                        status=cover_letter.status
                    ))

            return CoverLetterHistoryResponseDTO(
                cover_letters=history_items,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_next=end_idx < total_count
            )

        except Exception as e:
            logger.error("Error getting cover letter history", error=str(e), user_id=user_id)
            raise

    async def get_cover_letter_by_id(
        self,
        user_id: str,
        cover_letter_id: str
    ) -> Dict[str, Any]:
        """Get specific cover letter by ID."""
        try:
            cover_letter = self.cover_letters.get(cover_letter_id)
            if not cover_letter:
                raise ValueError("Cover letter not found")

            if cover_letter.user_id != user_id:
                raise ValueError("Unauthorized access to cover letter")

            return cover_letter.to_dict()

        except Exception as e:
            logger.error("Error getting cover letter", error=str(e), user_id=user_id)
            raise

    async def customize_cover_letter(
        self,
        user_id: str,
        request: CustomizeCoverLetterDTO
    ) -> CoverLetterResponseDTO:
        """Customize existing cover letter for new role."""
        try:
            base_cover_letter = self.cover_letters.get(request.base_cover_letter_id)
            if not base_cover_letter:
                raise ValueError("Base cover letter not found")

            if base_cover_letter.user_id != user_id:
                raise ValueError("Unauthorized access to cover letter")

            if not base_cover_letter.content:
                raise ValueError("Base cover letter has no content to customize")

            # Analyze new job
            job_analysis = await self.ai_service.analyze_job_description(
                job_description=request.new_job_details,
                company_name=request.new_company
            )

            # Customize the cover letter
            customized_content = await self.ai_service.customize_for_company(
                base_cover_letter=base_cover_letter.content.content,
                new_job_analysis=job_analysis,
                customization_focus=request.customization_focus + [request.new_position]
            )

            # Create new cover letter entity
            new_cover_letter_id = EntityId(str(uuid.uuid4()))

            # Copy settings from base letter
            generation_settings = base_cover_letter.generation_settings if request.maintain_style else GenerationSettings(
                writing_style=WritingStyle.PROFESSIONAL
            )

            # Update job context
            new_job_context = JobContext(
                desired_position=request.new_position,
                company_name=request.new_company,
                job_details=request.new_job_details
            )

            new_cover_letter = CoverLetter(
                cover_letter_id=new_cover_letter_id,
                user_id=user_id,
                personal_info=base_cover_letter.personal_info,
                job_context=new_job_context,
                generation_settings=generation_settings
            )

            # Set customized content
            new_cover_letter.generate_content(
                content=customized_content,
                ai_model="gpt-4o",
                generation_time_ms=1000,  # Customization is faster
                key_highlights=["Customized from previous letter"]
            )

            # Store new cover letter
            self.cover_letters[str(new_cover_letter_id)] = new_cover_letter

            return CoverLetterResponseDTO(
                cover_letter_id=str(new_cover_letter_id),
                cover_letter=customized_content,
                generation_id=new_cover_letter.generation_id,
                word_count=len(customized_content.split()),
                paragraph_count=len([p for p in customized_content.split('\n\n') if p.strip()]),
                key_highlights=["Customized for new role"],
                confidence_score=85.0,
                generation_time_ms=1000,
                timestamp=new_cover_letter.generated_at
            )

        except Exception as e:
            logger.error("Error customizing cover letter", error=str(e), user_id=user_id)
            raise

    async def submit_feedback(
        self,
        user_id: str,
        request: CoverLetterFeedbackDTO
    ) -> Dict[str, str]:
        """Submit feedback for a cover letter."""
        try:
            cover_letter = self.cover_letters.get(request.cover_letter_id)
            if not cover_letter:
                raise ValueError("Cover letter not found")

            if cover_letter.user_id != user_id:
                raise ValueError("Unauthorized access to cover letter")

            # Add feedback to cover letter
            cover_letter.add_feedback(
                feedback=request.feedback_text or "",
                quality_score=request.quality_score
            )

            return {"message": "Feedback submitted successfully", "status": "received"}

        except Exception as e:
            logger.error("Error submitting feedback", error=str(e), user_id=user_id)
            raise

    async def get_user_analytics(self, user_id: str) -> CoverLetterAnalyticsDTO:
        """Get analytics for user's cover letter usage."""
        try:
            user_cover_letters = [
                self.cover_letters[cl_id] for cl_id in self.user_history.get(user_id, [])
                if cl_id in self.cover_letters
            ]

            # Calculate analytics
            total_generated = len(user_cover_letters)

            # This month (simplified - last 30 days)
            current_time = datetime.now(timezone.utc)
            this_month = sum(
                1 for cl in user_cover_letters
                if (current_time - cl.created_at).days <= 30
            )

            # Average quality score
            quality_scores = [cl.quality_score for cl in user_cover_letters if cl.quality_score]
            average_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

            # Most used style
            styles = [cl.generation_settings.writing_style.value for cl in user_cover_letters]
            most_used_style = max(set(styles), key=styles.count) if styles else "professional"

            # Top industries
            industries = [cl.industry_sector for cl in user_cover_letters if cl.industry_sector]
            industry_counts = {}
            for industry in industries:
                industry_counts[industry] = industry_counts.get(industry, 0) + 1

            top_industries = [
                {"industry": industry, "count": count}
                for industry, count in sorted(industry_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            return CoverLetterAnalyticsDTO(
                total_generated=total_generated,
                this_month=this_month,
                average_quality_score=average_quality,
                most_used_style=most_used_style,
                top_industries=top_industries,
                success_metrics={
                    "response_rate": 0.0,  # Would track from actual applications
                    "interview_rate": 0.0
                }
            )

        except Exception as e:
            logger.error("Error getting user analytics", error=str(e), user_id=user_id)
            raise

    def get_writing_styles(self) -> List[Dict[str, str]]:
        """Get available writing style options."""
        return get_writing_style_options()

    def get_configuration_options(self) -> Dict[str, Any]:
        """Get all configuration options for the UI."""
        return {
            "writing_styles": get_writing_style_options(),
            "lengths": get_length_options(),
            "tones": get_tone_options(),
            "focus_areas": get_focus_area_options()
        }