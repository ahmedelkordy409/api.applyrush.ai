"""
Check all countries listed in the database
"""

import asyncio
import sys
from collections import Counter
from typing import Set, List, Dict
from motor.motor_asyncio import AsyncIOMotorClient

# Database configuration
MONGODB_URL = "mongodb://localhost:27017"
DATABASE_NAME = "applyrush_ai"


async def get_database():
    """Get database connection"""
    client = AsyncIOMotorClient(MONGODB_URL)
    return client[DATABASE_NAME]


async def extract_countries_from_location(location_data) -> Set[str]:
    """Extract country from location data (handles various formats)"""
    countries = set()

    if not location_data:
        return countries

    # Handle string format: "City, State, Country" or "City, Country"
    if isinstance(location_data, str):
        parts = [p.strip() for p in location_data.split(',')]
        if len(parts) >= 2:
            # Last part is usually the country
            countries.add(parts[-1])

    # Handle dict format: {"city": "...", "country": "..."}
    elif isinstance(location_data, dict):
        if 'country' in location_data:
            countries.add(location_data['country'])

    # Handle list format: ["United States", "Canada"]
    elif isinstance(location_data, list):
        for item in location_data:
            if isinstance(item, str):
                # If it's a full location string
                parts = [p.strip() for p in item.split(',')]
                if len(parts) >= 2:
                    countries.add(parts[-1])
                else:
                    countries.add(item)
            elif isinstance(item, dict) and 'country' in item:
                countries.add(item['country'])

    return countries


async def check_users_collection(db) -> Dict:
    """Check users collection for countries"""
    print("\n" + "="*60)
    print("Checking 'users' collection...")
    print("="*60)

    collection = db.users
    count = await collection.count_documents({})
    print(f"Total users: {count}")

    countries = set()
    location_data = []

    # Check users with location data
    async for user in collection.find({}):
        if user.get('location'):
            location = user['location']
            location_data.append(location)
            extracted = await extract_countries_from_location(location)
            countries.update(extracted)

        # Check location_preferences
        if user.get('location_preferences'):
            prefs = user['location_preferences']
            for pref in prefs if isinstance(prefs, list) else [prefs]:
                extracted = await extract_countries_from_location(pref)
                countries.update(extracted)

    print(f"Users with location data: {len(location_data)}")
    print(f"Unique countries found: {len(countries)}")
    if countries:
        print("Countries:", sorted(countries))

    return {
        'collection': 'users',
        'total': count,
        'countries': list(countries)
    }


async def check_jobs_collection(db) -> Dict:
    """Check jobs collection for countries"""
    print("\n" + "="*60)
    print("Checking 'jobs' collection...")
    print("="*60)

    collection = db.jobs
    count = await collection.count_documents({})
    print(f"Total jobs: {count}")

    countries = set()
    location_data = []

    # Check jobs with location data
    async for job in collection.find({}):
        if job.get('location'):
            location = job['location']
            location_data.append(location)
            extracted = await extract_countries_from_location(location)
            countries.update(extracted)

    print(f"Jobs with location data: {len(location_data)}")
    print(f"Unique countries found: {len(countries)}")
    if countries:
        print("Countries:", sorted(countries))

    return {
        'collection': 'jobs',
        'total': count,
        'countries': list(countries)
    }


async def check_user_profiles_collection(db) -> Dict:
    """Check user_profiles collection for countries"""
    print("\n" + "="*60)
    print("Checking 'user_profiles' collection...")
    print("="*60)

    collection = db.user_profiles
    count = await collection.count_documents({})
    print(f"Total user profiles: {count}")

    countries = set()
    location_data = []

    # Check profiles with location data
    async for profile in collection.find({}):
        if profile.get('location'):
            location = profile['location']
            location_data.append(location)
            extracted = await extract_countries_from_location(location)
            countries.update(extracted)

    print(f"Profiles with location data: {len(location_data)}")
    print(f"Unique countries found: {len(countries)}")
    if countries:
        print("Countries:", sorted(countries))

    return {
        'collection': 'user_profiles',
        'total': count,
        'countries': list(countries)
    }


async def check_user_search_settings_collection(db) -> Dict:
    """Check user_search_settings collection for countries"""
    print("\n" + "="*60)
    print("Checking 'user_search_settings' collection...")
    print("="*60)

    collection = db.user_search_settings
    count = await collection.count_documents({})
    print(f"Total search settings: {count}")

    countries = set()
    location_data = []

    # Check settings with location data
    async for settings in collection.find({}):
        if settings.get('locations'):
            locations = settings['locations']
            if isinstance(locations, list):
                for loc in locations:
                    location_data.append(loc)
                    extracted = await extract_countries_from_location(loc)
                    countries.update(extracted)

    print(f"Settings with location data: {len(location_data)}")
    print(f"Unique countries found: {len(countries)}")
    if countries:
        print("Countries:", sorted(countries))

    return {
        'collection': 'user_search_settings',
        'total': count,
        'countries': list(countries)
    }


async def check_onboarding_collection(db) -> Dict:
    """Check onboarding-related collections for countries"""
    print("\n" + "="*60)
    print("Checking 'onboarding_data' collection...")
    print("="*60)

    collection = db.onboarding_data
    count = await collection.count_documents({})
    print(f"Total onboarding records: {count}")

    countries = set()
    location_data = []

    # Check onboarding data for location info
    async for data in collection.find({}):
        if data.get('data'):
            onboarding_data = data['data']
            if isinstance(onboarding_data, dict):
                # Check various possible fields
                for key in ['location', 'country', 'locations', 'preferred_locations']:
                    if key in onboarding_data:
                        value = onboarding_data[key]
                        location_data.append(value)
                        extracted = await extract_countries_from_location(value)
                        countries.update(extracted)

    print(f"Onboarding with location data: {len(location_data)}")
    print(f"Unique countries found: {len(countries)}")
    if countries:
        print("Countries:", sorted(countries))

    return {
        'collection': 'onboarding_data',
        'total': count,
        'countries': list(countries)
    }


async def list_all_collections(db) -> List[str]:
    """List all collections in the database"""
    collections = await db.list_collection_names()
    return collections


async def main():
    """Main function to check all countries"""
    print("\n🌍 Checking Countries in ApplyRush.AI Database")
    print("="*60)

    try:
        db = await get_database()

        # List all collections
        print("\nAvailable collections:")
        collections = await list_all_collections(db)
        for col in sorted(collections):
            print(f"  - {col}")

        # Check each relevant collection
        results = []

        results.append(await check_users_collection(db))
        results.append(await check_jobs_collection(db))
        results.append(await check_user_profiles_collection(db))
        results.append(await check_user_search_settings_collection(db))
        results.append(await check_onboarding_collection(db))

        # Summary
        print("\n" + "="*60)
        print("SUMMARY - All Countries Found")
        print("="*60)

        all_countries = set()
        for result in results:
            all_countries.update(result['countries'])

        print(f"\n✅ Total unique countries across all collections: {len(all_countries)}")

        if all_countries:
            print("\nCountries by frequency:")
            country_count = Counter()
            for result in results:
                for country in result['countries']:
                    country_count[country] += 1

            for country, count in country_count.most_common():
                print(f"  {country}: {count} collection(s)")
        else:
            print("\n⚠️  No country data found in database")
            print("This might mean:")
            print("  - Users haven't completed their profiles yet")
            print("  - Location data is stored in a different format")
            print("  - Jobs haven't been scraped yet with location data")

        # Breakdown by collection
        print("\n" + "="*60)
        print("Countries by Collection:")
        print("="*60)
        for result in results:
            print(f"\n{result['collection']}:")
            print(f"  Total documents: {result['total']}")
            print(f"  Unique countries: {len(result['countries'])}")
            if result['countries']:
                print(f"  Countries: {', '.join(sorted(result['countries']))}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
