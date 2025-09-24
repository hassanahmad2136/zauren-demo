# core/database/redis_client.py
"""
Redis client for caching, rate limiting, and session management
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis
from config.settings import settings

class RedisClient:
    """Async Redis client wrapper with utility methods"""
    
    def __init__(self):
        self.redis = None
        self._connection_pool = None
    
    async def connect(self):
        """Initialize Redis connection"""
        if self.redis is None:
            self._connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.redis = redis.Redis(connection_pool=self._connection_pool)
            
            # Test connection
            try:
                await self.redis.ping()
                print(f"✅ Connected to Redis: {settings.redis_url}")
            except Exception as e:
                print(f"❌ Redis connection failed: {e}")
                raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            if self._connection_pool:
                await self._connection_pool.disconnect()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis, auto-deserialize JSON"""
        await self._ensure_connected()
        value = await self.redis.get(key)
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis, auto-serialize objects"""
        await self._ensure_connected()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if ttl:
            return await self.redis.setex(key, ttl, value)
        else:
            return await self.redis.set(key, value)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys from Redis"""
        await self._ensure_connected()
        return await self.redis.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        await self._ensure_connected()
        return await self.redis.exists(key)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key"""
        await self._ensure_connected()
        return await self.redis.expire(key, seconds)
    
    # Sorted Set operations for rate limiting
    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Add to sorted set"""
        await self._ensure_connected()
        return await self.redis.zadd(key, mapping)
    
    async def zcard(self, key: str) -> int:
        """Get sorted set size"""
        await self._ensure_connected()
        return await self.redis.zcard(key)
    
    async def zremrangebyscore(self, key: str, min_score: Union[str, float], 
                              max_score: Union[str, float]) -> int:
        """Remove elements by score range"""
        await self._ensure_connected()
        return await self.redis.zremrangebyscore(key, min_score, max_score)
    
    # List operations for logging
    async def lpush(self, key: str, *values: str) -> int:
        """Push to left of list"""
        await self._ensure_connected()
        return await self.redis.lpush(key, *values)
    
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get range from list"""
        await self._ensure_connected()
        return await self.redis.lrange(key, start, end)
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim list to range"""
        await self._ensure_connected()
        return await self.redis.ltrim(key, start, end)
    
    # Utility methods
    async def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        await self._ensure_connected()
        return await self.redis.keys(pattern)
    
    async def flushdb(self) -> bool:
        """Flush current database (use with caution!)"""
        await self._ensure_connected()
        return await self.redis.flushdb()
    
    async def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis info"""
        await self._ensure_connected()
        return await self.redis.info(section)
    
    async def _ensure_connected(self):
        """Ensure Redis connection is active"""
        if self.redis is None:
            await self.connect()

# Global Redis client instance
redis_client = RedisClient()