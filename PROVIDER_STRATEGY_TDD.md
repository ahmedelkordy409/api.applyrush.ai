# Provider Strategy Pattern - Auto Apply Module (TDD)

## Design Pattern: Strategy Pattern for Provider-Specific Application

### Problem Statement
Different job platforms (Greenhouse, Lever, Workday, LinkedIn, Indeed) have different:
- Form structures
- Question types
- Multi-step workflows
- Authentication requirements
- CAPTCHA implementations

### Solution: Strategy Pattern + AI Form Filling

## Architecture Overview

```
ApplicationContext
    ├── Provider Strategy (Abstract)
    │   ├── GreenhouseStrategy
    │   ├── LeverStrategy
    │   ├── WorkdayStrategy
    │   ├── LinkedInEasyApplyStrategy
    │   ├── IndeedQuickApplyStrategy
    │   └── GenericATSStrategy
    │
    └── AI Form Filler
        ├── ChatGPT Integration
        ├── Claude Integration
        └── Question Parser
```

## TDD Test Cases

### 1. Strategy Pattern Tests

#### Test 1.1: Provider Detection
```python
def test_detect_greenhouse_from_url():
    """Should detect Greenhouse ATS from URL"""
    url = "https://boards.greenhouse.io/company/jobs/123456"
    detector = ProviderDetector()

    provider = detector.detect_provider(url)

    assert provider == "greenhouse"
    assert detector.get_strategy(provider).__class__.__name__ == "GreenhouseStrategy"
```

#### Test 1.2: Strategy Selection
```python
def test_select_correct_strategy():
    """Should select correct strategy for provider"""
    context = ApplicationContext()

    # Test Greenhouse
    greenhouse_strategy = context.get_strategy_for_url(
        "https://boards.greenhouse.io/company/jobs/123"
    )
    assert isinstance(greenhouse_strategy, GreenhouseStrategy)

    # Test Lever
    lever_strategy = context.get_strategy_for_url(
        "https://jobs.lever.co/company/job-id"
    )
    assert isinstance(lever_strategy, LeverStrategy)

    # Test Workday
    workday_strategy = context.get_strategy_for_url(
        "https://company.wd1.myworkdayjobs.com/Careers"
    )
    assert isinstance(workday_strategy, WorkdayStrategy)
```

#### Test 1.3: Fallback to Generic Strategy
```python
def test_fallback_to_generic_strategy():
    """Should use generic strategy for unknown providers"""
    context = ApplicationContext()

    unknown_url = "https://careers.somecompany.com/apply"
    strategy = context.get_strategy_for_url(unknown_url)

    assert isinstance(strategy, GenericATSStrategy)
```

### 2. Form Detection Tests

#### Test 2.1: Detect Form Fields
```python
@pytest.mark.asyncio
async def test_detect_greenhouse_form_fields():
    """Should detect all form fields in Greenhouse application"""
    strategy = GreenhouseStrategy()
    page = await browser.new_page()
    await page.goto("https://boards.greenhouse.io/test/jobs/123")

    fields = await strategy.detect_form_fields(page)

    assert "first_name" in fields
    assert "last_name" in fields
    assert "email" in fields
    assert "phone" in fields
    assert "resume" in fields
```

#### Test 2.2: Detect Custom Questions
```python
@pytest.mark.asyncio
async def test_detect_custom_questions():
    """Should detect and categorize custom application questions"""
    strategy = GreenhouseStrategy()
    page = await browser.new_page()
    await page.goto("https://boards.greenhouse.io/test/jobs/123")

    questions = await strategy.detect_custom_questions(page)

    assert len(questions) > 0
    assert questions[0]["type"] in ["text", "select", "multi_select", "yes_no"]
    assert "question_text" in questions[0]
```

#### Test 2.3: Multi-Step Form Detection
```python
@pytest.mark.asyncio
async def test_detect_multi_step_form():
    """Should detect multi-step application workflow"""
    strategy = WorkdayStrategy()
    page = await browser.new_page()
    await page.goto("https://company.wd1.myworkdayjobs.com/test")

    steps = await strategy.detect_steps(page)

    assert len(steps) >= 1
    assert steps[0]["step_number"] == 1
    assert "next_button_selector" in steps[0]
```

### 3. AI Form Filling Tests

#### Test 3.1: AI Question Answering
```python
@pytest.mark.asyncio
async def test_ai_answers_why_interested_question():
    """Should generate contextual answer using AI"""
    ai_filler = AIFormFiller(provider="openai", model="gpt-4")

    question = {
        "text": "Why are you interested in this position?",
        "type": "textarea",
        "max_length": 500
    }

    context = {
        "user_name": "John Doe",
        "job_title": "Senior Python Developer",
        "company_name": "Tech Corp",
        "user_skills": ["Python", "Django", "PostgreSQL"],
        "user_experience": "5 years"
    }

    answer = await ai_filler.answer_question(question, context)

    assert len(answer) <= 500
    assert len(answer) > 50  # Not too short
    assert "Tech Corp" in answer or "position" in answer
    assert isinstance(answer, str)
```

#### Test 3.2: Yes/No Question Logic
```python
@pytest.mark.asyncio
async def test_ai_answers_yes_no_questions():
    """Should answer yes/no questions intelligently"""
    ai_filler = AIFormFiller()

    # Test authorization question
    question1 = {
        "text": "Are you authorized to work in the United States?",
        "type": "yes_no"
    }
    context = {"work_authorization": "US Citizen"}
    answer1 = await ai_filler.answer_question(question1, context)
    assert answer1 == "yes"

    # Test sponsorship question
    question2 = {
        "text": "Do you require visa sponsorship?",
        "type": "yes_no"
    }
    context = {"visa_sponsorship_required": False}
    answer2 = await ai_filler.answer_question(question2, context)
    assert answer2 == "no"
```

#### Test 3.3: Dropdown Selection
```python
@pytest.mark.asyncio
async def test_ai_selects_from_dropdown():
    """Should select appropriate option from dropdown"""
    ai_filler = AIFormFiller()

    question = {
        "text": "How did you hear about us?",
        "type": "select",
        "options": ["LinkedIn", "Indeed", "Company Website", "Referral", "Other"]
    }

    context = {"application_source": "Indeed"}

    answer = await ai_filler.answer_question(question, context)

    assert answer in question["options"]
    assert answer == "Indeed"
```

#### Test 3.4: Years of Experience
```python
@pytest.mark.asyncio
async def test_ai_calculates_years_experience():
    """Should calculate years of experience for specific skills"""
    ai_filler = AIFormFiller()

    question = {
        "text": "How many years of Python experience do you have?",
        "type": "number",
        "min": 0,
        "max": 20
    }

    context = {
        "skills": [
            {"name": "Python", "years": 5},
            {"name": "JavaScript", "years": 3}
        ]
    }

    answer = await ai_filler.answer_question(question, context)

    assert answer == 5
    assert isinstance(answer, int)
```

### 4. Provider-Specific Tests

#### Test 4.1: Greenhouse Application Flow
```python
@pytest.mark.asyncio
async def test_greenhouse_full_application():
    """Should complete full Greenhouse application"""
    strategy = GreenhouseStrategy()
    ai_filler = AIFormFiller()

    user_data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "555-1234",
        "resume_path": "/path/to/resume.pdf"
    }

    job_data = {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "url": "https://boards.greenhouse.io/techcorp/jobs/123"
    }

    result = await strategy.apply(
        page=page,
        user_data=user_data,
        job_data=job_data,
        ai_filler=ai_filler
    )

    assert result["success"] == True
    assert result["steps_completed"] > 0
    assert "screenshot_path" in result
```

#### Test 4.2: Lever Application Flow
```python
@pytest.mark.asyncio
async def test_lever_full_application():
    """Should complete full Lever application"""
    strategy = LeverStrategy()
    ai_filler = AIFormFiller()

    # Similar to Greenhouse test but Lever-specific
    result = await strategy.apply(page, user_data, job_data, ai_filler)

    assert result["success"] == True
    assert result["provider"] == "lever"
```

#### Test 4.3: LinkedIn Easy Apply
```python
@pytest.mark.asyncio
async def test_linkedin_easy_apply():
    """Should complete LinkedIn Easy Apply (human-approval required)"""
    strategy = LinkedInEasyApplyStrategy()
    strategy.set_mode("human_approval")  # Safe mode

    result = await strategy.apply(page, user_data, job_data, ai_filler)

    assert result["status"] == "pending_approval"
    assert result["fields_filled"] > 0
    assert result["requires_human_review"] == True
```

### 5. Error Handling Tests

#### Test 5.1: Handle Missing Fields
```python
@pytest.mark.asyncio
async def test_handle_missing_required_fields():
    """Should handle missing required user data gracefully"""
    strategy = GreenhouseStrategy()

    incomplete_user_data = {
        "first_name": "John",
        # Missing last_name, email, etc.
    }

    result = await strategy.apply(page, incomplete_user_data, job_data, ai_filler)

    assert result["success"] == False
    assert "missing_fields" in result
    assert "last_name" in result["missing_fields"]
```

#### Test 5.2: Handle CAPTCHA Blocking
```python
@pytest.mark.asyncio
async def test_handle_captcha_detected():
    """Should detect and report CAPTCHA"""
    strategy = GreenhouseStrategy()

    # Mock page with CAPTCHA
    result = await strategy.apply(page_with_captcha, user_data, job_data, ai_filler)

    assert result["success"] == False
    assert result["error_type"] == "captcha_detected"
    assert "captcha_url" in result
```

#### Test 5.3: Handle Timeout
```python
@pytest.mark.asyncio
async def test_handle_page_timeout():
    """Should timeout gracefully after max wait"""
    strategy = GreenhouseStrategy()
    strategy.set_timeout(5000)  # 5 seconds

    # Mock slow-loading page
    result = await strategy.apply(slow_page, user_data, job_data, ai_filler)

    assert result["success"] == False
    assert result["error_type"] == "timeout"
```

### 6. Integration Tests

#### Test 6.1: End-to-End Application
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_application_with_ai():
    """Should complete full application from URL to submission"""
    context = ApplicationContext()
    ai_filler = AIFormFiller(provider="openai")

    job_url = "https://boards.greenhouse.io/techcorp/jobs/123456"

    result = await context.apply_to_job(
        job_url=job_url,
        user_data=full_user_data,
        ai_enabled=True
    )

    assert result["success"] == True
    assert result["provider"] == "greenhouse"
    assert result["ai_questions_answered"] > 0
    assert result["fields_filled"] > 5
```

#### Test 6.2: Provider Switching
```python
@pytest.mark.asyncio
async def test_switch_providers_mid_application():
    """Should detect provider change (redirect) and switch strategy"""
    context = ApplicationContext()

    # Start with company career page
    initial_url = "https://company.com/careers/job/123"

    # Redirects to Workday
    result = await context.apply_to_job(
        job_url=initial_url,
        user_data=user_data
    )

    assert result["provider_detected"] == "workday"
    assert result["provider_switched"] == True
    assert result["original_url"] != result["final_url"]
```

### 7. AI Provider Tests

#### Test 7.1: OpenAI Integration
```python
@pytest.mark.asyncio
async def test_openai_form_filling():
    """Should use OpenAI GPT-4 for form filling"""
    ai_filler = AIFormFiller(provider="openai", model="gpt-4")

    answer = await ai_filler.answer_question(complex_question, context)

    assert answer is not None
    assert len(answer) > 0
    assert ai_filler.api_calls_made > 0
```

#### Test 7.2: Claude Integration
```python
@pytest.mark.asyncio
async def test_claude_form_filling():
    """Should use Claude for form filling"""
    ai_filler = AIFormFiller(provider="anthropic", model="claude-3-5-sonnet")

    answer = await ai_filler.answer_question(complex_question, context)

    assert answer is not None
    assert len(answer) > 0
```

#### Test 7.3: Fallback Between Providers
```python
@pytest.mark.asyncio
async def test_fallback_to_backup_ai_provider():
    """Should fallback to backup AI provider on failure"""
    ai_filler = AIFormFiller(
        primary_provider="openai",
        fallback_provider="anthropic"
    )

    # Mock OpenAI failure
    with mock.patch.object(ai_filler, '_call_openai', side_effect=Exception("API Error")):
        answer = await ai_filler.answer_question(question, context)

    assert answer is not None  # Should use Claude fallback
    assert ai_filler.fallback_used == True
```

## Implementation Structure

```python
# Base Strategy Interface
class ApplicationStrategy(ABC):
    @abstractmethod
    async def detect_provider(self, page: Page) -> bool:
        """Detect if page is this provider"""
        pass

    @abstractmethod
    async def detect_form_fields(self, page: Page) -> Dict[str, Any]:
        """Detect all form fields"""
        pass

    @abstractmethod
    async def fill_form(self, page: Page, data: Dict, ai_filler: AIFormFiller) -> bool:
        """Fill form with user data"""
        pass

    @abstractmethod
    async def submit_application(self, page: Page) -> Dict[str, Any]:
        """Submit application"""
        pass

# Concrete Strategies
class GreenhouseStrategy(ApplicationStrategy):
    URL_PATTERN = r"boards\.greenhouse\.io"

    async def detect_provider(self, page: Page) -> bool:
        return "greenhouse" in page.url.lower()

    async def detect_form_fields(self, page: Page) -> Dict[str, Any]:
        # Greenhouse-specific selectors
        fields = {
            "first_name": "input[name='job_application[first_name]']",
            "last_name": "input[name='job_application[last_name]']",
            "email": "input[name='job_application[email]']",
            # ...
        }
        return fields

# Context
class ApplicationContext:
    def __init__(self):
        self.strategies = {
            "greenhouse": GreenhouseStrategy(),
            "lever": LeverStrategy(),
            "workday": WorkdayStrategy(),
            "linkedin": LinkedInEasyApplyStrategy(),
            "indeed": IndeedQuickApplyStrategy(),
            "generic": GenericATSStrategy()
        }

    def get_strategy_for_url(self, url: str) -> ApplicationStrategy:
        for name, strategy in self.strategies.items():
            if re.search(strategy.URL_PATTERN, url):
                return strategy
        return self.strategies["generic"]

# AI Form Filler
class AIFormFiller:
    def __init__(self, provider="openai", model="gpt-4"):
        self.provider = provider
        self.model = model

    async def answer_question(
        self,
        question: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Use AI to answer application question"""

        prompt = self._build_prompt(question, context)

        if self.provider == "openai":
            answer = await self._call_openai(prompt, question["type"])
        elif self.provider == "anthropic":
            answer = await self._call_claude(prompt, question["type"])

        return self._validate_answer(answer, question)
```

## Test Coverage Goals

- Unit Tests: 80%+
- Integration Tests: 60%+
- E2E Tests: 40%+

## Run Tests

```bash
# Run all tests
pytest tests/test_provider_strategies.py -v

# Run specific provider
pytest tests/test_provider_strategies.py::test_greenhouse_full_application -v

# Run with coverage
pytest tests/test_provider_strategies.py --cov=app/services/providers --cov-report=html
```

---

**Status:** TDD Specification Complete
**Next Step:** Implement based on these test cases
**Date:** October 7, 2025
