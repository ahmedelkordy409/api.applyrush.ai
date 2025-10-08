"""
Check all countries in MongoDB Atlas database
"""

import os
from dotenv import load_dotenv
import pymongo
from collections import Counter

# Load environment variables
load_dotenv()

def main():
    """Check all countries in database"""
    print("\n🌍 Checking Countries in ApplyRush.AI Database")
    print("="*60)

    # Get MongoDB URL from environment
    mongodb_url = os.getenv("MONGODB_URL")
    mongodb_database = os.getenv("MONGODB_DATABASE", "jobhire")

    if not mongodb_url:
        print("❌ MONGODB_URL not found in .env file")
        return

    print(f"Database: {mongodb_database}")
    print("Connecting to MongoDB Atlas...")

    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(mongodb_url, serverSelectionTimeoutMS=10000)
        db = client[mongodb_database]

        # Test connection
        client.server_info()
        print("✅ Connected to MongoDB Atlas\n")

        # List all collections
        collections = db.list_collection_names()
        print(f"Found {len(collections)} collections:")
        for col in sorted(collections):
            count = db[col].count_documents({})
            print(f"  - {col}: {count} documents")

        all_countries = []
        country_sources = {}  # Track which collection each country came from

        # Check each collection for location/country data
        for collection_name in collections:
            collection = db[collection_name]
            count = collection.count_documents({})

            if count == 0:
                continue

            print(f"\n📂 Analyzing: {collection_name} ({count} documents)")

            # Get all documents (limit to 1000 for safety)
            documents = list(collection.find({}).limit(1000))

            for doc in documents:
                # Recursively search for country/location data
                countries_found = extract_countries_recursive(doc)
                for country in countries_found:
                    all_countries.append(country)
                    if country not in country_sources:
                        country_sources[country] = set()
                    country_sources[country].add(collection_name)

        # Summary
        print("\n" + "="*60)
        print("SUMMARY - Countries Found in Database")
        print("="*60)

        if all_countries:
            unique_countries = set(all_countries)
            counter = Counter(all_countries)

            print(f"\n✅ Total country references: {len(all_countries)}")
            print(f"✅ Unique countries: {len(unique_countries)}")

            print("\n📊 Countries by Frequency:")
            print("-" * 60)
            for country, count in counter.most_common():
                sources = country_sources.get(country, set())
                print(f"  {country:<30} {count:>3} mentions  (in: {', '.join(sorted(sources))})")

            print("\n🗺️  All Unique Countries (Alphabetical):")
            print("-" * 60)
            for i, country in enumerate(sorted(unique_countries), 1):
                print(f"  {i:2}. {country}")

        else:
            print("\n⚠️  No country data found in database")
            print("\nPossible reasons:")
            print("  • Users haven't completed location preferences in onboarding")
            print("  • Jobs haven't been scraped yet with location information")
            print("  • Location data is stored in a different format than expected")
            print("\nChecked collections:", ", ".join(collections))

        client.close()
        print("\n" + "="*60)

    except pymongo.errors.ServerSelectionTimeoutError:
        print("❌ Could not connect to MongoDB Atlas")
        print("Please check your MONGODB_URL in .env file")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def extract_countries_recursive(data, depth=0, max_depth=5):
    """Recursively extract country data from nested structures"""
    countries = set()

    if depth > max_depth:
        return countries

    if data is None:
        return countries

    # If it's a string, check if it looks like a location
    if isinstance(data, str):
        if any(keyword in data.lower() for keyword in ['remote', 'usa', 'us', 'uk', 'canada']):
            # Try to extract country from location string
            parts = [p.strip() for p in data.split(',')]
            if parts:
                # Last part is usually the country
                country = parts[-1].strip()
                # Filter out common non-country values
                if country and len(country) > 1 and country.lower() not in ['remote', 'hybrid', 'onsite', 'n/a', 'na']:
                    countries.add(country)

    # If it's a dictionary, check for country fields
    elif isinstance(data, dict):
        # Check for explicit country fields
        if 'country' in data:
            if data['country']:
                countries.add(str(data['country']))

        # Check location-related fields
        for key in ['location', 'city', 'region', 'address', 'locations', 'preferred_locations', 'location_preferences']:
            if key in data:
                countries.update(extract_countries_recursive(data[key], depth + 1, max_depth))

        # Recurse into all values
        for key, value in data.items():
            if key not in ['_id', 'id', 'created_at', 'updated_at']:  # Skip these
                countries.update(extract_countries_recursive(value, depth + 1, max_depth))

    # If it's a list, check each item
    elif isinstance(data, list):
        for item in data:
            countries.update(extract_countries_recursive(item, depth + 1, max_depth))

    return countries


if __name__ == "__main__":
    main()
