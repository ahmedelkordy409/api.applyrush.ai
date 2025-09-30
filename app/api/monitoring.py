"""
API endpoints for monitoring and performance metrics.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import redis
from datetime import datetime, timedelta

from app.monitoring import get_performance_monitor, track_performance
from app.core.redis import get_redis

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "jobhire-ai-backend"
    }

@router.get("/metrics/system")
async def get_system_metrics(redis_client: redis.Redis = Depends(get_redis)):
    """Get current system performance metrics"""
    try:
        monitor = get_performance_monitor()
        
        if not monitor.metrics_history:
            return {"message": "No metrics available yet"}
        
        latest_metrics = monitor.metrics_history[-1]
        
        return {
            "timestamp": latest_metrics.timestamp.isoformat(),
            "cpu_usage": latest_metrics.cpu_usage,
            "memory_usage": latest_metrics.memory_usage,
            "disk_usage": latest_metrics.disk_usage,
            "active_connections": latest_metrics.active_connections,
            "redis_memory": latest_metrics.redis_memory,
            "response_time": latest_metrics.response_time,
            "error_rate": latest_metrics.error_rate,
            "throughput": latest_metrics.throughput
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system metrics: {e}")

@router.get("/metrics/ai")
async def get_ai_metrics(redis_client: redis.Redis = Depends(get_redis)):
    """Get AI performance metrics"""
    try:
        monitor = get_performance_monitor()
        
        if not monitor.ai_metrics_history:
            return {"message": "No AI metrics available yet"}
        
        # Get latest metrics for each model
        latest_by_model = {}
        for metric in reversed(monitor.ai_metrics_history):
            if metric.model_name not in latest_by_model:
                latest_by_model[metric.model_name] = {
                    "timestamp": metric.timestamp.isoformat(),
                    "avg_response_time": metric.avg_response_time,
                    "success_rate": metric.success_rate,
                    "quality_score": metric.quality_score,
                    "token_usage": metric.token_usage,
                    "cost_per_request": metric.cost_per_request,
                    "accuracy_rate": metric.accuracy_rate
                }
        
        return latest_by_model
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting AI metrics: {e}")

@router.get("/metrics/applications")
async def get_application_metrics(redis_client: redis.Redis = Depends(get_redis)):
    """Get application processing metrics"""
    try:
        monitor = get_performance_monitor()
        
        if not monitor.app_metrics_history:
            return {"message": "No application metrics available yet"}
        
        latest_metrics = monitor.app_metrics_history[-1]
        
        return {
            "timestamp": latest_metrics.timestamp.isoformat(),
            "total_applications": latest_metrics.total_applications,
            "successful_applications": latest_metrics.successful_applications,
            "failed_applications": latest_metrics.failed_applications,
            "avg_processing_time": latest_metrics.avg_processing_time,
            "conversion_rate": latest_metrics.conversion_rate,
            "most_common_failures": latest_metrics.most_common_failures
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting application metrics: {e}")

@router.get("/summary")
async def get_performance_summary(redis_client: redis.Redis = Depends(get_redis)):
    """Get comprehensive performance summary"""
    try:
        monitor = get_performance_monitor()
        summary = await monitor.get_performance_summary()
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting performance summary: {e}")

@router.get("/alerts")
async def get_recent_alerts(redis_client: redis.Redis = Depends(get_redis)):
    """Get recent system alerts"""
    try:
        # Get last 20 alerts from Redis
        alerts = await redis_client.lrange("system_alerts", 0, 19)
        
        return {
            "alerts": [alert.decode() if isinstance(alert, bytes) else alert for alert in alerts],
            "count": len(alerts)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting alerts: {e}")

@router.get("/optimization/history")
async def get_optimization_history(redis_client: redis.Redis = Depends(get_redis)):
    """Get recent optimization actions"""
    try:
        # Get last 20 optimization actions from Redis
        optimizations = await redis_client.lrange("optimization_history", 0, 19)
        
        parsed_optimizations = []
        for opt in optimizations:
            if isinstance(opt, bytes):
                opt = opt.decode()
            
            try:
                timestamp, actions = opt.split(":", 1)
                parsed_optimizations.append({
                    "timestamp": timestamp,
                    "actions": actions.split(",")
                })
            except ValueError:
                continue
        
        return {
            "optimizations": parsed_optimizations,
            "count": len(parsed_optimizations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting optimization history: {e}")

@router.get("/metrics/trends")
async def get_metrics_trends(
    hours: int = 24,
    redis_client: redis.Redis = Depends(get_redis)
):
    """Get metrics trends over specified time period"""
    try:
        monitor = get_performance_monitor()
        
        # Filter metrics by time period
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        system_trends = [
            m for m in monitor.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        ai_trends = [
            m for m in monitor.ai_metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        app_trends = [
            m for m in monitor.app_metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        # Calculate trend data
        trends = {
            "system": {
                "data_points": len(system_trends),
                "avg_cpu": sum(m.cpu_usage for m in system_trends) / len(system_trends) if system_trends else 0,
                "avg_memory": sum(m.memory_usage for m in system_trends) / len(system_trends) if system_trends else 0,
                "avg_response_time": sum(m.response_time for m in system_trends) / len(system_trends) if system_trends else 0,
                "avg_error_rate": sum(m.error_rate for m in system_trends) / len(system_trends) if system_trends else 0
            },
            "applications": {
                "data_points": len(app_trends),
                "avg_conversion_rate": sum(m.conversion_rate for m in app_trends) / len(app_trends) if app_trends else 0,
                "avg_processing_time": sum(m.avg_processing_time for m in app_trends) / len(app_trends) if app_trends else 0,
                "total_applications": sum(m.total_applications for m in app_trends) if app_trends else 0
            },
            "time_period": f"{hours} hours",
            "start_time": cutoff_time.isoformat(),
            "end_time": datetime.utcnow().isoformat()
        }
        
        return trends
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting trends: {e}")

@router.post("/test-performance")
async def test_performance_tracking(redis_client: redis.Redis = Depends(get_redis)):
    """Test endpoint to demonstrate performance tracking"""
    try:
        async with track_performance("test_operation", redis_client):
            # Simulate some work
            import asyncio
            await asyncio.sleep(0.1)
            
            # Simulate potential error (10% chance)
            import random
            if random.random() < 0.1:
                raise Exception("Simulated error for testing")
        
        return {"message": "Performance test completed successfully"}
        
    except Exception as e:
        return {"message": f"Performance test failed: {e}", "status": "error"}