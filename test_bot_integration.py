"""
Test script for bot integration
Tests the BotManager and LinkedInAIHawkAdapter
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_bot_manager():
    """Test BotManager platform detection and routing"""
    print("=" * 60)
    print("Testing Bot Manager Integration")
    print("=" * 60)

    from app.services.bots.bot_manager import BotManager

    bot_manager = BotManager()

    # Test platform detection
    test_urls = [
        ("https://www.linkedin.com/jobs/view/123456", "linkedin"),
        ("https://boards.greenhouse.io/company/jobs/123", "greenhouse"),
        ("https://jobs.lever.co/company/abc123", "lever"),
        ("https://company.wd5.myworkdayjobs.com/en-US/jobs", "workday"),
        ("https://www.indeed.com/viewjob?jk=123", "indeed"),
        ("https://example.com/careers/job/123", "generic"),
    ]

    print("\n✅ Testing Platform Detection:")
    for url, expected in test_urls:
        detected = await bot_manager.detect_platform(url)
        status = "✓" if detected == expected else "✗"
        print(f"{status} {url[:50]:<50} → {detected} (expected: {expected})")

    # Test bot availability
    print("\n✅ Available Bots:")
    for platform, bot in bot_manager.bots.items():
        status = "✓" if bot else "✗"
        bot_name = bot.__class__.__name__ if bot else "None"
        print(f"{status} {platform:<15} → {bot_name}")

    print("\n✅ Supported Platforms:")
    for platform, bot in bot_manager.bots.items():
        if bot:
            supported = bot.get_supported_platforms()
            print(f"  {platform}: {supported}")


async def test_linkedin_adapter():
    """Test LinkedInAIHawkAdapter (without actual application)"""
    print("\n" + "=" * 60)
    print("Testing LinkedIn AIHawk Adapter")
    print("=" * 60)

    from app.services.bots.linkedin_aihawk_adapter import LinkedInAIHawkAdapter

    adapter = LinkedInAIHawkAdapter()

    # Test supported platforms
    print("\n✅ Supported Platforms:")
    print(f"  {adapter.get_supported_platforms()}")

    # Test config conversion
    print("\n✅ Testing Config Conversion:")
    test_config = {
        "desired_positions": ["Software Engineer", "Data Scientist"],
        "preferred_locations": ["San Francisco, CA", "New York, NY"],
        "excluded_companies": ["Company A", "Company B"],
        "allow_contract": False,
        "allow_part_time": False,
        "llm_type": "openai",
        "llm_model": "gpt-4"
    }

    aihawk_config = adapter._convert_to_aihawk_config(test_config)
    print(f"  Positions: {aihawk_config['positions']}")
    print(f"  Locations: {aihawk_config['locations']}")
    print(f"  Company Blacklist: {aihawk_config['companyBlacklist']}")
    print(f"  LLM Model: {aihawk_config['llm_model']}")
    print(f"  Remote: {aihawk_config['remote']}")
    print(f"  Experience Levels: {sum(1 for v in aihawk_config['experienceLevel'].values() if v)}/{len(aihawk_config['experienceLevel'])}")

    print("\n⚠️  Note: Actual job application test requires:")
    print("  - Valid LinkedIn credentials")
    print("  - OpenAI/Anthropic API key")
    print("  - LinkedIn Easy Apply job URL")
    print("  - Risk of account ban")


async def test_bot_manager_application_flow():
    """Test the complete application flow (without actual submission)"""
    print("\n" + "=" * 60)
    print("Testing Complete Application Flow")
    print("=" * 60)

    from app.services.bots.bot_manager import BotManager

    bot_manager = BotManager()

    # Mock user data
    user_data = {
        "email": "test@example.com",
        "profile": {
            "full_name": "Test User",
            "phone": "555-0100"
        },
        "desired_position": "Software Engineer",
        "location": "San Francisco, CA",
        "desired_positions": ["Software Engineer", "Backend Developer"],
        "preferred_locations": ["San Francisco, CA", "Remote"],
        "linkedin_email": None,  # Would need real credentials
        "linkedin_password": None,
        "openai_api_key": None,
        "anthropic_api_key": None
    }

    # Test LinkedIn URL (would trigger AIHawk bot)
    linkedin_url = "https://www.linkedin.com/jobs/view/123456"
    platform = await bot_manager.detect_platform(linkedin_url)

    print(f"\n✅ Test Job URL: {linkedin_url}")
    print(f"  Detected Platform: {platform}")
    print(f"  Bot Available: {bot_manager.bots.get(platform) is not None}")

    if bot_manager.bots.get(platform):
        print(f"  Would use: {bot_manager.bots[platform].__class__.__name__}")
    else:
        print(f"  Would fallback to: BrowserAutoApplyService")

    print("\n⚠️  To actually apply, you need:")
    print("  1. Valid LinkedIn credentials in user_data")
    print("  2. OpenAI API key for AI question answering")
    print("  3. Resume file path")
    print("  4. Accept account ban risk")


async def main():
    """Run all tests"""
    try:
        await test_bot_manager()
        await test_linkedin_adapter()
        await test_bot_manager_application_flow()

        print("\n" + "=" * 60)
        print("✅ All Tests Completed Successfully!")
        print("=" * 60)
        print("\nNext Steps:")
        print("1. Set LinkedIn credentials in user document")
        print("2. Set OpenAI API key in user settings")
        print("3. Upload resume for user")
        print("4. Test with real LinkedIn Easy Apply job")
        print("5. Monitor for account bans")

    except Exception as e:
        print(f"\n❌ Test Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
