"""
Performance monitoring and optimization system for production environment.
Tracks system metrics, AI performance, and auto-scales resources.
"""

import asyncio
import time
import psutil
import redis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
from contextlib import asynccontextmanager

from app.core.database import get_db
from app.models.applications import Application
from app.models.jobs import Job

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    redis_memory: float
    response_time: float
    error_rate: float
    throughput: float

@dataclass
class AIPerformanceMetrics:
    timestamp: datetime
    model_name: str
    avg_response_time: float
    success_rate: float
    quality_score: float
    token_usage: int
    cost_per_request: float
    accuracy_rate: float

@dataclass
class ApplicationMetrics:
    timestamp: datetime
    total_applications: int
    successful_applications: int
    failed_applications: int
    avg_processing_time: float
    conversion_rate: float
    most_common_failures: List[str]

class PerformanceMonitor:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.monitoring_active = False
        self.metrics_history: List[SystemMetrics] = []
        self.ai_metrics_history: List[AIPerformanceMetrics] = []
        self.app_metrics_history: List[ApplicationMetrics] = []
        
    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        self.monitoring_active = True
        logger.info("Starting performance monitoring...")
        
        # Start monitoring tasks
        await asyncio.gather(
            self._monitor_system_metrics(),
            self._monitor_ai_performance(),
            self._monitor_application_metrics(),
            self._optimize_resources(),
            return_exceptions=True
        )
    
    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring_active = False
        logger.info("Stopping performance monitoring...")
    
    async def _monitor_system_metrics(self):
        """Monitor system-level metrics"""
        while self.monitoring_active:
            try:
                # CPU and Memory
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Network connections
                connections = len(psutil.net_connections())
                
                # Redis memory usage
                redis_info = self.redis.info('memory')
                redis_memory = redis_info.get('used_memory', 0) / (1024 * 1024)  # MB
                
                # Response time (from recent requests)
                response_time = await self._get_avg_response_time()
                
                # Error rate
                error_rate = await self._get_error_rate()
                
                # Throughput
                throughput = await self._get_throughput()
                
                metrics = SystemMetrics(
                    timestamp=datetime.utcnow(),
                    cpu_usage=cpu_usage,
                    memory_usage=memory.percent,
                    disk_usage=disk.percent,
                    active_connections=connections,
                    redis_memory=redis_memory,
                    response_time=response_time,
                    error_rate=error_rate,
                    throughput=throughput
                )
                
                # Store metrics
                await self._store_system_metrics(metrics)
                self.metrics_history.append(metrics)
                
                # Keep only last 1000 metrics in memory
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                # Alert if critical thresholds exceeded
                await self._check_system_alerts(metrics)
                
            except Exception as e:
                logger.error(f"Error monitoring system metrics: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _monitor_ai_performance(self):
        """Monitor AI model performance"""
        while self.monitoring_active:
            try:
                # Get AI metrics from last hour
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                
                # Aggregate metrics from Redis
                ai_metrics = await self._get_ai_metrics_since(one_hour_ago)
                
                for model_name, metrics in ai_metrics.items():
                    ai_perf = AIPerformanceMetrics(
                        timestamp=datetime.utcnow(),
                        model_name=model_name,
                        avg_response_time=metrics.get('avg_response_time', 0),
                        success_rate=metrics.get('success_rate', 0),
                        quality_score=metrics.get('quality_score', 0),
                        token_usage=metrics.get('token_usage', 0),
                        cost_per_request=metrics.get('cost_per_request', 0),
                        accuracy_rate=metrics.get('accuracy_rate', 0)
                    )
                    
                    await self._store_ai_metrics(ai_perf)
                    self.ai_metrics_history.append(ai_perf)
                
                # Keep only last 500 AI metrics
                if len(self.ai_metrics_history) > 500:
                    self.ai_metrics_history = self.ai_metrics_history[-500:]
                
            except Exception as e:
                logger.error(f"Error monitoring AI performance: {e}")
            
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def _monitor_application_metrics(self):
        """Monitor application processing metrics"""
        while self.monitoring_active:
            try:
                async with get_db() as db:
                    # Get metrics from last hour
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    
                    # Total applications
                    total_apps = await db.scalar(
                        select(func.count(Application.id))
                        .where(Application.created_at >= one_hour_ago)
                    )
                    
                    # Successful applications
                    successful_apps = await db.scalar(
                        select(func.count(Application.id))
                        .where(
                            Application.created_at >= one_hour_ago,
                            Application.status == 'submitted'
                        )
                    )
                    
                    # Failed applications
                    failed_apps = await db.scalar(
                        select(func.count(Application.id))
                        .where(
                            Application.created_at >= one_hour_ago,
                            Application.status.in_(['failed', 'error'])
                        )
                    )
                    
                    # Average processing time
                    avg_processing_time = await self._get_avg_processing_time(db, one_hour_ago)
                    
                    # Conversion rate
                    conversion_rate = (successful_apps / total_apps * 100) if total_apps > 0 else 0
                    
                    # Most common failures
                    common_failures = await self._get_common_failures(db, one_hour_ago)
                    
                    app_metrics = ApplicationMetrics(
                        timestamp=datetime.utcnow(),
                        total_applications=total_apps or 0,
                        successful_applications=successful_apps or 0,
                        failed_applications=failed_apps or 0,
                        avg_processing_time=avg_processing_time,
                        conversion_rate=conversion_rate,
                        most_common_failures=common_failures
                    )
                    
                    await self._store_application_metrics(app_metrics)
                    self.app_metrics_history.append(app_metrics)
                
                # Keep only last 500 application metrics
                if len(self.app_metrics_history) > 500:
                    self.app_metrics_history = self.app_metrics_history[-500:]
                
            except Exception as e:
                logger.error(f"Error monitoring application metrics: {e}")
            
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def _optimize_resources(self):
        """Auto-optimize resources based on performance metrics"""
        while self.monitoring_active:
            try:
                if len(self.metrics_history) < 5:
                    await asyncio.sleep(60)
                    continue
                
                recent_metrics = self.metrics_history[-5:]
                
                # Check if optimization needed
                avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
                avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
                avg_response_time = sum(m.response_time for m in recent_metrics) / len(recent_metrics)
                
                optimization_actions = []
                
                # High CPU usage optimization
                if avg_cpu > 80:
                    optimization_actions.append("scale_workers")
                    await self._scale_workers("up")
                
                # High memory usage optimization
                if avg_memory > 85:
                    optimization_actions.append("clear_cache")
                    await self._clear_old_cache()
                
                # High response time optimization
                if avg_response_time > 5000:  # 5 seconds
                    optimization_actions.append("optimize_db_queries")
                    await self._optimize_database_connections()
                
                # Low resource usage - scale down
                if avg_cpu < 20 and avg_memory < 30:
                    optimization_actions.append("scale_down")
                    await self._scale_workers("down")
                
                if optimization_actions:
                    logger.info(f"Auto-optimization actions taken: {optimization_actions}")
                    
                    # Store optimization record
                    await self.redis.lpush(
                        "optimization_history",
                        f"{datetime.utcnow().isoformat()}:{','.join(optimization_actions)}"
                    )
                
            except Exception as e:
                logger.error(f"Error in resource optimization: {e}")
            
            await asyncio.sleep(120)  # Check every 2 minutes
    
    async def _get_avg_response_time(self) -> float:
        """Get average response time from recent requests"""
        try:
            response_times = await self.redis.lrange("response_times", 0, 99)
            if not response_times:
                return 0.0
            
            times = [float(rt) for rt in response_times if rt]
            return sum(times) / len(times) if times else 0.0
        except:
            return 0.0
    
    async def _get_error_rate(self) -> float:
        """Get error rate from recent requests"""
        try:
            total_requests = await self.redis.get("total_requests_last_hour") or 0
            error_requests = await self.redis.get("error_requests_last_hour") or 0
            
            total_requests = int(total_requests)
            error_requests = int(error_requests)
            
            return (error_requests / total_requests * 100) if total_requests > 0 else 0.0
        except:
            return 0.0
    
    async def _get_throughput(self) -> float:
        """Get requests per minute"""
        try:
            requests_last_minute = await self.redis.get("requests_last_minute") or 0
            return float(requests_last_minute)
        except:
            return 0.0
    
    async def _get_ai_metrics_since(self, since: datetime) -> Dict[str, Dict]:
        """Get AI performance metrics since given time"""
        try:
            # Get metrics from Redis hash
            ai_metrics = {}
            
            # Example models to track
            models = ["llama-3.1-70b", "job-matcher", "application-handler"]
            
            for model in models:
                metrics_key = f"ai_metrics:{model}"
                metrics_data = await self.redis.hgetall(metrics_key)
                
                if metrics_data:
                    ai_metrics[model] = {
                        'avg_response_time': float(metrics_data.get(b'avg_response_time', 0)),
                        'success_rate': float(metrics_data.get(b'success_rate', 0)),
                        'quality_score': float(metrics_data.get(b'quality_score', 0)),
                        'token_usage': int(metrics_data.get(b'token_usage', 0)),
                        'cost_per_request': float(metrics_data.get(b'cost_per_request', 0)),
                        'accuracy_rate': float(metrics_data.get(b'accuracy_rate', 0))
                    }
            
            return ai_metrics
        except Exception as e:
            logger.error(f"Error getting AI metrics: {e}")
            return {}
    
    async def _get_avg_processing_time(self, db: AsyncSession, since: datetime) -> float:
        """Get average application processing time"""
        try:
            # This would need to be implemented based on your application tracking
            # For now, return a placeholder
            return 45.5  # seconds
        except:
            return 0.0
    
    async def _get_common_failures(self, db: AsyncSession, since: datetime) -> List[str]:
        """Get most common failure reasons"""
        try:
            # This would analyze error messages and return top failure types
            return ["form_validation_error", "network_timeout", "captcha_required"]
        except:
            return []
    
    async def _store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics in Redis"""
        try:
            metrics_data = asdict(metrics)
            metrics_data['timestamp'] = metrics.timestamp.isoformat()
            
            await self.redis.lpush("system_metrics", str(metrics_data))
            await self.redis.ltrim("system_metrics", 0, 2999)  # Keep last 3000
        except Exception as e:
            logger.error(f"Error storing system metrics: {e}")
    
    async def _store_ai_metrics(self, metrics: AIPerformanceMetrics):
        """Store AI performance metrics"""
        try:
            metrics_data = asdict(metrics)
            metrics_data['timestamp'] = metrics.timestamp.isoformat()
            
            await self.redis.lpush("ai_performance_metrics", str(metrics_data))
            await self.redis.ltrim("ai_performance_metrics", 0, 1999)  # Keep last 2000
        except Exception as e:
            logger.error(f"Error storing AI metrics: {e}")
    
    async def _store_application_metrics(self, metrics: ApplicationMetrics):
        """Store application metrics"""
        try:
            metrics_data = asdict(metrics)
            metrics_data['timestamp'] = metrics.timestamp.isoformat()
            
            await self.redis.lpush("application_metrics", str(metrics_data))
            await self.redis.ltrim("application_metrics", 0, 1999)  # Keep last 2000
        except Exception as e:
            logger.error(f"Error storing application metrics: {e}")
    
    async def _check_system_alerts(self, metrics: SystemMetrics):
        """Check for system alerts and notify if needed"""
        alerts = []
        
        if metrics.cpu_usage > 90:
            alerts.append(f"Critical CPU usage: {metrics.cpu_usage}%")
        
        if metrics.memory_usage > 90:
            alerts.append(f"Critical memory usage: {metrics.memory_usage}%")
        
        if metrics.disk_usage > 85:
            alerts.append(f"High disk usage: {metrics.disk_usage}%")
        
        if metrics.response_time > 10000:  # 10 seconds
            alerts.append(f"High response time: {metrics.response_time}ms")
        
        if metrics.error_rate > 10:  # 10%
            alerts.append(f"High error rate: {metrics.error_rate}%")
        
        if alerts:
            alert_message = f"SYSTEM ALERTS at {metrics.timestamp}: " + "; ".join(alerts)
            logger.warning(alert_message)
            
            # Store alert in Redis
            await self.redis.lpush("system_alerts", alert_message)
            await self.redis.ltrim("system_alerts", 0, 99)  # Keep last 100 alerts
    
    async def _scale_workers(self, direction: str):
        """Scale worker processes up or down"""
        try:
            current_workers = await self.redis.get("worker_count") or 4
            current_workers = int(current_workers)
            
            if direction == "up" and current_workers < 20:
                new_workers = min(current_workers + 2, 20)
                await self.redis.set("worker_count", new_workers)
                logger.info(f"Scaled workers up to {new_workers}")
                
            elif direction == "down" and current_workers > 2:
                new_workers = max(current_workers - 1, 2)
                await self.redis.set("worker_count", new_workers)
                logger.info(f"Scaled workers down to {new_workers}")
                
        except Exception as e:
            logger.error(f"Error scaling workers: {e}")
    
    async def _clear_old_cache(self):
        """Clear old cached data to free memory"""
        try:
            # Clear old cached job data
            await self.redis.eval("""
                local keys = redis.call('keys', 'job_cache:*')
                for i=1,#keys do
                    local ttl = redis.call('ttl', keys[i])
                    if ttl > 3600 then  -- If TTL > 1 hour, delete
                        redis.call('del', keys[i])
                    end
                end
                return #keys
            """, 0)
            
            logger.info("Cleared old cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    async def _optimize_database_connections(self):
        """Optimize database connection pool"""
        try:
            # This would implement database connection optimization
            # For now, just log the action
            logger.info("Optimized database connections")
            
        except Exception as e:
            logger.error(f"Error optimizing database connections: {e}")
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        try:
            summary = {
                "system_health": "good",
                "current_metrics": {},
                "trends": {},
                "recommendations": []
            }
            
            if self.metrics_history:
                latest = self.metrics_history[-1]
                summary["current_metrics"] = {
                    "cpu_usage": latest.cpu_usage,
                    "memory_usage": latest.memory_usage,
                    "response_time": latest.response_time,
                    "error_rate": latest.error_rate,
                    "throughput": latest.throughput
                }
                
                # Determine overall health
                if latest.cpu_usage > 80 or latest.memory_usage > 80 or latest.error_rate > 5:
                    summary["system_health"] = "warning"
                if latest.cpu_usage > 90 or latest.memory_usage > 90 or latest.error_rate > 10:
                    summary["system_health"] = "critical"
            
            # Calculate trends (last 10 metrics vs previous 10)
            if len(self.metrics_history) >= 20:
                recent = self.metrics_history[-10:]
                previous = self.metrics_history[-20:-10]
                
                recent_avg_cpu = sum(m.cpu_usage for m in recent) / len(recent)
                previous_avg_cpu = sum(m.cpu_usage for m in previous) / len(previous)
                
                summary["trends"]["cpu_trend"] = "up" if recent_avg_cpu > previous_avg_cpu else "down"
            
            # Add recommendations
            if self.metrics_history:
                latest = self.metrics_history[-1]
                if latest.cpu_usage > 70:
                    summary["recommendations"].append("Consider scaling up workers")
                if latest.response_time > 3000:
                    summary["recommendations"].append("Optimize database queries")
                if latest.error_rate > 3:
                    summary["recommendations"].append("Investigate error patterns")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return {"error": str(e)}

# Context manager for performance tracking
@asynccontextmanager
async def track_performance(operation_name: str, redis_client: redis.Redis):
    """Context manager to track operation performance"""
    start_time = time.time()
    success = False
    
    try:
        yield
        success = True
    except Exception as e:
        logger.error(f"Operation {operation_name} failed: {e}")
        raise
    finally:
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Store performance data
        await redis_client.lpush("response_times", duration)
        await redis_client.ltrim("response_times", 0, 999)  # Keep last 1000
        
        # Update request counters
        await redis_client.incr("total_requests_last_hour")
        await redis_client.expire("total_requests_last_hour", 3600)
        
        if not success:
            await redis_client.incr("error_requests_last_hour")
            await redis_client.expire("error_requests_last_hour", 3600)
        
        # Store per-operation metrics
        await redis_client.hset(
            f"operation_metrics:{operation_name}",
            mapping={
                "last_duration": duration,
                "last_success": success,
                "last_timestamp": datetime.utcnow().isoformat()
            }
        )

# Global performance monitor instance
performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global performance_monitor
    if performance_monitor is None:
        raise RuntimeError("Performance monitor not initialized")
    return performance_monitor

async def initialize_performance_monitor(redis_client: redis.Redis):
    """Initialize global performance monitor"""
    global performance_monitor
    performance_monitor = PerformanceMonitor(redis_client)
    logger.info("Performance monitor initialized")

async def start_performance_monitoring():
    """Start performance monitoring"""
    monitor = get_performance_monitor()
    await monitor.start_monitoring()

async def stop_performance_monitoring():
    """Stop performance monitoring"""
    monitor = get_performance_monitor()
    await monitor.stop_monitoring()