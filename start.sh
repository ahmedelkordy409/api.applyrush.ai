#!/bin/bash

# JobHire.AI Backend Startup Script
echo "🚀 Starting JobHire.AI Backend Services..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please copy from .env.example and configure your API keys."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start services with Docker Compose
echo "📦 Starting services with Docker Compose..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🏥 Checking service health..."

# Check backend
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend API is running at http://localhost:8000"
    echo "📖 API Documentation: http://localhost:8000/docs"
else
    echo "❌ Backend API is not responding"
fi

# Check Flower (Celery monitoring)
if curl -s http://localhost:5555 > /dev/null; then
    echo "✅ Flower (Celery monitoring) is running at http://localhost:5555"
else
    echo "❌ Flower is not responding"
fi

# Check database connection
echo "🗄️  Checking database connection..."
if docker-compose exec -T backend python -c "
import asyncio
from app.core.database import check_database_health

async def check():
    healthy = await check_database_health()
    print('✅ Database connection: OK' if healthy else '❌ Database connection: FAILED')

asyncio.run(check())
" 2>/dev/null; then
    echo "Database check completed"
else
    echo "⚠️  Could not check database connection"
fi

echo ""
echo "🎉 JobHire.AI Backend is ready!"
echo ""
echo "📋 Service URLs:"
echo "   • Backend API:        http://localhost:8000"
echo "   • API Documentation:  http://localhost:8000/docs"
echo "   • Celery Monitoring:  http://localhost:5555"
echo "   • Database:          localhost:5432"
echo "   • Redis:             localhost:6379"
echo ""
echo "📊 To check logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f celery-worker"
echo ""
echo "🛑 To stop services:"
echo "   docker-compose down"
echo ""
echo "🔧 Next steps:"
echo "   1. Update your Next.js app to use: http://localhost:8000"
echo "   2. Test the API at: http://localhost:8000/docs"
echo "   3. Import the job-matching-dashboard component"
echo ""