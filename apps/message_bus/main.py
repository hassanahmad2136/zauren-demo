# apps/message_bus/main.py
"""
Message Bus - Complete Ingress Implementation
Receives raw messages from different channels and normalizes them to CanonicalMessage format
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.models.message import CanonicalMessage
from apps.message_bus.ingress.normalizer import MessageNormalizer
from apps.message_bus.middleware.auth import verify_tenant_token
from apps.message_bus.middleware.rate_limiter import RateLimiter
from apps.message_bus.middleware.logging_middleware import setup_logging
from config.settings import settings

# Setup logging
logger = setup_logging()

# Initialize services
normalizer = MessageNormalizer()
rate_limiter = RateLimiter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("🚀 Message Bus starting up...")
    yield
    logger.info("📴 Message Bus shutting down...")

app = FastAPI(
    title="Retail AI - Message Bus",
    description="Message normalization service for multi-channel input",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = datetime.now()
    
    # Get tenant info from headers
    tenant_id = request.headers.get("x-tenant-id", "unknown")
    channel = request.url.path.split("/")[-1] if "/" in request.url.path else "unknown"
    
    logger.info(
        f"📥 Ingress request",
        extra={
            "tenant_id": tenant_id,
            "channel": channel,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host
        }
    )
    
    response = await call_next(request)
    
    process_time = (datetime.now() - start_time).total_seconds()
    
    logger.info(
        f"📤 Ingress response",
        extra={
            "tenant_id": tenant_id,
            "channel": channel,
            "status_code": response.status_code,
            "process_time": process_time
        }
    )
    
    return response

# Health and Status Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "message_bus_ingress",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }

@app.get("/metrics")
async def get_metrics():
    """Basic metrics endpoint"""
    return await rate_limiter.get_metrics()

# Channel Normalization Endpoints
@app.post("/normalize/whatsapp")
async def normalize_whatsapp(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize WhatsApp Business API webhook data to CanonicalMessage
    
    Expected WhatsApp format:
    {
        "messages": [{
            "from": "1234567890",
            "body": "Hello world",
            "timestamp": "1234567890",
            "id": "message_id_123",
            "type": "text"
        }],
        "contacts": [{
            "profile": {"name": "John Doe"}
        }]
    }
    """
    # Rate limiting
    await rate_limiter.check_rate_limit(tenant_id, "whatsapp")
    
    # Authentication
    await verify_tenant_token(tenant_id, api_key, "whatsapp")
    
    try:
        canonical_message = await normalizer.normalize_whatsapp(raw_data, tenant_id)
        
        logger.info(
            f"✅ WhatsApp message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "message_length": len(canonical_message.content)
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(
            f"❌ WhatsApp normalization failed: {str(e)}",
            extra={"tenant_id": tenant_id, "raw_data": raw_data}
        )
        raise HTTPException(status_code=400, detail=f"WhatsApp normalization failed: {str(e)}")

@app.post("/normalize/web")
async def normalize_web(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize web widget data to CanonicalMessage
    
    Expected web format:
    {
        "session_id": "web_session_123",
        "message": "I need help with my order",
        "user_info": {
            "email": "john@example.com",
            "name": "John Doe"
        },
        "page_info": {
            "url": "https://store.com/products/shoes",
            "title": "Nike Shoes - Store"
        }
    }
    """
    await rate_limiter.check_rate_limit(tenant_id, "web")
    await verify_tenant_token(tenant_id, api_key, "web")
    
    try:
        canonical_message = await normalizer.normalize_web(raw_data, tenant_id, request)
        
        logger.info(
            f"✅ Web message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "session_id": raw_data.get("session_id")
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ Web normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Web normalization failed: {str(e)}")

@app.post("/normalize/facebook")
async def normalize_facebook(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize Facebook Messenger webhook data to CanonicalMessage
    
    Expected Facebook format:
    {
        "messaging": [{
            "sender": {"id": "1234567890"},
            "recipient": {"id": "PAGE_ID"},
            "timestamp": 1234567890123,
            "message": {
                "mid": "message_id",
                "text": "Hello",
                "attachments": []
            }
        }]
    }
    """
    await rate_limiter.check_rate_limit(tenant_id, "facebook")
    await verify_tenant_token(tenant_id, api_key, "facebook")
    
    try:
        canonical_message = await normalizer.normalize_facebook(raw_data, tenant_id)
        
        logger.info(
            f"✅ Facebook message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "sender_id": raw_data["messaging"][0]["sender"]["id"]
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ Facebook normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Facebook normalization failed: {str(e)}")

@app.post("/normalize/telegram")
async def normalize_telegram(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize Telegram bot webhook data to CanonicalMessage
    
    Expected Telegram format:
    {
        "update_id": 123456,
        "message": {
            "message_id": 789,
            "from": {
                "id": 987654321,
                "first_name": "John",
                "username": "johndoe"
            },
            "chat": {"id": 987654321, "type": "private"},
            "date": 1234567890,
            "text": "Hello bot"
        }
    }
    """
    await rate_limiter.check_rate_limit(tenant_id, "telegram")
    await verify_tenant_token(tenant_id, api_key, "telegram")
    
    try:
        canonical_message = await normalizer.normalize_telegram(raw_data, tenant_id)
        
        logger.info(
            f"✅ Telegram message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "telegram_user_id": raw_data["message"]["from"]["id"]
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ Telegram normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Telegram normalization failed: {str(e)}")

@app.post("/normalize/instagram")
async def normalize_instagram(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize Instagram messaging webhook data to CanonicalMessage
    """
    await rate_limiter.check_rate_limit(tenant_id, "instagram")
    await verify_tenant_token(tenant_id, api_key, "instagram")
    
    try:
        canonical_message = await normalizer.normalize_instagram(raw_data, tenant_id)
        
        logger.info(
            f"✅ Instagram message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ Instagram normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Instagram normalization failed: {str(e)}")

@app.post("/normalize/sms")
async def normalize_sms(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    api_key: str = Header(..., alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize SMS (Twilio) webhook data to CanonicalMessage
    
    Expected Twilio SMS format:
    {
        "From": "+1234567890",
        "To": "+0987654321",
        "Body": "Hello via SMS",
        "MessageSid": "SM1234567890abcdef",
        "AccountSid": "AC1234567890abcdef"
    }
    """
    await rate_limiter.check_rate_limit(tenant_id, "sms")
    await verify_tenant_token(tenant_id, api_key, "sms")
    
    try:
        canonical_message = await normalizer.normalize_sms(raw_data, tenant_id)
        
        logger.info(
            f"✅ SMS message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "from_number": raw_data.get("From")
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ SMS normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"SMS normalization failed: {str(e)}")

@app.post("/normalize/console")
async def normalize_console(
    raw_data: Dict[str, Any],
    request: Request,
    tenant_id: Optional[str] = Header(default="test_retailer", alias="x-tenant-id"),
    api_key: Optional[str] = Header(default="test_key", alias="x-api-key")
) -> Dict[str, Any]:
    """
    Normalize console input data to CanonicalMessage (for testing)
    
    Expected console format:
    {
        "user_id": "console_user_001",
        "content": "I want to buy shoes",
        "metadata": {"source": "console"}
    }
    """
    try:
        canonical_message = await normalizer.normalize_console(raw_data, tenant_id)
        
        logger.info(
            f"✅ Console message normalized",
            extra={
                "tenant_id": tenant_id,
                "user_id": canonical_message.user_id,
                "content_preview": canonical_message.content[:50]
            }
        )
        
        return canonical_message.dict()
        
    except Exception as e:
        logger.error(f"❌ Console normalization failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Console normalization failed: {str(e)}")

# Utility Endpoints
@app.post("/validate")
async def validate_canonical_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that a message follows CanonicalMessage format
    """
    try:
        canonical_message = CanonicalMessage(**message_data)
        return {
            "valid": True,
            "message": canonical_message.dict(),
            "validation_timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "validation_timestamp": datetime.now().isoformat()
        }

@app.get("/channels")
async def list_supported_channels():
    """List all supported channels"""
    return {
        "supported_channels": [
            {
                "name": "whatsapp",
                "endpoint": "/normalize/whatsapp",
                "description": "WhatsApp Business API integration"
            },
            {
                "name": "web",
                "endpoint": "/normalize/web", 
                "description": "Web widget integration"
            },
            {
                "name": "facebook",
                "endpoint": "/normalize/facebook",
                "description": "Facebook Messenger integration"
            },
            {
                "name": "telegram",
                "endpoint": "/normalize/telegram",
                "description": "Telegram bot integration"
            },
            {
                "name": "instagram",
                "endpoint": "/normalize/instagram",
                "description": "Instagram messaging integration"
            },
            {
                "name": "sms",
                "endpoint": "/normalize/sms",
                "description": "SMS (Twilio) integration"
            },
            {
                "name": "console",
                "endpoint": "/normalize/console",
                "description": "Console testing interface"
            }
        ]
    }

# Error Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.error(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code
        }
    )
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.now().isoformat()
    }

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__
        }
    )
    return {
        "error": "Internal server error",
        "status_code": 500,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=settings.environment == "development"
    )