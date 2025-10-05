# apps/orchestrator/main.py
"""
Orchestrator Service with LangGraph
Manages conversation workflows and coordinates agent interactions
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.models.message import CanonicalMessage, AgentResponse
from core.database.redis_client import RedisClient
from core.llm.groq_client import groq_client
from apps.orchestrator.context_manager import ContextManager
from apps.orchestrator.workflow_engine import RetailWorkflow
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Initialize services
redis_client = RedisClient()
context_manager = ContextManager()
workflow_engine = RetailWorkflow()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("🚀 Orchestrator starting up...")
    
    # Initialize connections
    await redis_client.connect()
    await groq_client.initialize()
    await context_manager.initialize()
    await workflow_engine.initialize()
    
    logger.info("✅ Orchestrator ready")
    yield
    
    # Cleanup
    logger.info("📴 Orchestrator shutting down...")
    await context_manager.close()
    await redis_client.disconnect()

app = FastAPI(
    title="Retail AI - Orchestrator",
    description="LangGraph workflow orchestrator for retail AI agents",
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "timestamp": datetime.now().isoformat(),
        "connections": {
            "redis": redis_client.redis is not None,
            "groq": groq_client.client is not None
        }
    }

@app.post("/process")
async def process_message(canonical_message: CanonicalMessage) -> Dict[str, Any]:
    """
    Main endpoint to process messages through the workflow
    
    Args:
        canonical_message: Normalized message from message bus
        
    Returns:
        Response with reply and metadata
    """
    try:
        logger.info(f"Processing message from {canonical_message.user_id} on {canonical_message.channel}")
        
        # Get user context
        user_context = await context_manager.get_user_context(
            canonical_message.user_id,
            canonical_message.tenant_id
        )
        
        # Detect language from the message
        language_code = None
        if canonical_message.content:
            language_code, language_name = await groq_client.detect_language(
                canonical_message.content
            )
            logger.info(f"Detected language: {language_name} ({language_code})")
        
        # Execute workflow
        result = await workflow_engine.execute(
            message=canonical_message,
            context=user_context,
            language=language_code
        )
        
        # Update context with conversation
        await context_manager.add_message_to_history(
            canonical_message.user_id,
            canonical_message.tenant_id,
            {
                "role": "user",
                "content": canonical_message.content,
                "timestamp": canonical_message.timestamp.isoformat()
            }
        )
        
        await context_manager.add_message_to_history(
            canonical_message.user_id,
            canonical_message.tenant_id,
            {
                "role": "assistant",
                "content": result["response"],
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "response": result["response"],
            "metadata": {
                "language": language_code,
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "agents_used": result.get("agents_used", []),
                "execution_time_ms": result.get("execution_time_ms"),
                "session_id": user_context.session_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process/batch")
async def process_batch(messages: List[CanonicalMessage]) -> List[Dict[str, Any]]:
    """Process multiple messages in parallel"""
    tasks = [process_message(msg) for msg in messages]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error responses
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "success": False,
                "error": str(result),
                "message_index": i
            })
        else:
            processed_results.append(result)
    
    return processed_results

@app.get("/session/{user_id}/{tenant_id}")
async def get_session(user_id: str, tenant_id: str) -> Dict[str, Any]:
    """Get current session information for a user"""
    try:
        context = await context_manager.get_user_context(user_id, tenant_id)
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "session_id": context.session_id,
            "conversation_context": context.conversation_context,
            "cart_items": context.current_cart,
            "preferences": context.preferences,
            "message_count": len(context.recent_messages)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")

@app.delete("/session/{user_id}/{tenant_id}")
async def clear_session(user_id: str, tenant_id: str) -> Dict[str, Any]:
    """Clear session data for a user"""
    try:
        await context_manager.clear_session(user_id, tenant_id)
        return {"success": True, "message": "Session cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get orchestrator statistics"""
    stats = await workflow_engine.get_stats()
    return {
        "service": "orchestrator",
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "apps.orchestrator.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )