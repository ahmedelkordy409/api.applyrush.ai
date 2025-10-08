"""
Resume Parser Service
Extracts information from resume files (PDF, DOCX, TXT)
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ResumeParserService:
    """Parse resume files and extract structured data"""

    def __init__(self):
        self.skills_database = self._load_skills_database()

    async def parse_resume(self, file_path: str) -> Dict[str, Any]:
        """
        Parse resume file and extract information

        Args:
            file_path: Path to resume file

        Returns:
            Dictionary with parsed data
        """
        try:
            # Extract text based on file type
            file_ext = Path(file_path).suffix.lower()

            if file_ext == '.pdf':
                text = await self._extract_text_from_pdf(file_path)
            elif file_ext in ['.docx', '.doc']:
                text = await self._extract_text_from_docx(file_path)
            elif file_ext == '.txt':
                text = await self._extract_text_from_txt(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")

            # Parse extracted text
            parsed_data = await self._parse_text(text)
            parsed_data['raw_text'] = text[:5000]  # Store first 5000 chars

            return parsed_data

        except Exception as e:
            logger.error(f"Failed to parse resume: {e}")
            return {
                "error": str(e),
                "raw_text": "",
                "name": None,
                "email": None,
                "phone": None,
                "skills": [],
                "experience_years": 0,
                "education": []
            }

    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(file_path)
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return ""

    async def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            import docx
            doc = docx.Document(file_path)
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from DOCX: {e}")
            return ""

    async def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to extract text from TXT: {e}")
            return ""

    async def _parse_text(self, text: str) -> Dict[str, Any]:
        """Parse extracted text and extract structured data"""

        parsed = {
            "name": self._extract_name(text),
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
            "skills": self._extract_skills(text),
            "experience_years": self._extract_experience_years(text),
            "education": self._extract_education(text),
            "summary": self._extract_summary(text)
        }

        return parsed

    def _extract_name(self, text: str) -> Optional[str]:
        """Extract name from resume text"""
        # Name is usually in first few lines
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            # Simple heuristic: line with 2-4 words, capitalized
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() if w else False for w in words):
                return line
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from resume text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from resume text"""
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
            r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # (123) 456-7890
            r'\b\+\d{1,3}\s*\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # +1 123-456-7890
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text"""
        text_lower = text.lower()
        found_skills = []

        for skill in self.skills_database:
            if skill.lower() in text_lower:
                found_skills.append(skill)

        return list(set(found_skills))[:50]  # Return up to 50 unique skills

    def _extract_experience_years(self, text: str) -> int:
        """Estimate years of experience from resume text"""
        # Look for patterns like "5 years of experience"
        patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'experience[:\s]+(\d+)\+?\s*years?',
        ]

        years = []
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                years.append(int(match.group(1)))

        return max(years) if years else 0

    def _extract_education(self, text: str) -> List[Dict[str, str]]:
        """Extract education information from resume text"""
        education = []

        # Common degree keywords
        degrees = [
            'Bachelor', 'Master', 'PhD', 'MBA', 'B.S.', 'M.S.', 'B.A.', 'M.A.',
            'B.Tech', 'M.Tech', 'Associate', 'Doctorate'
        ]

        lines = text.split('\n')
        for i, line in enumerate(lines):
            for degree in degrees:
                if degree.lower() in line.lower():
                    education.append({
                        "degree": degree,
                        "details": line.strip()
                    })
                    break

        return education[:5]  # Return up to 5 education entries

    def _extract_summary(self, text: str) -> Optional[str]:
        """Extract summary/objective from resume"""
        # Look for summary section
        summary_keywords = ['summary', 'objective', 'profile', 'about']

        lines = text.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in summary_keywords):
                # Get next 3-5 lines as summary
                summary_lines = lines[i+1:i+6]
                summary = ' '.join([l.strip() for l in summary_lines if l.strip()])
                return summary[:500] if summary else None

        return None

    def _load_skills_database(self) -> List[str]:
        """Load common technical skills database"""
        return [
            # Programming Languages
            'Python', 'JavaScript', 'Java', 'C++', 'C#', 'Ruby', 'Go', 'Rust',
            'TypeScript', 'PHP', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB',

            # Web Technologies
            'HTML', 'CSS', 'React', 'Angular', 'Vue.js', 'Node.js', 'Express',
            'Django', 'Flask', 'FastAPI', 'Spring Boot', 'Ruby on Rails',

            # Databases
            'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch',
            'DynamoDB', 'Cassandra', 'Oracle', 'SQL Server',

            # Cloud & DevOps
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'GitLab CI',
            'Terraform', 'Ansible', 'CircleCI', 'GitHub Actions',

            # Data Science & ML
            'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Scikit-learn',
            'Pandas', 'NumPy', 'Data Analysis', 'Data Visualization', 'Tableau',
            'Power BI', 'Apache Spark', 'Hadoop',

            # Tools & Frameworks
            'Git', 'Linux', 'REST API', 'GraphQL', 'Microservices', 'Agile', 'Scrum',
            'JIRA', 'Confluence', 'Slack', 'VS Code', 'IntelliJ',

            # Soft Skills
            'Leadership', 'Communication', 'Problem Solving', 'Team Collaboration',
            'Project Management', 'Analytical', 'Critical Thinking'
        ]
