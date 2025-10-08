"""
Quick check of all countries in the database
"""

import pymongo
from collections import Counter
import re


def main():
    """Check all countries in database"""
    print("\n🌍 Checking Countries in Database")
    print("="*60)

    try:
        # Connect to MongoDB
        client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
        db = client["applyrush_ai"]

        # Test connection
        client.server_info()
        print("✅ Connected to MongoDB")

        # List all collections
        collections = db.list_collection_names()
        print(f"\nFound {len(collections)} collections")

        all_countries = []

        # Check each collection
        for collection_name in collections:
            print(f"\n📂 Checking: {collection_name}")
            collection = db[collection_name]

            count = collection.count_documents({})
            print(f"   Total documents: {count}")

            if count == 0:
                print("   (empty)")
                continue

            # Sample first document to see structure
            sample = collection.find_one()
            if sample:
                # Look for location/country fields
                for key in sample.keys():
                    if any(keyword in key.lower() for keyword in ['location', 'country', 'city', 'region']):
                        print(f"   Found field: {key}")

                        # Get all unique values for this field
                        unique_values = collection.distinct(key)
                        if unique_values:
                            print(f"   Values ({len(unique_values)}): {unique_values[:5]}")  # Show first 5

                            # Try to extract countries
                            for value in unique_values:
                                if value:
                                    if isinstance(value, str):
                                        # Split by comma and take last part (usually country)
                                        parts = [p.strip() for p in value.split(',')]
                                        if parts:
                                            country = parts[-1]
                                            all_countries.append(country)
                                    elif isinstance(value, dict) and 'country' in value:
                                        all_countries.append(value['country'])
                                    elif isinstance(value, list):
                                        for item in value:
                                            if isinstance(item, str):
                                                parts = [p.strip() for p in item.split(',')]
                                                if parts:
                                                    all_countries.append(parts[-1])

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        if all_countries:
            unique_countries = set(all_countries)
            counter = Counter(all_countries)

            print(f"\n✅ Found {len(all_countries)} country references")
            print(f"✅ Unique countries: {len(unique_countries)}")

            print("\nCountries by frequency:")
            for country, count in counter.most_common(20):
                print(f"  {country}: {count}")

            if len(counter) > 20:
                print(f"  ... and {len(counter) - 20} more")

            print("\nAll unique countries (sorted):")
            for country in sorted(unique_countries):
                print(f"  - {country}")
        else:
            print("\n⚠️  No country data found")
            print("\nPossible reasons:")
            print("  • Users haven't set location preferences")
            print("  • Jobs haven't been scraped with location data")
            print("  • Location data uses a different field name")

        client.close()

    except pymongo.errors.ServerSelectionTimeoutError:
        print("❌ Could not connect to MongoDB")
        print("Make sure MongoDB is running on localhost:27017")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
