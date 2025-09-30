"""
AI Model interfaces for JobHire.AI
Handles Replicate API integration and model management
"""

import replicate
import openai
from typing import Dict, Any, Optional, List
import json
import time
import asyncio
from app.core.config import settings
from app.core.monitoring import performance_monitor
import structlog

logger = structlog.get_logger()


class AIModelError(Exception):
    """Custom exception for AI model errors"""
    pass


class ModelTier:
    """Model tier configuration"""
    CHEAP = "cheap"          # Fast, low-cost models for simple tasks
    BALANCED = "balanced"    # Good performance/cost ratio
    PREMIUM = "premium"      # Highest quality for critical tasks


class AIModelManager:
    """Manages AI model interactions with cost optimization"""
    
    def __init__(self):
        self.replicate_client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
        self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Model configurations
        self.models = {
            ModelTier.CHEAP: {
                "replicate": "mistralai/mixtral-8x7b-instruct-v0.1",
                "openai": "gpt-3.5-turbo",
                "cost_per_token": 0.0000005,
                "max_tokens": 4000,
                "use_for": ["simple_matching", "quick_analysis"]
            },
            ModelTier.BALANCED: {
                "replicate": "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
                "openai": "gpt-4o-mini", 
                "cost_per_token": 0.000001,
                "max_tokens": 8000,
                "use_for": ["job_matching", "cover_letter", "resume_optimization"]
            },
            ModelTier.PREMIUM: {
                "replicate": "anthropic/claude-3-5-sonnet-20241022",
                "openai": "gpt-4o",
                "cost_per_token": 0.000015,
                "max_tokens": 128000,
                "use_for": ["complex_analysis", "premium_users", "critical_decisions"]
            }
        }
    
    async def generate_response(
        self,
        prompt: str,
        user_data: Dict[str, Any],
        model_tier: str = ModelTier.BALANCED,
        provider: str = "replicate",
        temperature: float = 0.7,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """Generate AI response with monitoring and error handling"""
        
        start_time = time.time()
        operation = f"{provider}_{model_tier}"
        
        try:
            if provider == "replicate":
                response = await self._generate_replicate_response(
                    prompt, model_tier, temperature, max_tokens
                )
            elif provider == "openai":
                response = await self._generate_openai_response(
                    prompt, model_tier, temperature, max_tokens
                )
            else:
                raise AIModelError(f"Unsupported provider: {provider}")
            
            # Record performance metrics
            processing_time = time.time() - start_time
            performance_monitor.record_ai_processing_time(
                model=self.models[model_tier][provider],
                operation=operation,
                duration=processing_time
            )
            
            # Calculate cost
            estimated_tokens = len(prompt.split()) + len(response.get("text", "").split())
            cost = estimated_tokens * self.models[model_tier]["cost_per_token"]
            
            return {
                "success": True,
                "response": response,
                "metadata": {
                    "model": self.models[model_tier][provider],
                    "processing_time": processing_time,
                    "estimated_tokens": estimated_tokens,
                    "cost_usd": cost,
                    "provider": provider,
                    "tier": model_tier
                }
            }
            
        except Exception as e:
            logger.error("AI model error", error=str(e), operation=operation)
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "processing_time": time.time() - start_time,
                    "provider": provider,
                    "tier": model_tier
                }
            }
    
    async def _generate_replicate_response(
        self,
        prompt: str,
        model_tier: str,
        temperature: float,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate response using Replicate API"""
        
        model_name = self.models[model_tier]["replicate"]
        if max_tokens is None:
            max_tokens = self.models[model_tier]["max_tokens"]
        
        # Run the model
        try:
            output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.replicate_client.run(
                    model_name,
                    input={
                        "prompt": prompt,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": 0.9
                    }
                )
            )
            
            # Handle different output formats
            if isinstance(output, list):
                text = "".join(output)
            elif isinstance(output, str):
                text = output
            else:
                text = str(output)
            
            return {
                "text": text,
                "model": model_name,
                "provider": "replicate"
            }
            
        except Exception as e:
            raise AIModelError(f"Replicate API error: {str(e)}")
    
    async def _generate_openai_response(
        self,
        prompt: str,
        model_tier: str,
        temperature: float,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        
        model_name = self.models[model_tier]["openai"]
        if max_tokens is None:
            max_tokens = self.models[model_tier]["max_tokens"]
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                "text": response.choices[0].message.content,
                "model": model_name,
                "provider": "openai",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            raise AIModelError(f"OpenAI API error: {str(e)}")
    
    def select_optimal_model(
        self, 
        task_type: str, 
        user_tier: str = "free",
        complexity: str = "medium"
    ) -> tuple[str, str]:
        """Select optimal model based on task and user tier"""
        
        # Premium users get premium models for complex tasks
        if user_tier == "premium" and complexity in ["high", "critical"]:
            return ModelTier.PREMIUM, "replicate"
        
        # Balanced model for most tasks
        if task_type in ["job_matching", "cover_letter", "resume_optimization"]:
            return ModelTier.BALANCED, "replicate"
        
        # Cheap model for simple tasks
        if task_type in ["simple_analysis", "quick_classification"]:
            return ModelTier.CHEAP, "replicate"
        
        # Default
        return ModelTier.BALANCED, "replicate"
    
    async def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from AI model with error handling"""
        try:
            # Clean the response text
            text = response_text.strip()
            
            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            # Parse JSON
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON", error=str(e), response=response_text[:200])
            raise AIModelError(f"Invalid JSON response from AI model: {str(e)}")


# Global AI model manager instance
ai_model_manager = AIModelManager()


# Convenience functions for specific AI operations
async def generate_job_match_analysis(
    job_data: Dict[str, Any],
    user_profile: Dict[str, Any],
    user_tier: str = "free"
) -> Dict[str, Any]:
    """Generate job matching analysis"""
    from app.ai.prompts import AIPrompts, PromptType
    
    prompt = AIPrompts.format_prompt(
        PromptType.JOB_MATCHING,
        job_description=job_data.get("description", ""),
        resume=user_profile.get("resume_text", ""),
        skills=user_profile.get("skills", []),
        experience=user_profile.get("experience_years", 0),
        preferences=user_profile.get("preferences", {}),
        past_applications=user_profile.get("past_applications", []),
        success_rates=user_profile.get("success_rates", {})
    )
    
    model_tier, provider = ai_model_manager.select_optimal_model("job_matching", user_tier)
    result = await ai_model_manager.generate_response(prompt, user_profile, model_tier, provider)
    
    if result["success"]:
        parsed_response = await ai_model_manager.parse_json_response(result["response"]["text"])
        return {
            "success": True,
            "analysis": parsed_response,
            "metadata": result["metadata"]
        }
    else:
        return result


async def generate_cover_letter(
    job_data: Dict[str, Any],
    user_profile: Dict[str, Any],
    company_research: Dict[str, Any] = None,
    user_tier: str = "free"
) -> Dict[str, Any]:
    """Generate personalized cover letter"""
    from app.ai.prompts import AIPrompts, PromptType
    
    prompt = AIPrompts.format_prompt(
        PromptType.COVER_LETTER,
        job_title=job_data.get("title", ""),
        company_name=job_data.get("company", {}).get("name", ""),
        job_description=job_data.get("description", ""),
        resume=user_profile.get("resume_text", ""),
        company_culture=company_research.get("culture", "") if company_research else "",
        recent_news=company_research.get("news", "") if company_research else "",
        values=company_research.get("values", "") if company_research else "",
        skills_alignment=job_data.get("skills_match", ""),
        experience_relevance=job_data.get("experience_match", "")
    )
    
    model_tier, provider = ai_model_manager.select_optimal_model("cover_letter", user_tier)
    result = await ai_model_manager.generate_response(prompt, user_profile, model_tier, provider)
    
    if result["success"]:
        parsed_response = await ai_model_manager.parse_json_response(result["response"]["text"])
        return {
            "success": True,
            "cover_letter": parsed_response,
            "metadata": result["metadata"]
        }
    else:
        return result


# Export public interfaces
__all__ = [
    "AIModelManager", 
    "ModelTier", 
    "AIModelError",
    "ai_model_manager",
    "generate_job_match_analysis",
    "generate_cover_letter"
]