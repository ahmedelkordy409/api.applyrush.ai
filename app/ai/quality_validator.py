"""
AI Output Quality Validator
Ensures AI responses meet production quality standards
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
import asyncio
from datetime import datetime
import statistics

import structlog

logger = structlog.get_logger()


class QualityLevel(Enum):
    """Quality assessment levels"""
    EXCELLENT = "excellent"     # 90-100%
    GOOD = "good"              # 80-89%
    ACCEPTABLE = "acceptable"   # 70-79%
    POOR = "poor"              # 50-69%
    UNACCEPTABLE = "unacceptable"  # 0-49%


class ValidationError(Exception):
    """AI output validation error"""
    pass


class AIQualityValidator:
    """Validates AI outputs for production quality"""
    
    def __init__(self):
        self.quality_thresholds = {
            QualityLevel.EXCELLENT: 90,
            QualityLevel.GOOD: 80,
            QualityLevel.ACCEPTABLE: 70,
            QualityLevel.POOR: 50,
            QualityLevel.UNACCEPTABLE: 0
        }
        
        # Quality metrics weights
        self.metric_weights = {
            "structure_completeness": 0.25,
            "data_accuracy": 0.30,
            "logical_consistency": 0.20,
            "response_relevance": 0.15,
            "format_compliance": 0.10
        }
        
        # Response format validators
        self.format_validators = {
            "job_matching": self._validate_job_matching_format,
            "cover_letter": self._validate_cover_letter_format,
            "auto_apply_decision": self._validate_auto_apply_format,
            "resume_optimization": self._validate_resume_format
        }

    async def validate_ai_response(
        self,
        response_type: str,
        ai_output: str,
        input_data: Dict[str, Any],
        expected_schema: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of AI response quality
        """
        
        validation_start = datetime.utcnow()
        
        try:
            # Parse AI response
            parsed_response = await self._parse_ai_response(ai_output)
            
            # Run all validation checks
            validation_results = await self._run_validation_suite(
                response_type, parsed_response, input_data, expected_schema
            )
            
            # Calculate overall quality score
            quality_score = self._calculate_quality_score(validation_results)
            quality_level = self._determine_quality_level(quality_score)
            
            # Generate quality report
            quality_report = {
                "validation_passed": quality_level != QualityLevel.UNACCEPTABLE,
                "quality_score": quality_score,
                "quality_level": quality_level.value,
                "validation_results": validation_results,
                "recommendations": self._generate_quality_recommendations(validation_results),
                "metadata": {
                    "response_type": response_type,
                    "validation_time_ms": (datetime.utcnow() - validation_start).total_seconds() * 1000,
                    "response_length": len(ai_output),
                    "parsed_successfully": parsed_response is not None
                }
            }
            
            # Log quality issues if any
            if quality_level in [QualityLevel.POOR, QualityLevel.UNACCEPTABLE]:
                logger.warning("AI response quality issues detected",
                              type=response_type,
                              quality_score=quality_score,
                              issues=validation_results.get("issues", []))
            
            return quality_report
            
        except Exception as e:
            logger.error("AI response validation failed", error=str(e))
            return {
                "validation_passed": False,
                "quality_score": 0,
                "quality_level": QualityLevel.UNACCEPTABLE.value,
                "error": str(e),
                "metadata": {"response_type": response_type}
            }

    async def _parse_ai_response(self, ai_output: str) -> Optional[Dict[str, Any]]:
        """Parse AI response with multiple fallback strategies"""
        
        try:
            # Strategy 1: Direct JSON parsing
            return json.loads(ai_output)
        except json.JSONDecodeError:
            pass
        
        try:
            # Strategy 2: Extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
        
        try:
            # Strategy 3: Extract JSON from text (find first { to last })
            start_idx = ai_output.find('{')
            end_idx = ai_output.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = ai_output[start_idx:end_idx + 1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Parse as plain text response
        return {"raw_text": ai_output, "parsed_as_text": True}

    async def _run_validation_suite(
        self,
        response_type: str,
        parsed_response: Dict[str, Any],
        input_data: Dict[str, Any],
        expected_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run comprehensive validation suite"""
        
        validation_results = {
            "structure_completeness": await self._validate_structure_completeness(
                response_type, parsed_response, expected_schema
            ),
            "data_accuracy": await self._validate_data_accuracy(
                parsed_response, input_data
            ),
            "logical_consistency": await self._validate_logical_consistency(
                response_type, parsed_response
            ),
            "response_relevance": await self._validate_response_relevance(
                parsed_response, input_data
            ),
            "format_compliance": await self._validate_format_compliance(
                response_type, parsed_response
            )
        }
        
        # Collect all issues
        all_issues = []
        for check_name, check_result in validation_results.items():
            if check_result.get("issues"):
                all_issues.extend([f"{check_name}: {issue}" for issue in check_result["issues"]])
        
        validation_results["issues"] = all_issues
        validation_results["total_checks"] = len(validation_results) - 1  # Exclude 'issues'
        validation_results["passed_checks"] = sum(
            1 for k, v in validation_results.items() 
            if k != "issues" and k != "total_checks" and v.get("passed", False)
        )
        
        return validation_results

    async def _validate_structure_completeness(
        self,
        response_type: str,
        parsed_response: Dict[str, Any],
        expected_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that response has complete expected structure"""
        
        issues = []
        score = 100
        
        # Get expected fields for response type
        expected_fields = self._get_expected_fields(response_type)
        
        if not expected_fields and expected_schema:
            expected_fields = expected_schema.get("required_fields", [])
        
        # Check for missing required fields
        missing_fields = []
        for field in expected_fields:
            if field not in parsed_response:
                missing_fields.append(field)
                score -= 15  # Deduct 15 points per missing field
        
        if missing_fields:
            issues.append(f"Missing required fields: {missing_fields}")
        
        # Check for empty values in important fields
        empty_fields = []
        for field, value in parsed_response.items():
            if field in expected_fields and (value is None or value == "" or value == []):
                empty_fields.append(field)
                score -= 10  # Deduct 10 points per empty field
        
        if empty_fields:
            issues.append(f"Empty required fields: {empty_fields}")
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "missing_fields": missing_fields,
            "empty_fields": empty_fields,
            "issues": issues
        }

    async def _validate_data_accuracy(
        self,
        parsed_response: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate accuracy of data in response"""
        
        issues = []
        score = 100
        
        # Check score ranges
        if "overall_score" in parsed_response:
            overall_score = parsed_response["overall_score"]
            if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                issues.append(f"Invalid overall_score: {overall_score} (must be 0-100)")
                score -= 25
        
        # Check probability values
        if "success_probability" in parsed_response:
            prob = parsed_response["success_probability"]
            if not isinstance(prob, (int, float)) or not (0 <= prob <= 1):
                issues.append(f"Invalid success_probability: {prob} (must be 0-1)")
                score -= 20
        
        # Check priority values
        if "apply_priority" in parsed_response:
            priority = parsed_response["apply_priority"]
            if not isinstance(priority, int) or not (1 <= priority <= 10):
                issues.append(f"Invalid apply_priority: {priority} (must be 1-10)")
                score -= 15
        
        # Check category scores consistency
        if "category_scores" in parsed_response:
            category_scores = parsed_response["category_scores"]
            if isinstance(category_scores, dict):
                for category, data in category_scores.items():
                    if isinstance(data, dict) and "score" in data:
                        cat_score = data["score"]
                        if not isinstance(cat_score, (int, float)) or not (0 <= cat_score <= 100):
                            issues.append(f"Invalid {category} score: {cat_score}")
                            score -= 10
        
        # Check data consistency with input
        if "matched_skills" in parsed_response and "skills" in input_data:
            matched_skills = parsed_response.get("matched_skills", [])
            user_skills = input_data.get("skills", [])
            
            # Check if matched skills are actually in user's skills
            invalid_matches = [skill for skill in matched_skills if skill not in user_skills]
            if invalid_matches:
                issues.append(f"Matched skills not in user profile: {invalid_matches}")
                score -= 15
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_logical_consistency(
        self,
        response_type: str,
        parsed_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate logical consistency within the response"""
        
        issues = []
        score = 100
        
        # Check score-recommendation consistency
        if "overall_score" in parsed_response and "recommendation" in parsed_response:
            overall_score = parsed_response["overall_score"]
            recommendation = parsed_response["recommendation"]
            
            expected_recommendation = self._score_to_recommendation(overall_score)
            if recommendation.lower() != expected_recommendation.lower():
                issues.append(
                    f"Inconsistent score-recommendation: {overall_score}% -> {recommendation} "
                    f"(expected {expected_recommendation})"
                )
                score -= 20
        
        # Check priority-score consistency
        if "overall_score" in parsed_response and "apply_priority" in parsed_response:
            overall_score = parsed_response["overall_score"]
            priority = parsed_response["apply_priority"]
            
            expected_priority = min(10, max(1, int(overall_score / 10)))
            if abs(priority - expected_priority) > 2:
                issues.append(
                    f"Inconsistent score-priority: {overall_score}% -> priority {priority} "
                    f"(expected ~{expected_priority})"
                )
                score -= 15
        
        # Check category scores vs overall score
        if "category_scores" in parsed_response and "overall_score" in parsed_response:
            category_scores = parsed_response["category_scores"]
            overall_score = parsed_response["overall_score"]
            
            if isinstance(category_scores, dict):
                # Calculate weighted average (simplified)
                cat_scores = []
                for category, data in category_scores.items():
                    if isinstance(data, dict) and "score" in data:
                        cat_scores.append(data["score"])
                
                if cat_scores:
                    avg_category_score = sum(cat_scores) / len(cat_scores)
                    if abs(overall_score - avg_category_score) > 20:
                        issues.append(
                            f"Inconsistent category vs overall scores: "
                            f"overall={overall_score}, avg_categories={avg_category_score:.1f}"
                        )
                        score -= 15
        
        # Check missing skills logic
        if ("matched_skills" in parsed_response and 
            "missing_skills" in parsed_response and
            "improvement_suggestions" in parsed_response):
            
            missing_skills = parsed_response.get("missing_skills", [])
            suggestions = parsed_response.get("improvement_suggestions", [])
            
            # Should have suggestions if there are missing skills
            if missing_skills and not suggestions:
                issues.append("Missing skills identified but no improvement suggestions provided")
                score -= 10
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_response_relevance(
        self,
        parsed_response: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that response is relevant to input"""
        
        issues = []
        score = 100
        
        # Check if response addresses the input job/candidate
        job_title = input_data.get("job_title", "")
        if job_title and "competitive_advantage" in parsed_response:
            advantage = parsed_response["competitive_advantage"]
            if isinstance(advantage, str) and len(advantage) < 20:
                issues.append("Competitive advantage too generic or short")
                score -= 15
        
        # Check skill relevance
        job_skills = input_data.get("required_skills", [])
        if job_skills and "matched_skills" in parsed_response:
            matched_skills = parsed_response["matched_skills"]
            
            # At least some matched skills should be from job requirements
            relevant_matches = [skill for skill in matched_skills if skill in job_skills]
            if matched_skills and not relevant_matches:
                issues.append("No matched skills are from job requirements")
                score -= 20
        
        # Check if suggestions are actionable
        if "improvement_suggestions" in parsed_response:
            suggestions = parsed_response["improvement_suggestions"]
            if isinstance(suggestions, list):
                generic_suggestions = [
                    s for s in suggestions 
                    if isinstance(s, str) and len(s) < 30
                ]
                if len(generic_suggestions) > len(suggestions) / 2:
                    issues.append("Too many generic improvement suggestions")
                    score -= 10
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_format_compliance(
        self,
        response_type: str,
        parsed_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate format compliance for specific response types"""
        
        if response_type in self.format_validators:
            return await self.format_validators[response_type](parsed_response)
        else:
            return {"passed": True, "score": 100, "issues": []}

    async def _validate_job_matching_format(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate job matching response format"""
        
        issues = []
        score = 100
        
        # Check required top-level fields
        required_fields = [
            "overall_score", "category_scores", "recommendation", 
            "apply_priority", "success_probability"
        ]
        
        for field in required_fields:
            if field not in response:
                issues.append(f"Missing required field: {field}")
                score -= 20
        
        # Check category_scores structure
        if "category_scores" in response:
            cat_scores = response["category_scores"]
            expected_categories = ["skills", "experience", "education", "location", "salary", "culture"]
            
            for category in expected_categories:
                if category not in cat_scores:
                    issues.append(f"Missing category score: {category}")
                    score -= 10
                elif not isinstance(cat_scores[category], dict) or "score" not in cat_scores[category]:
                    issues.append(f"Invalid category score format: {category}")
                    score -= 10
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_cover_letter_format(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cover letter response format"""
        
        issues = []
        score = 100
        
        # Check for cover letter content
        if "cover_letter" not in response:
            issues.append("Missing cover_letter field")
            score -= 30
        else:
            cover_letter = response["cover_letter"]
            if not isinstance(cover_letter, str) or len(cover_letter) < 200:
                issues.append("Cover letter too short (< 200 characters)")
                score -= 20
            elif len(cover_letter) > 2000:
                issues.append("Cover letter too long (> 2000 characters)")
                score -= 10
        
        # Check for metadata
        expected_metadata = ["key_points_highlighted", "keywords_included", "customization_score"]
        for field in expected_metadata:
            if field not in response:
                issues.append(f"Missing metadata field: {field}")
                score -= 10
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_auto_apply_format(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate auto-apply decision format"""
        
        issues = []
        score = 100
        
        # Check decision field
        if "decision" not in response:
            issues.append("Missing decision field")
            score -= 30
        else:
            decision = response["decision"]
            valid_decisions = ["APPLY", "SKIP", "REVIEW_REQUIRED"]
            if decision not in valid_decisions:
                issues.append(f"Invalid decision: {decision}")
                score -= 20
        
        # Check reasoning
        if "reasoning" not in response:
            issues.append("Missing reasoning field")
            score -= 20
        elif len(response["reasoning"]) < 20:
            issues.append("Reasoning too brief")
            score -= 10
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    async def _validate_resume_format(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resume optimization format"""
        
        issues = []
        score = 100
        
        if "optimized_resume" not in response:
            issues.append("Missing optimized_resume field")
            score -= 30
        
        if "changes_made" not in response:
            issues.append("Missing changes_made field")
            score -= 20
        
        if "ats_score" not in response:
            issues.append("Missing ats_score field")
            score -= 20
        
        return {
            "passed": score >= 70,
            "score": max(0, score),
            "issues": issues
        }

    def _calculate_quality_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall quality score from validation results"""
        
        weighted_score = 0
        for metric, weight in self.metric_weights.items():
            if metric in validation_results:
                metric_score = validation_results[metric].get("score", 0)
                weighted_score += metric_score * weight
        
        return round(weighted_score, 1)

    def _determine_quality_level(self, quality_score: float) -> QualityLevel:
        """Determine quality level from score"""
        
        for level, threshold in self.quality_thresholds.items():
            if quality_score >= threshold:
                return level
        
        return QualityLevel.UNACCEPTABLE

    def _generate_quality_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improving quality"""
        
        recommendations = []
        
        for metric, result in validation_results.items():
            if metric == "issues":
                continue
                
            if isinstance(result, dict) and result.get("score", 100) < 80:
                if metric == "structure_completeness":
                    recommendations.append("Ensure all required fields are present and non-empty")
                elif metric == "data_accuracy":
                    recommendations.append("Verify all numerical values are within valid ranges")
                elif metric == "logical_consistency":
                    recommendations.append("Check for logical consistency between scores and recommendations")
                elif metric == "response_relevance":
                    recommendations.append("Make response more specific and relevant to input data")
                elif metric == "format_compliance":
                    recommendations.append("Follow the expected response format more closely")
        
        if not recommendations:
            recommendations.append("Quality is good - continue maintaining current standards")
        
        return recommendations

    def _get_expected_fields(self, response_type: str) -> List[str]:
        """Get expected fields for response type"""
        
        field_mappings = {
            "job_matching": [
                "overall_score", "category_scores", "recommendation", 
                "apply_priority", "success_probability", "improvement_suggestions"
            ],
            "cover_letter": [
                "cover_letter", "key_points_highlighted", "keywords_included"
            ],
            "auto_apply_decision": [
                "decision", "reasoning", "confidence", "priority_score"
            ],
            "resume_optimization": [
                "optimized_resume", "changes_made", "ats_score"
            ]
        }
        
        return field_mappings.get(response_type, [])

    def _score_to_recommendation(self, score: float) -> str:
        """Convert score to expected recommendation"""
        
        if score >= 85:
            return "strong_match"
        elif score >= 70:
            return "good_match"
        elif score >= 50:
            return "possible_match"
        else:
            return "weak_match"


class QualityMetricsTracker:
    """Track quality metrics over time"""
    
    def __init__(self):
        self.quality_history = []
        self.metrics_by_type = {}
    
    def record_quality_result(self, response_type: str, quality_result: Dict[str, Any]):
        """Record a quality validation result"""
        
        timestamp = datetime.utcnow()
        
        record = {
            "timestamp": timestamp,
            "response_type": response_type,
            "quality_score": quality_result["quality_score"],
            "quality_level": quality_result["quality_level"],
            "validation_passed": quality_result["validation_passed"]
        }
        
        self.quality_history.append(record)
        
        # Track by type
        if response_type not in self.metrics_by_type:
            self.metrics_by_type[response_type] = []
        self.metrics_by_type[response_type].append(record)
        
        # Keep only last 1000 records
        if len(self.quality_history) > 1000:
            self.quality_history = self.quality_history[-1000:]
    
    def get_quality_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get quality trends over specified days"""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_records = [r for r in self.quality_history if r["timestamp"] >= cutoff]
        
        if not recent_records:
            return {"no_data": True}
        
        scores = [r["quality_score"] for r in recent_records]
        pass_rate = sum(1 for r in recent_records if r["validation_passed"]) / len(recent_records)
        
        trends_by_type = {}
        for response_type, records in self.metrics_by_type.items():
            type_recent = [r for r in records if r["timestamp"] >= cutoff]
            if type_recent:
                type_scores = [r["quality_score"] for r in type_recent]
                trends_by_type[response_type] = {
                    "avg_score": statistics.mean(type_scores),
                    "min_score": min(type_scores),
                    "max_score": max(type_scores),
                    "count": len(type_recent)
                }
        
        return {
            "period_days": days,
            "total_validations": len(recent_records),
            "avg_quality_score": statistics.mean(scores),
            "min_quality_score": min(scores),
            "max_quality_score": max(scores),
            "validation_pass_rate": pass_rate,
            "trends_by_type": trends_by_type
        }


# Global instances
ai_quality_validator = AIQualityValidator()
quality_metrics_tracker = QualityMetricsTracker()