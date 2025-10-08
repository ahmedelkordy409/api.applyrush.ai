"""
Check all countries in MongoDB - Clean version with better filtering
"""

import os
from dotenv import load_dotenv
import pymongo
from collections import Counter

# Load environment variables
load_dotenv()

# Common country names to look for
KNOWN_COUNTRIES = {
    'United States', 'USA', 'US', 'America',
    'Canada', 'UK', 'United Kingdom', 'England', 'Scotland', 'Wales',
    'Germany', 'France', 'Spain', 'Italy', 'Netherlands', 'Belgium',
    'Australia', 'New Zealand',
    'India', 'China', 'Japan', 'Singapore', 'South Korea',
    'Brazil', 'Mexico', 'Argentina', 'Chile',
    'Israel', 'UAE', 'Saudi Arabia',
    'Poland', 'Czech Republic', 'Romania', 'Ukraine',
    'Ireland', 'Sweden', 'Norway', 'Denmark', 'Finland',
    'Switzerland', 'Austria', 'Portugal', 'Greece',
    'South Africa', 'Egypt', 'Nigeria', 'Kenya',
    'Pakistan', 'Bangladesh', 'Philippines', 'Indonesia', 'Vietnam', 'Thailand',
    'Turkey', 'Russia'
}


def normalize_country(text):
    """Normalize country name"""
    if not text or not isinstance(text, str):
        return None

    text = text.strip()

    # Map common variations
    mappings = {
        'USA': 'United States',
        'US': 'United States',
        'America': 'United States',
        'UK': 'United Kingdom',
        'England': 'United Kingdom',
        'Scotland': 'United Kingdom',
        'Wales': 'United Kingdom',
    }

    if text in mappings:
        return mappings[text]

    # Check if it's a known country
    for country in KNOWN_COUNTRIES:
        if country.lower() in text.lower():
            return country

    return None


def extract_country_from_location(location_str):
    """Extract country from location string"""
    if not location_str or not isinstance(location_str, str):
        return None

    # Remove common prefixes
    location_str = location_str.replace('Remote - ', '').replace('Remote, ', '')

    # Split by comma and check each part
    parts = [p.strip() for p in location_str.split(',')]

    # Check each part for a country
    for part in reversed(parts):  # Check from right to left (country usually last)
        country = normalize_country(part)
        if country:
            return country

    return None


def main():
    """Check all countries in database"""
    print("\n🌍 Countries in ApplyRush.AI Database")
    print("="*60)

    # Get MongoDB URL from environment
    mongodb_url = os.getenv("MONGODB_URL")
    mongodb_database = os.getenv("MONGODB_DATABASE", "jobhire")

    if not mongodb_url:
        print("❌ MONGODB_URL not found in .env file")
        return

    print(f"Database: {mongodb_database}")
    print("Connecting to MongoDB Atlas...\n")

    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(mongodb_url, serverSelectionTimeoutMS=10000)
        db = client[mongodb_database]

        # Test connection
        client.server_info()
        print("✅ Connected successfully\n")

        countries_by_collection = {}

        # Collections to check with their location fields
        checks = [
            ('users', ['location']),
            ('jobs', ['location', 'country']),
            ('guest_profiles', ['location']),
            ('user_settings', ['location', 'locations']),
            ('applications', ['location']),
        ]

        for collection_name, location_fields in checks:
            if collection_name not in db.list_collection_names():
                continue

            collection = db[collection_name]
            count = collection.count_documents({})

            if count == 0:
                continue

            print(f"📂 {collection_name} ({count} documents)")
            countries = []

            # Check each location field
            for field in location_fields:
                # Get distinct values for this field
                try:
                    values = collection.distinct(field)
                    for value in values:
                        if value:
                            if isinstance(value, str):
                                country = extract_country_from_location(value)
                                if country:
                                    countries.append(country)
                            elif isinstance(value, list):
                                for item in value:
                                    if isinstance(item, str):
                                        country = extract_country_from_location(item)
                                        if country:
                                            countries.append(country)
                            elif isinstance(value, dict):
                                if 'country' in value:
                                    country = normalize_country(value['country'])
                                    if country:
                                        countries.append(country)
                except Exception as e:
                    pass

            if countries:
                unique = set(countries)
                countries_by_collection[collection_name] = countries
                print(f"   Found: {', '.join(sorted(unique))}")
            else:
                print(f"   No countries found")

            print()

        # Summary
        print("="*60)
        print("SUMMARY")
        print("="*60)

        all_countries = []
        for countries in countries_by_collection.values():
            all_countries.extend(countries)

        if all_countries:
            counter = Counter(all_countries)
            unique_countries = set(all_countries)

            print(f"\n✅ Total country mentions: {len(all_countries)}")
            print(f"✅ Unique countries: {len(unique_countries)}")

            print("\n📊 Countries by Frequency:")
            print("-" * 40)
            for country, count in counter.most_common():
                print(f"  {country:<25} {count:>3} mentions")

            print("\n🗺️  All Countries (Alphabetical):")
            print("-" * 40)
            for i, country in enumerate(sorted(unique_countries), 1):
                print(f"  {i:2}. {country}")

            # Show breakdown by collection
            print("\n📊 By Collection:")
            print("-" * 40)
            for coll_name, countries in countries_by_collection.items():
                if countries:
                    coll_counter = Counter(countries)
                    print(f"\n  {coll_name}:")
                    for country, count in coll_counter.most_common():
                        print(f"    {country}: {count}")

        else:
            print("\n⚠️  No country data found")
            print("\nThis means:")
            print("  • Users haven't set location preferences yet")
            print("  • Jobs were scraped without location data")
            print("  • Database is still being populated")

        client.close()

    except pymongo.errors.ServerSelectionTimeoutError:
        print("❌ Could not connect to MongoDB Atlas")
        print("Check MONGODB_URL in .env file")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
