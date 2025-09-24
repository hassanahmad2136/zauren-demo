# apps/message_bus/middleware/auth.py
"""
Authentication middleware for message bus
Handles tenant API key validation and channel permissions
"""

import hashlib
import hmac
import time
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from core.database.redis_client import RedisClient
from config.settings import settings

class TenantAuthManager:
    """Manages tenant authentication and permissions"""
    
    def __init__(self):
        self.redis_client = RedisClient()
        self.cache_ttl = 300  # 5 minutes
    
    async def get_tenant_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant configuration from cache or database
        In production, this would query your tenant database
        """
        cache_key = f"tenant_config:{tenant_id}"
        
        # Try cache first
        cached_config = await self.redis_client.get(cache_key)
        if cached_config:
            return cached_config
        
        # Simulate database lookup - replace with actual DB query
        tenant_configs = {
            "test_retailer": {
                "tenant_id": "test_retailer",
                "name": "Test Retailer",
                "api_keys": {
                    "whatsapp": "test_whatsapp_key_123",
                    "web": "test_web_key_456", 
                    "facebook": "test_facebook_key_789",
                    "telegram": "test_telegram_key_abc",
                    "instagram": "test_instagram_key_def",
                    "sms": "test_sms_key_ghi",
                    "console": "test_key"
                },
                "enabled_channels": ["whatsapp", "web", "facebook", "telegram", "console"],
                "rate_limits": {
                    "whatsapp": {"requests_per_minute": 60, "requests_per_hour": 1000},
                    "web": {"requests_per_minute": 100, "requests_per_hour": 2000},
                    "facebook": {"requests_per_minute": 60, "requests_per_hour": 1000},
                    "telegram": {"requests_per_minute": 30, "requests_per_hour": 500},
                    "console": {"requests_per_minute": 1000, "requests_per_hour": 10000}
                },
                "webhook_secrets": {
                    "whatsapp": "whatsapp_webhook_secret",
                    "facebook": "facebook_webhook_secret"
                },
                "features": {
                    "message_encryption": True,
                    "pii_redaction": True,
                    "audit_logging": True
                },
                "created_at": "2024-01-01T00:00:00Z",
                "status": "active"
            },
            "walmart_store_123": {
                "tenant_id": "walmart_store_123",
                "name": "Walmart Store #123",
                "api_keys": {
                    "whatsapp": "walmart_wa_key_xyz789",
                    "web": "walmart_web_key_abc123",
                    "sms": "walmart_sms_key_def456"
                },
                "enabled_channels": ["whatsapp", "web", "sms"],
                "rate_limits": {
                    "whatsapp": {"requests_per_minute": 200, "requests_per_hour": 5000},
                    "web": {"requests_per_minute": 500, "requests_per_hour": 10000},
                    "sms": {"requests_per_minute": 100, "requests_per_hour": 2000}
                },
                "webhook_secrets": {
                    "whatsapp": "walmart_wa_webhook_secret_xyz"
                },
                "features": {
                    "message_encryption": True,
                    "pii_redaction": True,
                    "audit_logging": True,
                    "premium_support": True
                },
                "status": "active"
            }
        }
        
        config = tenant_configs.get(tenant_id)
        if config:
            # Cache the config
            await self.redis_client.set(cache_key, config, ttl=self.cache_ttl)
        
        return config
    
    async def validate_api_key(self, tenant_id: str, api_key: str, channel: str) -> bool:
        """Validate API key for tenant and channel"""
        tenant_config = await self.get_tenant_config(tenant_id)
        
        if not tenant_config:
            return False
        
        if tenant_config.get("status") != "active":
            return False
        
        # Check if channel is enabled for tenant
        if channel not in tenant_config.get("enabled_channels", []):
            return False
        
        # Validate API key
        expected_key = tenant_config.get("api_keys", {}).get(channel)
        if not expected_key:
            return False
        
        return hmac.compare_digest(api_key, expected_key)
    
    async def verify_webhook_signature(self, tenant_id: str, channel: str, 
                                     payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature for channels that support it (WhatsApp, Facebook)
        """
        tenant_config = await self.get_tenant_config(tenant_id)
        if not tenant_config:
            return False
        
        webhook_secret = tenant_config.get("webhook_secrets", {}).get(channel)
        if not webhook_secret:
            return True  # If no secret configured, skip verification
        
        if channel == "whatsapp":
            # WhatsApp signature format: sha256=<signature>
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            return signature == f"sha256={expected_signature}"
        
        elif channel == "facebook":
            # Facebook signature format: sha1=<signature>
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha1
            ).hexdigest()
            return signature == f"sha1={expected_signature}"
        
        return True
    
    async def get_channel_permissions(self, tenant_id: str, channel: str) -> Dict[str, Any]:
        """Get specific permissions for tenant and channel"""
        tenant_config = await self.get_tenant_config(tenant_id)
        if not tenant_config:
            return {}
        
        return {
            "enabled": channel in tenant_config.get("enabled_channels", []),
            "rate_limits": tenant_config.get("rate_limits", {}).get(channel, {}),
            "features": tenant_config.get("features", {}),
            "webhook_secret_configured": bool(
                tenant_config.get("webhook_secrets", {}).get(channel)
            )
        }

# Global auth manager instance
auth_manager = TenantAuthManager()

async def verify_tenant_token(tenant_id: str, api_key: str, channel: str) -> Dict[str, Any]:
    """
    Verify tenant authentication token and return tenant info
    """
    if not tenant_id or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing tenant ID or API key"
        )
    
    # Validate API key
    is_valid = await auth_manager.validate_api_key(tenant_id, api_key, channel)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant ID, API key, or channel not enabled"
        )
    
    # Get tenant configuration
    tenant_config = await auth_manager.get_tenant_config(tenant_id)
    if not tenant_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check tenant status
    if tenant_config.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant status: {tenant_config.get('status')}"
        )
    
    # Return safe tenant info (no secrets)
    return {
        "tenant_id": tenant_config["tenant_id"],
        "name": tenant_config["name"],
        "enabled_channels": tenant_config["enabled_channels"],
        "features": tenant_config["features"],
        "authenticated_at": datetime.now().isoformat()
    }

async def verify_webhook_signature(tenant_id: str, channel: str, 
                                 payload: bytes, signature: Optional[str] = None) -> bool:
    """
    Verify webhook signature for secure channels
    """
    if not signature:
        return True  # Skip verification if no signature provided
    
    return await auth_manager.verify_webhook_signature(tenant_id, channel, payload, signature)

class APIKeyRotationManager:
    """Manages API key rotation for tenants"""
    
    def __init__(self):
        self.redis_client = RedisClient()
    
    async def rotate_api_key(self, tenant_id: str, channel: str) -> Dict[str, str]:
        """
        Rotate API key for tenant and channel
        In production, this would update the database
        """
        import secrets
        import string
        
        # Generate new API key
        alphabet = string.ascii_letters + string.digits
        new_key = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # In production, update database here
        # For now, just return the new key
        
        # Invalidate cache
        cache_key = f"tenant_config:{tenant_id}"
        await self.redis_client.delete(cache_key)
        
        return {
            "tenant_id": tenant_id,
            "channel": channel,
            "new_api_key": new_key,
            "rotated_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
        }
    
    async def list_api_keys(self, tenant_id: str) -> Dict[str, Any]:
        """List all API keys for tenant (masked)"""
        tenant_config = await auth_manager.get_tenant_config(tenant_id)
        if not tenant_config:
            return {}
        
        api_keys = tenant_config.get("api_keys", {})
        
        # Mask API keys for security
        masked_keys = {}
        for channel, key in api_keys.items():
            if len(key) > 8:
                masked_keys[channel] = f"{key[:4]}****{key[-4:]}"
            else:
                masked_keys[channel] = "****"
        
        return {
            "tenant_id": tenant_id,
            "api_keys": masked_keys,
            "enabled_channels": tenant_config.get("enabled_channels", [])
        }

# Security utilities
def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure token"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "_-"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_api_key(api_key: str, salt: str = None) -> str:
    """Hash API key for secure storage"""
    if not salt:
        salt = generate_secure_token(16)
    
    hashed = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt.encode(), 100000)
    return f"{salt}:{hashed.hex()}"

def verify_hashed_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify API key against hash"""
    try:
        salt, hash_hex = hashed_key.split(':', 1)
        hash_bytes = bytes.fromhex(hash_hex)
        expected_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt.encode(), 100000)
        return hmac.compare_digest(hash_bytes, expected_hash)
    except (ValueError, TypeError):
        return False