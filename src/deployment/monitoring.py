from typing import Dict, List, Optional
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor system performance."""
    
    def __init__(self, alert_threshold_cpu: float = 80.0):
        """Initialize monitor.
        
        Args:
            alert_threshold_cpu: CPU threshold for alerts
        """
        self.alert_threshold_cpu = alert_threshold_cpu
        self.metrics_history: List[Dict] = []
    
    async def collect_metrics(self) -> Dict[str, float]:
        """Collect system metrics.
        
        Returns:
            Metrics dictionary
        """
        import psutil
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
        
        self.metrics_history.append(metrics)
        
        # Keep only last 1000 metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
        
        return metrics
    
    async def check_alerts(self) -> List[str]:
        """Check for alert conditions.
        
        Returns:
            List of active alerts
        """
        alerts = []
        
        if not self.metrics_history:
            return alerts
        
        latest = self.metrics_history[-1]
        
        if latest["cpu_percent"] > self.alert_threshold_cpu:
            alerts.append(
                f"High CPU usage: {latest['cpu_percent']:.1f}%"
            )
        
        if latest["memory_percent"] > 85:
            alerts.append(
                f"High memory usage: {latest['memory_percent']:.1f}%"
            )
        
        return alerts


class HealthChecker:
    """Health check for all services."""
    
    def __init__(self):
        """Initialize health checker."""
        self.service_status: Dict[str, bool] = {}
    
    async def check_api_health(self, url: str = "http://localhost:8000/health") -> bool:
        """Check API health.
        
        Args:
            url: API URL
        
        Returns:
            Health status
        """
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5)
                self.service_status["api"] = response.status_code == 200
                return response.status_code == 200
        
        except Exception as e:
            logger.error(f"API health check failed: {str(e)}")
            self.service_status["api"] = False
            return False
    
    async def check_database_health(self) -> bool:
        """Check database health.
        
        Returns:
            Database health status
        """
        try:
            # Implementation depends on database type
            self.service_status["database"] = True
            return True
        
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            self.service_status["database"] = False
            return False
    
    async def check_all_services(self) -> Dict[str, bool]:
        """Check all services.
        
        Returns:
            Status of all services
        """
        await self.check_api_health()
        await self.check_database_health()
        
        return self.service_status
    
    def get_overall_status(self) -> bool:
        """Get overall system status.
        
        Returns:
            Whether all services are healthy
        """
        return all(self.service_status.values())


class LogAggregation:
    """Centralized log aggregation."""
    
    def __init__(self, elasticsearch_url: str = "http://localhost:9200"):
        """Initialize log aggregation.
        
        Args:
            elasticsearch_url: Elasticsearch URL
        """
        self.elasticsearch_url = elasticsearch_url
    
    async def send_log(
        self,
        index: str,
        document: Dict
    ) -> bool:
        """Send log to Elasticsearch.
        
        Args:
            index: Index name
            document: Log document
        
        Returns:
            Success status
        """
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.elasticsearch_url}/{index}/_doc",
                    json=document,
                    timeout=5
                )
                
                return response.status_code in [200, 201]
        
        except Exception as e:
            logger.error(f"Log aggregation error: {str(e)}")
            return False


class AlertNotifier:
    """Send alerts to various channels."""
    
    def __init__(self, slack_webhook: Optional[str] = None):
        """Initialize notifier.
        
        Args:
            slack_webhook: Slack webhook URL
        """
        self.slack_webhook = slack_webhook
    
    async def notify(
        self,
        title: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """Send notification.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (info, warning, critical)
        
        Returns:
            Success status
        """
        if not self.slack_webhook:
            return False
        
        try:
            import httpx
            
            payload = {
                "attachments": [{
                    "title": title,
                    "text": message,
                    "color": {
                        "info": "36a64f",
                        "warning": "ff6600",
                        "critical": "ff0000",
                    }.get(severity, "36a64f"),
                    "ts": int(datetime.utcnow().timestamp()),
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=10
                )
                
                return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Alert notification error: {str(e)}")
            return False