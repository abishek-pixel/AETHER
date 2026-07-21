from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Distribute requests across instances."""
    
    def __init__(self, instances: List[str]):
        """Initialize load balancer.
        
        Args:
            instances: List of instance URLs
        """
        self.instances = instances
        self.current_index = 0
    
    def get_next_instance(self) -> str:
        """Get next instance using round-robin.
        
        Returns:
            Instance URL
        """
        instance = self.instances[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.instances)
        return instance
    
    async def get_least_loaded_instance(self) -> str:
        """Get least loaded instance.
        
        Returns:
            Instance URL
        """
        import httpx
        
        loads = {}
        
        for instance in self.instances:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{instance}/metrics/load", timeout=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        loads[instance] = data.get("load", float('inf'))
                    else:
                        loads[instance] = float('inf')
            
            except Exception:
                loads[instance] = float('inf')
        
        return min(loads, key=loads.get)


class CacheStrategy:
    """Implement caching for performance."""
    
    def __init__(self, cache_type: str = "redis"):
        """Initialize cache.
        
        Args:
            cache_type: Type of cache (redis, memcached, etc.)
        """
        self.cache_type = cache_type
        self.local_cache: Dict[str, Any] = {}
    
    async def get_cached_result(self, query: str) -> Any:
        """Get cached research result.
        
        Args:
            query: Research query
        
        Returns:
            Cached result or None
        """
        # Check local cache first
        cache_key = f"query:{query}"
        
        if cache_key in self.local_cache:
            return self.local_cache[cache_key]
        
        # Check Redis
        if self.cache_type == "redis":
            try:
                import redis
                
                r = redis.Redis(host='localhost', port=6379, db=0)
                cached = r.get(cache_key)
                
                if cached:
                    import json
                    return json.loads(cached)
            
            except Exception as e:
                logger.warning(f"Redis cache error: {str(e)}")
        
        return None
    
    async def cache_result(
        self,
        query: str,
        result: Any,
        ttl: int = 3600
    ) -> bool:
        """Cache research result.
        
        Args:
            query: Research query
            result: Result to cache
            ttl: Time to live in seconds
        
        Returns:
            Success status
        """
        cache_key = f"query:{query}"
        
        # Cache locally
        self.local_cache[cache_key] = result
        
        # Cache in Redis
        if self.cache_type == "redis":
            try:
                import redis
                import json
                
                r = redis.Redis(host='localhost', port=6379, db=0)
                r.setex(cache_key, ttl, json.dumps(result, default=str))
                return True
            
            except Exception as e:
                logger.warning(f"Redis cache error: {str(e)}")
        
        return True


class AutoScaler:
    """Automatically scale based on load."""
    
    def __init__(self):
        """Initialize autoscaler."""
        self.min_instances = 2
        self.max_instances = 10
        self.current_instances = 2
    
    async def decide_scaling(self, metrics: Dict[str, float]) -> str:
        """Decide whether to scale up or down.
        
        Args:
            metrics: Current metrics
        
        Returns:
            Action (scale_up, scale_down, maintain)
        """
        avg_load = metrics.get("avg_cpu_load", 0)
        queue_length = metrics.get("queue_length", 0)
        
        # Scale up if load is high
        if avg_load > 75 or queue_length > 100:
            if self.current_instances < self.max_instances:
                self.current_instances += 1
                return "scale_up"
        
        # Scale down if load is low
        elif avg_load < 25 and queue_length < 10:
            if self.current_instances > self.min_instances:
                self.current_instances -= 1
                return "scale_down"
        
        return "maintain"