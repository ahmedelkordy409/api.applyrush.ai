# JobHire.AI Backend

Production-ready FastAPI backend for AI-powered job matching and auto-application system.

## Features

### 🤖 AI-Powered Matching
- Advanced job-candidate matching using Llama 3.1 70B
- Intelligent cover letter generation
- Quality validation system for AI outputs
- Multi-step reasoning with chain-of-thought prompts

### 🚀 Auto-Apply System
- Complex form handling (Workday, Greenhouse, Lever, etc.)
- Multi-step application workflows
- Comprehensive error handling and retry mechanisms
- Safety controls and rate limiting

### 📊 Performance Monitoring
- Real-time system metrics tracking
- AI performance monitoring
- Auto-scaling and optimization
- Comprehensive logging and alerting

### 🔒 Production Ready
- Docker containerization
- Zero-downtime deployment
- SSL/TLS encryption
- Rate limiting and security headers
- Comprehensive testing suite  

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js       │    │   FastAPI       │    │   PostgreSQL    │
│   Frontend      │◄──►│   Backend       │◄──►│   Database      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Celery        │    │   Redis         │
                       │   Workers       │◄──►│   Broker        │
                       │                 │    │                 │
                       └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Models     │
                       │   (Replicate)   │
                       │                 │
                       └─────────────────┘
```

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```env
# Database
DATABASE_URL=postgresql://username:password@localhost/jobhire_ai

# AI Services
REPLICATE_API_TOKEN=your_replicate_token
OPENAI_API_KEY=your_openai_key

# Job APIs
JSEARCH_API_KEY=your_jsearch_key

# Redis/Celery
REDIS_URL=redis://localhost:6379/0

# Supabase (for frontend integration)
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
```

### 2. Docker Development

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

### 3. Manual Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis
# (via Docker or local installation)

# Run database migrations
python -c "from app.core.database import engine; from app.models.database import Base; Base.metadata.create_all(engine)"

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Start Celery beat scheduler (separate terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

### 4. API Documentation

Once running, visit:
- **API Docs**: http://localhost:8000/docs
- **Flower (Celery)**: http://localhost:5555
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Jobs
- `POST /api/v1/jobs/search` - Search for jobs
- `GET /api/v1/jobs/{job_id}` - Get job details
- `POST /api/v1/jobs/fetch-for-user/{user_id}` - Fetch jobs for user
- `GET /api/v1/jobs/user/{user_id}/matches` - Get user's job matches
- `GET /api/v1/jobs/trending` - Get trending jobs

### Matching
- `POST /api/v1/matching/analyze` - Analyze job match
- `POST /api/v1/matching/bulk-analyze` - Bulk job matching
- `POST /api/v1/matching/cover-letter` - Generate cover letter
- `GET /api/v1/matching/user/{user_id}/preferences` - Get matching preferences
- `GET /api/v1/matching/user/{user_id}/statistics` - Get matching statistics

### Applications
- `POST /api/v1/applications/submit` - Submit job application
- `GET /api/v1/applications/user/{user_id}` - Get user applications
- `PUT /api/v1/applications/{application_id}/status` - Update application status
- `POST /api/v1/applications/auto-apply/settings` - Update auto-apply settings
- `GET /api/v1/applications/user/{user_id}/statistics` - Get application statistics

### Users
- `GET /api/v1/users/{user_id}/profile` - Get user profile
- `PUT /api/v1/users/{user_id}/profile` - Update user profile

### Analytics
- `GET /api/v1/analytics/dashboard/{user_id}` - Get user dashboard
- `GET /api/v1/analytics/system/health` - System health check

## AI Agent Prompts

The system includes comprehensive AI prompts for:

1. **Job Matching**: 85%+ accuracy job-candidate matching
2. **Cover Letter Generation**: Personalized, compelling cover letters
3. **Auto-Apply Decision**: Intelligent application automation
4. **Resume Optimization**: ATS-optimized resume customization
5. **Interview Scheduling**: Smart calendar coordination
6. **Application Tracking**: Lifecycle monitoring and insights
7. **Learning & Improvement**: Continuous algorithm optimization

## Background Tasks

### Celery Workers Handle:
- **Job Fetching**: Periodic job discovery from multiple sources
- **Matching**: AI-powered job-candidate matching
- **Auto-Apply**: Intelligent application submission
- **Status Updates**: Application status tracking
- **Analytics**: Performance metrics calculation
- **Notifications**: User communication

### Scheduled Tasks:
```python
# Every 2 hours: Fetch trending jobs
# Every 10 minutes: Process auto-apply queue
# Every 6 hours: Update application statuses
# Daily at 2 AM: Calculate user analytics
# Weekly: Cleanup old data
```

## Database Schema

Key tables:
- `users` - User profiles and preferences
- `jobs` - Job listings from various sources  
- `job_matches` - AI matching results
- `job_applications` - Application tracking
- `application_status_history` - Status change timeline
- `ai_processing_logs` - AI operation monitoring
- `user_analytics` - Performance metrics

## Monitoring & Performance

### Health Monitoring
- API response times < 200ms p95
- Error rates < 0.1%
- AI model accuracy > 85%
- Queue processing < 30s

### Metrics Tracked
- Job matching accuracy
- Application success rates
- AI processing costs
- User engagement metrics
- System performance indicators

## Integration with Next.js Frontend

The backend is designed to integrate seamlessly with your existing Next.js app:

### 1. Add API Routes
```typescript
// In your Next.js app/api/ directory
export async function POST(request: Request) {
  // Proxy to Python backend
  const response = await fetch('http://localhost:8000/api/v1/jobs/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(await request.json()),
  });
  
  return Response.json(await response.json());
}
```

### 2. Environment Variables
```env
# Add to your Next.js .env.local
PYTHON_BACKEND_URL=http://localhost:8000
```

### 3. API Client
```typescript
// lib/api-client.ts
const API_BASE = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function searchJobs(params: JobSearchParams) {
  const response = await fetch(`${API_BASE}/api/v1/jobs/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return response.json();
}

export async function getJobMatches(userId: number) {
  const response = await fetch(`${API_BASE}/api/v1/jobs/user/${userId}/matches`);
  return response.json();
}
```

## Production Deployment

### Docker Production
```bash
# Build production image
docker build -t jobhire-backend .

# Run with production settings
docker run -d \
  --name jobhire-backend \
  -p 8000:8000 \
  --env-file .env.production \
  jobhire-backend
```

### Environment Setup
- PostgreSQL: Managed instance (AWS RDS, Google Cloud SQL)
- Redis: Managed instance (AWS ElastiCache, Redis Cloud)
- Load Balancer: Nginx or AWS ALB
- Monitoring: Prometheus + Grafana
- Logging: ELK Stack or similar

### Scaling
- Horizontal: Multiple backend instances behind load balancer
- Workers: Scale Celery workers based on queue depth
- Database: Read replicas, connection pooling
- Caching: Redis cluster for high availability

## Cost Optimization

The system includes intelligent cost optimization:

- **Tiered Models**: Cheap → Balanced → Premium based on user tier
- **Caching**: Aggressive caching to minimize API calls
- **Batch Processing**: Efficient bulk operations
- **Rate Limiting**: Prevent API abuse
- **Usage Tracking**: Cost monitoring per operation

Target metrics:
- Cost per user: < $0.50/month
- Cost per application: < $0.10
- Infrastructure efficiency: > 80%

## Support & Contributing

For issues, feature requests, or contributions:

1. Check existing issues
2. Create detailed bug reports
3. Follow coding standards
4. Include tests for new features
5. Update documentation

## License

MIT License - see LICENSE file for details.