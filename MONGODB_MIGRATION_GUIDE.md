# MongoDB Migration Guide

This guide will help you migrate from Supabase (PostgreSQL) to MongoDB for your JobHire.AI backend.

## Overview

The migration includes:
- Converting from SQL (PostgreSQL/Supabase) to NoSQL (MongoDB)
- Replacing Supabase client with MongoDB/Beanie ODM
- Updating all database models and services
- Maintaining API compatibility

## Prerequisites

1. **MongoDB Installation**
   ```bash
   # For Ubuntu/Debian
   sudo apt-get install mongodb

   # For macOS
   brew install mongodb-community

   # Or use Docker
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   ```

2. **Update Environment Variables**
   ```bash
   # Copy the new environment template
   cp .env.example .env

   # Edit .env and set MongoDB configuration
   MONGODB_URL=mongodb://localhost:27017
   MONGODB_DATABASE=jobhire_ai
   TEST_MONGODB_DATABASE=jobhire_ai_test
   ```

## Migration Steps

### 1. Install Dependencies

The required MongoDB dependencies are already in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Test MongoDB Connection

```bash
python test_mongodb.py
```

This will test:
- MongoDB connection
- Model creation and queries
- User service operations

### 3. Migrate Data (if needed)

If you have existing data in Supabase:

```bash
# Create test data for development
python migrate_to_mongodb.py --test-data

# Verify existing data
python migrate_to_mongodb.py --verify-only

# Run full migration (customize the script first)
python migrate_to_mongodb.py
```

### 4. Update Application Configuration

The application has been updated to support both MongoDB and legacy PostgreSQL during the transition:

- MongoDB is the primary database
- PostgreSQL/Supabase connection is optional (for migration period)
- Health checks monitor both databases

### 5. Start the Application

```bash
python -m app.main
```

Check the health endpoint:
```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "databases": {
    "mongodb": "healthy"
  }
}
```

## Key Changes

### Models

- **Before**: SQLAlchemy models in `app/models/database.py`
- **After**: Beanie documents in `app/models/mongodb_models.py`

### Services

- **Before**: `UserService` using Supabase client
- **After**: `MongoDBUserService` using Beanie ODM

### Database Connection

- **Before**: `databases` package with PostgreSQL
- **After**: `motor` with MongoDB + Beanie ODM

## Model Mapping

| SQLAlchemy Model | MongoDB Document | Changes |
|------------------|------------------|---------|
| `User` | `User` | - `supabase_id` → `external_id`<br>- JSON fields now native dicts |
| `Company` | `Company` | - Minimal changes |
| `Job` | `Job` | - `company_id` still references Company<br>- Added `company_name` for denormalization |
| `JobMatch` | `JobMatch` | - Uses ObjectId references |
| `JobApplication` | `JobApplication` | - Status enum preserved |

## API Compatibility

All existing API endpoints remain unchanged. The MongoDB services implement the same interface as the Supabase services.

## Development Features

### 1. Health Monitoring
- `/health` endpoint shows database status
- Supports both MongoDB and legacy database

### 2. Migration Tools
- `migrate_to_mongodb.py` - Data migration script
- `test_mongodb.py` - Connection and functionality tests

### 3. Dual Database Support
During transition, the app can connect to both:
- MongoDB (primary)
- PostgreSQL (legacy, optional)

## Production Deployment

### 1. MongoDB Setup

For production, use MongoDB Atlas or a managed MongoDB service:

```bash
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=jobhire_ai_prod
```

### 2. Data Migration

1. Export data from Supabase
2. Customize `migrate_to_mongodb.py` for your schema
3. Run migration in staging environment
4. Verify data integrity
5. Deploy to production

### 3. Monitoring

- Monitor MongoDB performance
- Set up alerts for connection issues
- Use MongoDB Compass for database administration

## Troubleshooting

### Connection Issues

```bash
# Test MongoDB connection
python -c "from pymongo import MongoClient; print(MongoClient().admin.command('ismaster'))"
```

### Model Issues

```bash
# Test model creation
python test_mongodb.py
```

### Migration Issues

```bash
# Check migration logs
python migrate_to_mongodb.py --verify-only
```

## Rollback Plan

If needed, you can rollback by:

1. Commenting out MongoDB initialization in `app/main.py`
2. Reverting to Supabase services
3. Restoring environment variables

The legacy database connection code is preserved for this purpose.

## Performance Benefits

MongoDB offers several advantages:

1. **Flexible Schema**: No migrations needed for schema changes
2. **Horizontal Scaling**: Built-in sharding support
3. **Rich Queries**: Complex queries with aggregation pipeline
4. **Document Storage**: Natural fit for JSON-heavy data
5. **Performance**: Optimized for read-heavy workloads

## Next Steps

1. Run tests to ensure everything works
2. Customize migration script if you have existing data
3. Update any custom queries to use MongoDB syntax
4. Consider implementing data archiving strategies
5. Set up monitoring and backup procedures

## Support

For issues with the migration:

1. Check the logs in `app/main.py` startup
2. Verify environment variables
3. Test individual components with provided scripts
4. Review MongoDB documentation for advanced features