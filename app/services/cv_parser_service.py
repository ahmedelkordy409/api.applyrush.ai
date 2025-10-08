"""
ATS-Optimized CV Parser and Generator
Parses resumes, calculates ATS scores, and optimizes for applicant tracking systems
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
import PyPDF2
import pdfplumber
import replicate
from app.core.config import settings

logger = logging.getLogger(__name__)


class CVParserService:
    """
    Parse resumes and optimize for ATS
    """

    def __init__(self, db):
        self.db = db

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF using multiple methods for accuracy
        """
        text = ""

        try:
            # Method 1: pdfplumber (better for complex layouts)
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            # If pdfplumber fails, fall back to PyPDF2
            if not text.strip():
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            raise ValueError(f"Could not extract text from PDF: {str(e)}")

        return text.strip()

    def parse_resume_with_ai(self, resume_text: str) -> Dict:
        """
        Use Replicate AI to parse resume into structured data
        """
        system_prompt = "You are an expert resume parser. Extract information accurately and return only valid JSON."

        user_prompt = f"""
Parse the following resume and extract structured information in JSON format.

Resume:
{resume_text}

Extract the following information:
1. Personal Information:
   - full_name
   - email
   - phone
   - location (city, state)
   - linkedin_url
   - github_url
   - portfolio_url

2. Professional Summary (2-3 sentences)

3. Work Experience (array of objects):
   - company
   - position
   - start_date (MM/YYYY format)
   - end_date (MM/YYYY or "Present")
   - location
   - description (bullet points as array)

4. Education (array of objects):
   - institution
   - degree
   - field_of_study
   - graduation_date (MM/YYYY)
   - gpa (if mentioned)

5. Skills (categorized):
   - technical_skills (array)
   - soft_skills (array)
   - languages (array)
   - tools (array)

6. Certifications (array of objects):
   - name
   - issuer
   - date
   - credential_id

7. Projects (array of objects):
   - name
   - description
   - technologies (array)
   - url

Return ONLY valid JSON, no additional text.
"""

        try:
            import json
            import os

            # Set Replicate API token
            os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN

            # Use Llama model from Replicate (Claude not available on Replicate)
            output = replicate.run(
                settings.DEFAULT_MODEL,
                input={
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "top_p": 0.9,
                    "top_k": 50
                }
            )

            # Concatenate the output
            response_text = "".join(output)

            # Extract JSON from response (in case there's extra text)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed_data = json.loads(json_str)
            else:
                parsed_data = json.loads(response_text)

            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing resume with AI: {str(e)}")
            raise ValueError(f"Could not parse resume: {str(e)}")

    def calculate_ats_score(self, resume_text: str, job_description: Optional[str] = None) -> Dict:
        """
        Calculate ATS compatibility score (0-100)
        Based on multiple factors
        """
        score = 0
        max_score = 100
        issues = []
        recommendations = []

        # 1. Length check (15 points)
        word_count = len(resume_text.split())
        if 400 <= word_count <= 800:
            score += 15
        elif 300 <= word_count < 400 or 800 < word_count <= 1000:
            score += 10
            issues.append("Resume length not optimal")
            recommendations.append("Aim for 400-800 words for best ATS compatibility")
        else:
            score += 5
            issues.append("Resume too short or too long")
            recommendations.append("Significantly adjust resume length (target: 400-800 words)")

        # 2. Contact information (10 points)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'

        if re.search(email_pattern, resume_text):
            score += 5
        else:
            issues.append("Email not found")
            recommendations.append("Add a clear email address")

        if re.search(phone_pattern, resume_text):
            score += 5
        else:
            issues.append("Phone number not found")
            recommendations.append("Add a clear phone number")

        # 3. Section headers (15 points)
        required_sections = [
            r'\b(experience|work experience|employment)\b',
            r'\b(education)\b',
            r'\b(skills)\b'
        ]

        sections_found = 0
        for pattern in required_sections:
            if re.search(pattern, resume_text, re.IGNORECASE):
                sections_found += 1

        score += (sections_found / len(required_sections)) * 15
        if sections_found < len(required_sections):
            issues.append(f"Missing {len(required_sections) - sections_found} key sections")
            recommendations.append("Include sections: Experience, Education, Skills")

        # 4. Quantifiable achievements (20 points)
        numbers_pattern = r'\b\d+[%]?\b'
        numbers_found = len(re.findall(numbers_pattern, resume_text))

        if numbers_found >= 10:
            score += 20
        elif numbers_found >= 5:
            score += 15
            recommendations.append("Add more quantifiable achievements (numbers, percentages)")
        else:
            score += 5
            issues.append("Lacks quantifiable achievements")
            recommendations.append("Add metrics and numbers to demonstrate impact")

        # 5. Action verbs (15 points)
        action_verbs = [
            'achieved', 'managed', 'led', 'developed', 'created', 'designed',
            'implemented', 'improved', 'increased', 'reduced', 'delivered',
            'launched', 'optimized', 'streamlined', 'automated', 'built'
        ]

        verbs_found = sum(1 for verb in action_verbs if verb in resume_text.lower())

        if verbs_found >= 8:
            score += 15
        elif verbs_found >= 5:
            score += 10
            recommendations.append("Use more strong action verbs")
        else:
            score += 5
            issues.append("Insufficient action verbs")
            recommendations.append("Start bullet points with strong action verbs")

        # 6. Keyword matching with job description (25 points)
        if job_description:
            job_keywords = self._extract_keywords(job_description)
            resume_keywords = self._extract_keywords(resume_text)

            matched_keywords = set(job_keywords) & set(resume_keywords)
            keyword_match_rate = len(matched_keywords) / len(job_keywords) if job_keywords else 0

            keyword_score = keyword_match_rate * 25
            score += keyword_score

            if keyword_match_rate < 0.5:
                issues.append("Low keyword match with job description")
                recommendations.append(f"Include these keywords: {', '.join(list(set(job_keywords) - matched_keywords)[:5])}")

        # Ensure score doesn't exceed 100
        score = min(score, max_score)

        # Determine grade
        if score >= 80:
            grade = "A - Excellent ATS compatibility"
        elif score >= 70:
            grade = "B - Good ATS compatibility"
        elif score >= 60:
            grade = "C - Fair ATS compatibility"
        else:
            grade = "D - Poor ATS compatibility"

        return {
            "score": round(score, 1),
            "grade": grade,
            "word_count": word_count,
            "issues": issues,
            "recommendations": recommendations,
            "metrics_found": numbers_found,
            "action_verbs_found": verbs_found
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract important keywords from text
        """
        # Common tech keywords
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'node', 'aws', 'docker',
            'kubernetes', 'sql', 'nosql', 'mongodb', 'postgresql', 'git',
            'agile', 'scrum', 'ci/cd', 'microservices', 'api', 'rest',
            'graphql', 'typescript', 'vue', 'angular', 'django', 'flask',
            'fastapi', 'spring', 'redis', 'elasticsearch', 'kafka'
        ]

        text_lower = text.lower()
        found_keywords = [kw for kw in tech_keywords if kw in text_lower]

        # Extract other potential keywords (2+ chars, appears 2+ times)
        words = re.findall(r'\b[a-z]{2,}\b', text_lower)
        word_freq = {}
        for word in words:
            if word not in ['the', 'and', 'for', 'with', 'that', 'this']:
                word_freq[word] = word_freq.get(word, 0) + 1

        frequent_words = [word for word, count in word_freq.items() if count >= 2]

        return list(set(found_keywords + frequent_words))

    def optimize_resume(self, resume_text: str, job_description: str) -> Dict:
        """
        Optimize resume for specific job description using AI
        """
        system_prompt = "You are an expert resume optimizer specializing in ATS optimization."

        user_prompt = f"""
Given a resume and job description, optimize the resume to maximize ATS score while keeping it truthful.

Original Resume:
{resume_text}

Job Description:
{job_description}

Optimize the resume by:
1. Incorporating relevant keywords from job description naturally
2. Quantifying achievements where possible
3. Using strong action verbs
4. Ensuring proper formatting for ATS
5. Highlighting relevant experience

Return the optimized resume in plain text format with clear sections.
"""

        try:
            import os

            # Set Replicate API token
            os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN

            # Use Llama model from Replicate (Claude not available on Replicate)
            output = replicate.run(
                settings.DEFAULT_MODEL,
                input={
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "top_p": 0.9,
                    "top_k": 50
                }
            )

            # Concatenate the output
            optimized_text = "".join(output)

            # Calculate improvement
            original_score = self.calculate_ats_score(resume_text, job_description)
            optimized_score = self.calculate_ats_score(optimized_text, job_description)

            return {
                "optimized_text": optimized_text,
                "original_score": original_score["score"],
                "optimized_score": optimized_score["score"],
                "improvement": round(optimized_score["score"] - original_score["score"], 1),
                "recommendations": optimized_score["recommendations"]
            }

        except Exception as e:
            logger.error(f"Error optimizing resume: {str(e)}")
            raise ValueError(f"Could not optimize resume: {str(e)}")

    def save_parsed_resume(self, user_id: str, pdf_path: str, filename: str) -> Dict:
        """
        Parse and save resume to database
        """
        # Extract text
        resume_text = self.extract_text_from_pdf(pdf_path)

        # Parse with AI
        parsed_data = self.parse_resume_with_ai(resume_text)

        # Calculate ATS score
        ats_analysis = self.calculate_ats_score(resume_text)

        # Create resume document
        resume_doc = {
            "user_id": ObjectId(user_id),
            "filename": filename,
            "file_path": pdf_path,
            "raw_text": resume_text,
            "parsed_data": parsed_data,
            "ats_score": ats_analysis["score"],
            "ats_grade": ats_analysis["grade"],
            "ats_analysis": ats_analysis,
            "is_primary": True,  # Set as primary resume
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Set all other resumes as non-primary
        self.db.resumes.update_many(
            {"user_id": ObjectId(user_id)},
            {"$set": {"is_primary": False}}
        )

        # Insert new resume
        result = self.db.resumes.insert_one(resume_doc)
        resume_doc["_id"] = result.inserted_id

        logger.info(f"Saved resume {resume_doc['_id']} for user {user_id} with ATS score: {ats_analysis['score']}")

        return resume_doc

    def generate_tailored_resume(self, user_id: str, job_id: str) -> Dict:
        """
        Generate job-specific optimized resume
        """
        # Get user's primary resume
        primary_resume = self.db.resumes.find_one({
            "user_id": ObjectId(user_id),
            "is_primary": True
        })

        if not primary_resume:
            raise ValueError("No primary resume found")

        # Get job details
        job = self.db.jobs.find_one({"_id": ObjectId(job_id)})

        if not job:
            raise ValueError("Job not found")

        # Build job description
        job_description = f"""
{job.get('title', '')}
{job.get('description', '')}

Required Skills: {', '.join(job.get('skills_required', []))}
Experience Required: {job.get('experience_years_min', 0)}+ years
"""

        # Optimize resume for this job
        optimized = self.optimize_resume(primary_resume["raw_text"], job_description)

        # Save tailored resume
        tailored_resume_doc = {
            "user_id": ObjectId(user_id),
            "job_id": ObjectId(job_id),
            "based_on_resume_id": primary_resume["_id"],
            "optimized_text": optimized["optimized_text"],
            "original_ats_score": optimized["original_score"],
            "optimized_ats_score": optimized["optimized_score"],
            "improvement": optimized["improvement"],
            "created_at": datetime.utcnow()
        }

        result = self.db.resumes.insert_one(tailored_resume_doc)
        tailored_resume_doc["_id"] = result.inserted_id

        logger.info(f"Generated tailored resume {tailored_resume_doc['_id']} for job {job_id}, ATS improvement: +{optimized['improvement']}%")

        return tailored_resume_doc
