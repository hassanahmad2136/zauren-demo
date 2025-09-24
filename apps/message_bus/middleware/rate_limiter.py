# apps/message_bus/middleware/rate_limiter.py
"""
Complete Rate limiting middleware for message bus
Implements per-tenant, per-channel rate limiting using Redis with sliding window algorithm
"""

import time
import json
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from core.database.redis_client import RedisClient
from config.settings import settings

class RateLimiter:
    """
    Redis-based rate limiter with sliding window algorithm
    Supports per-tenant, per-channel rate limiting with multiple time windows
    """
    
    def __init__(self):
        self.redis_client = RedisClient()
        self.default_limits = {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "requests_per_day": 10000
        }
    
    async def check_rate_limit(self, tenant_id: str, channel: str, 
                             custom_limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """
        Check if request is within rate limits
        Raises HTTPException if limit exceeded
        Returns current usage stats
        """
        limits = custom_limits or await self._get_tenant_limits(tenant_id, channel)
        
        current_time = int(time.time())
        
        # Check all time windows
        for window_name, limit in limits.items():
            if limit <= 0:  # Skip if limit is 0 or negative
                continue
                
            window_seconds = self._get_window_seconds(window_name)
            if not window_seconds:
                continue
            
            current_count = await self._get_request_count(
                tenant_id, channel, window_seconds, current_time
            )
            
            if current_count >= limit:
                # Calculate reset time
                reset_time = current_time + window_seconds
                
                # Log rate limit hit
                await self._log_rate_limit_hit(tenant_id, channel, window_name, current_count, limit)
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {window_name}. Limit: {limit}, Current: {current_count}",
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                        "X-RateLimit-Window": window_name,
                        "Retry-After": str(window_seconds)
                    }
                )
        
        # Record the request
        await self._record_request(tenant_id, channel, current_time)
        
        # Return current usage stats
        usage_stats = await self._get_usage_stats(tenant_id, channel, limits, current_time)
        return usage_stats
    
    async def _get_tenant_limits(self, tenant_id: str, channel: str) -> Dict[str, int]:
        """Get rate limits for tenant and channel from config or cache"""
        cache_key = f"rate_limits:{tenant_id}:{channel}"
        
        # Try cache first
        cached_limits = await self.redis_client.get(cache_key)
        if cached_limits:
            return cached_limits
        
        # In production, this would query tenant configuration database
        # For now, return predefined tenant-specific limits
        tenant_limits = {
            "test_retailer": {
                "whatsapp": {"requests_per_minute": 60, "requests_per_hour": 1000, "requests_per_day": 5000},
                "web": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000},
                "facebook": {"requests_per_minute": 60, "requests_per_hour": 1000, "requests_per_day": 5000},
                "telegram": {"requests_per_minute": 30, "requests_per_hour": 500, "requests_per_day": 2000},
                "console": {"requests_per_minute": 1000, "requests_per_hour": 10000, "requests_per_day": 50000}
            },
            "walmart_store_123": {
                "whatsapp": {"requests_per_minute": 200, "requests_per_hour": 5000, "requests_per_day": 25000},
                "web": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "sms": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000}
            },
            "premium_retailer": {
                "whatsapp": {"requests_per_minute": 1000, "requests_per_hour": 20000, "requests_per_day": 100000},
                "web": {"requests_per_minute": 2000, "requests_per_hour": 50000, "requests_per_day": 200000},
                "facebook": {"requests_per_minute": 1000, "requests_per_hour": 20000, "requests_per_day": 100000},
                "telegram": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "instagram": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "sms": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000}
            }
        }
        
        limits = tenant_limits.get(tenant_id, {}).get(channel, self.default_limits)
        
        # Cache the limits
        await self.redis_client.set(cache_key, limits, ttl=300)  # 5 minutes
        
        return limits
    
    def _get_window_seconds(self, window_name: str) -> Optional[int]:
        """Convert window name to seconds"""
        window_map = {
            "requests_per_minute": 60,
            "requests_per_hour": 3600,
            "requests_per_day": 86400,
            "requests_per_week": 604800
        }
        return window_map.get(window_name)
    
    async def _get_request_count(self, tenant_id: str, channel: str, 
                               window_seconds: int, current_time: int) -> int:
        """Get current request count for sliding window using Redis sorted sets"""
        key = f"rate_limit:{tenant_id}:{channel}:{window_seconds}"
        
        # Remove old entries outside the sliding window
        cutoff_time = current_time - window_seconds
        await self.redis_client.zremrangebyscore(key, "-inf", cutoff_time)
        
        # Count current entries in the window
        count = await self.redis_client.zcard(key)
        return count
    
    async def _record_request(self, tenant_id: str, channel: str, timestamp: int):
        """Record a request in all relevant time windows"""
        windows = [60, 3600, 86400, 604800]  # minute, hour, day, week
        
        for window_seconds in windows:
            key = f"rate_limit:{tenant_id}:{channel}:{window_seconds}"
            
            # Add current request with timestamp as both score and member
            # Using unique member to avoid collisions in the same second
            member = f"{timestamp}:{time.time_ns()}"
            await self.redis_client.zadd(key, {member: timestamp})
            
            # Set expiration to window size + small buffer
            await self.redis_client.expire(key, window_seconds + 60)
    
    async def _get_usage_stats(self, tenant_id: str, channel: str, 
                             limits: Dict[str, int], current_time: int) -> Dict[str, Any]:
        """Get current usage statistics for monitoring"""
        stats = {
            "tenant_id": tenant_id,
            "channel": channel,
            "timestamp": current_time,
            "windows": {}
        }
        
        for window_name, limit in limits.items():
            window_seconds = self._get_window_seconds(window_name)
            if not window_seconds:
                continue
                
            current_count = await self._get_request_count(
                tenant_id, channel, window_seconds, current_time
            )
            
            remaining = max(0, limit - current_count)
            usage_percent = round((current_count / limit) * 100, 2) if limit > 0 else 0
            
            stats["windows"][window_name] = {
                "limit": limit,
                "used": current_count,
                "remaining": remaining,
                "usage_percent": usage_percent,
                "reset_at": current_time + window_seconds,
                "window_seconds": window_seconds
            }
        
        return stats
    
    async def _log_rate_limit_hit(self, tenant_id: str, channel: str, 
                                window_name: str, current_count: int, limit: int):
        """Log rate limit violations for monitoring and alerting"""
        log_entry = {
            "event": "rate_limit_exceeded",
            "tenant_id": tenant_id,
            "channel": channel,
            "window": window_name,
            "current_count": current_count,
            "limit": limit,
            "usage_percent": round((current_count / limit) * 100, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        # Store in Redis list for monitoring dashboard
        log_key = f"rate_limit_violations:{tenant_id}"
        await self.redis_client.lpush(log_key, json.dumps(log_entry))
        await self.redis_client.ltrim(log_key, 0, 999)  # Keep last 1000 entries
        await self.redis_client.expire(log_key, 86400)  # 24 hours
        
        # Also store global violations for system monitoring
        global_log_key = "rate_limit_violations:global"
        await self.redis_client.lpush(global_log_key, json.dumps(log_entry))
        await self.redis_client.ltrim(global_log_key, 0, 9999)  # Keep last 10K entries
        await self.redis_client.expire(global_log_key, 86400 * 7)  # 1 week
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive rate limiting metrics for monitoring dashboard"""
        current_time = int(time.time())
        
        # Get all rate limit keys
        pattern = "rate_limit:*"
        keys = await self.redis_client.keys(pattern)
        
        metrics = {
            "timestamp": current_time,
            "total_active_limits": len(keys),
            "tenants": {},
            "channels": {},
            "global_stats": {
                "total_requests_last_hour": 0,
                "total_requests_last_day": 0,
                "violations_last_hour": 0
            }
        }
        
        # Aggregate metrics by tenant and channel
        tenant_channels = {}
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 4:
                tenant_id = parts[1]
                channel = parts[2]
                window = int(parts[3])
                
                if tenant_id not in tenant_channels:
                    tenant_channels[tenant_id] = set()
                tenant_channels[tenant_id].add(channel)
                
                if tenant_id not in metrics["tenants"]:
                    metrics["tenants"][tenant_id] = {
                        "channels": {},
                        "total_requests_hour": 0,
                        "total_requests_day": 0
                    }
                
                if channel not in metrics["channels"]:
                    metrics["channels"][channel] = {
                        "tenants": set(),
                        "total_requests_hour": 0,
                        "total_requests_day": 0
                    }
                
                # Get request counts for different windows
                if window == 3600:  # 1 hour
                    count = await self._get_request_count(tenant_id, channel, window, current_time)
                    metrics["tenants"][tenant_id]["total_requests_hour"] += count
                    metrics["channels"][channel]["total_requests_hour"] += count
                    metrics["global_stats"]["total_requests_last_hour"] += count
                
                elif window == 86400:  # 1 day
                    count = await self._get_request_count(tenant_id, channel, window, current_time)
                    metrics["tenants"][tenant_id]["total_requests_day"] += count
                    metrics["channels"][channel]["total_requests_day"] += count
                    metrics["global_stats"]["total_requests_last_day"] += count
                
                metrics["channels"][channel]["tenants"].add(tenant_id)
        
        # Convert sets to counts and add channel info to tenants
        for tenant_id, channels in tenant_channels.items():
            metrics["tenants"][tenant_id]["channels"] = list(channels)
            metrics["tenants"][tenant_id]["channel_count"] = len(channels)
        
        for channel_data in metrics["channels"].values():
            channel_data["tenants"] = len(channel_data["tenants"])
        
        # Get violation count for last hour
        violations_key = "rate_limit_violations:global"
        violations = await self.redis_client.lrange(violations_key, 0, -1)
        hour_ago = current_time - 3600
        
        violations_last_hour = 0
        for violation_json in violations:
            try:
                violation = json.loads(violation_json)
                violation_time = datetime.fromisoformat(violation["timestamp"]).timestamp()
                if violation_time >= hour_ago:
                    violations_last_hour += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        
        metrics["global_stats"]["violations_last_hour"] = violations_last_hour
        
        return metrics
    
    async def reset_tenant_limits(self, tenant_id: str, channel: Optional[str] = None) -> Dict[str, Any]:
        """Reset rate limits for tenant (admin function)"""
        if channel:
            # Reset specific channel
            patterns = [f"rate_limit:{tenant_id}:{channel}:*"]
        else:
            # Reset all channels for tenant
            patterns = [f"rate_limit:{tenant_id}:*"]
        
        deleted_keys = 0
        for pattern in patterns:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted_keys += await self.redis_client.delete(*keys)
        
        return {
            "tenant_id": tenant_id,
            "channel": channel,
            "deleted_keys": deleted_keys,
            "reset_at": datetime.now().isoformat()
        }
    
    async def get_tenant_usage(self, tenant_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get detailed usage statistics for specific tenant"""
        current_time = int(time.time())
        start_time = current_time - (hours * 3600)
        
        usage = {
            "tenant_id": tenant_id,
            "period_hours": hours,
            "start_time": start_time,
            "end_time": current_time,
            "channels": {},
            "limits": {}
        }
        
        # Get all channels for this tenant
        pattern = f"rate_limit:{tenant_id}:*"
        keys = await self.redis_client.keys(pattern)
        
        channels = set()
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 3:
                channel = parts[2]
                if not channel.isdigit():  # Skip window size suffixes
                    channels.add(channel)
        
        # Get usage and limits for each channel
        for channel in channels:
            channel_usage = {
                "total_requests": 0,
                "windows": {},
                "limits": await self._get_tenant_limits(tenant_id, channel)
            }
            
            # Check different time windows
            for window_name, window_seconds in [
                ("last_hour", 3600),
                ("last_6_hours", 21600), 
                ("last_24_hours", 86400)
            ]:
                if window_seconds <= hours * 3600:
                    count = await self._get_request_count(
                        tenant_id, channel, window_seconds, current_time
                    )
                    channel_usage["windows"][window_name] = count
                    if window_name == "last_24_hours":
                        channel_usage["total_requests"] = count
            
            usage["channels"][channel] = channel_usage
            usage["limits"][channel] = channel_usage["limits"]
        
        return usage
    
    async def predict_rate_limit_hit(self, tenant_id: str, channel: str, 
                                   minutes_ahead: int = 60) -> Dict[str, Any]:
        """Predict if tenant will hit rate limit in the near future"""
        current_time = int(time.time())
        limits = await self._get_tenant_limits(tenant_id, channel)
        
        predictions = {}
        
        for window_name, limit in limits.items():
            window_seconds = self._get_window_seconds(window_name)
            if not window_seconds:
                continue
            
            # Get current usage
            current_count = await self._get_request_count(
                tenant_id, channel, window_seconds, current_time
            )
            
            # Calculate recent rate (requests per minute in last 10 minutes)
            recent_count = await self._get_request_count(
                tenant_id, channel, 600, current_time  # Last 10 minutes
            )
            recent_rate_per_minute = recent_count / 10
            
            # Predict usage after specified minutes
            predicted_requests = recent_rate_per_minute * minutes_ahead
            predicted_total = current_count + predicted_requests
            
            predictions[window_name] = {
                "current_count": current_count,
                "limit": limit,
                "recent_rate_per_minute": round(recent_rate_per_minute, 2),
                "predicted_total_after_minutes": round(predicted_total),
                "will_hit_limit": predicted_total >= limit,
                "minutes_until_limit": max(0, round((limit - current_count) / recent_rate_per_minute)) if recent_rate_per_minute > 0 else float('inf')
            }
        
        return {
            "tenant_id": tenant_id,
            "channel": channel,
            "prediction_window_minutes": minutes_ahead,
            "predictions": predictions,
            "timestamp": current_time
        }

class RateLimitConfig:
    """Configuration manager for rate limits with different tiers and validation"""
    
    @staticmethod
    def create_tier_limits(tier: str) -> Dict[str, Dict[str, int]]:
        """Create rate limits based on subscription tier"""
        tiers = {
            "free": {
                "whatsapp": {"requests_per_minute": 10, "requests_per_hour": 100, "requests_per_day": 500},
                "web": {"requests_per_minute": 20, "requests_per_hour": 200, "requests_per_day": 1000},
                "sms": {"requests_per_minute": 5, "requests_per_hour": 50, "requests_per_day": 200}
            },
            "basic": {
                "whatsapp": {"requests_per_minute": 60, "requests_per_hour": 1000, "requests_per_day": 5000},
                "web": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000},
                "facebook": {"requests_per_minute": 60, "requests_per_hour": 1000, "requests_per_day": 5000},
                "sms": {"requests_per_minute": 30, "requests_per_hour": 300, "requests_per_day": 1500}
            },
            "premium": {
                "whatsapp": {"requests_per_minute": 200, "requests_per_hour": 5000, "requests_per_day": 25000},
                "web": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "facebook": {"requests_per_minute": 200, "requests_per_hour": 5000, "requests_per_day": 25000},
                "telegram": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000},
                "instagram": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000},
                "sms": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000}
            },
            "enterprise": {
                "whatsapp": {"requests_per_minute": 1000, "requests_per_hour": 20000, "requests_per_day": 100000},
                "web": {"requests_per_minute": 2000, "requests_per_hour": 50000, "requests_per_day": 200000},
                "facebook": {"requests_per_minute": 1000, "requests_per_hour": 20000, "requests_per_day": 100000},
                "telegram": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "instagram": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "sms": {"requests_per_minute": 500, "requests_per_hour": 10000, "requests_per_day": 50000},
                "email": {"requests_per_minute": 100, "requests_per_hour": 2000, "requests_per_day": 10000}
            }
        }
        
        return tiers.get(tier, tiers["basic"])
    
    @staticmethod
    def validate_limits(limits: Dict[str, int]) -> Tuple[bool, List[str]]:
        """Validate rate limit configuration and return errors if any"""
        errors = []
        required_keys = ["requests_per_minute", "requests_per_hour"]
        
        for key in required_keys:
            if key not in limits:
                errors.append(f"Missing required limit: {key}")
                continue
            
            if not isinstance(limits[key], int) or limits[key] < 0:
                errors.append(f"Invalid value for {key}: must be non-negative integer")
        
        if not errors:
            # Logical validation
            if limits["requests_per_minute"] * 60 > limits["requests_per_hour"]:
                errors.append("requests_per_minute * 60 cannot exceed requests_per_hour")
            
            if "requests_per_day" in limits:
                if limits["requests_per_hour"] * 24 > limits["requests_per_day"]:
                    errors.append("requests_per_hour * 24 cannot exceed requests_per_day")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def calculate_burst_allowance(base_limit: int, burst_factor: float = 1.5) -> int:
        """Calculate burst allowance for temporary rate limit increases"""
        return int(base_limit * burst_factor)

# Global rate limiter instance
rate_limiter = RateLimiter()