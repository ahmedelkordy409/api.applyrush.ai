"""
Search preferences DTOs.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SearchPreferencesUpdateDTO(BaseModel):
    """DTO for updating search preferences."""
    keywords: Optional[List[str]] = Field(None, description="Job search keywords")
    locations: Optional[List[str]] = Field(None, description="Preferred job locations")
    remote_only: Optional[bool] = Field(None, description="Remote work only preference")
    employment_types: Optional[List[str]] = Field(None, description="Preferred employment types")
    experience_levels: Optional[List[str]] = Field(None, description="Preferred experience levels")
    salary_min: Optional[int] = Field(None, description="Minimum salary expectation")
    salary_max: Optional[int] = Field(None, description="Maximum salary expectation")
    company_sizes: Optional[List[str]] = Field(None, description="Preferred company sizes")
    industries: Optional[List[str]] = Field(None, description="Preferred industries")

    class Config:
        json_schema_extra = {
            "example": {
                "keywords": ["python", "fastapi", "backend"],
                "locations": ["San Francisco", "Remote"],
                "remote_only": False,
                "employment_types": ["full_time", "contract"],
                "experience_levels": ["mid", "senior"],
                "salary_min": 90000,
                "salary_max": 150000,
                "company_sizes": ["medium", "large"],
                "industries": ["technology", "finance"]
            }
        }


class SearchConfigurationUpdateDTO(BaseModel):
    """DTO for updating search configuration."""
    auto_apply: Optional[bool] = Field(None, description="Enable automatic job applications")
    notification_frequency: Optional[str] = Field(None, description="Notification frequency")
    max_applications_per_day: Optional[int] = Field(None, description="Maximum applications per day")
    search_radius: Optional[int] = Field(None, description="Search radius in miles")
    job_age_days: Optional[int] = Field(None, description="Maximum job posting age in days")

    class Config:
        json_schema_extra = {
            "example": {
                "auto_apply": False,
                "notification_frequency": "daily",
                "max_applications_per_day": 5,
                "search_radius": 25,
                "job_age_days": 7
            }
        }


class SearchPreferencesResponseDTO(BaseModel):
    """DTO for search preferences response."""
    keywords: List[str]
    locations: List[str]
    remote_only: bool
    employment_types: List[str]
    experience_levels: List[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    company_sizes: List[str]
    industries: List[str]
    auto_apply: bool
    notification_frequency: str
    max_applications_per_day: int
    search_radius: int
    job_age_days: int
    updated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "keywords": ["python", "fastapi", "backend"],
                "locations": ["San Francisco", "Remote"],
                "remote_only": False,
                "employment_types": ["full_time", "contract"],
                "experience_levels": ["mid", "senior"],
                "salary_min": 90000,
                "salary_max": 150000,
                "company_sizes": ["medium", "large"],
                "industries": ["technology", "finance"],
                "auto_apply": False,
                "notification_frequency": "daily",
                "max_applications_per_day": 5,
                "search_radius": 25,
                "job_age_days": 7,
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }