# apps/orchestrator/context_manager.py
"""
Context Manager for User State and Conversation History
Manages all context data in Redis with intelligent caching
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from core.database.redis_client import RedisClient
from core.models.message import UserContext
import logging

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Manages all types of user context and conversation state
    Provides fast access to user data for the orchestrator
    """
    
    def __init__(self):
        self.redis_client = RedisClient()
        self.context_cache = {}  # In-memory cache for frequently accessed contexts
        
        # Context expiry times (in seconds)
        self.expiry_times = {
            "conversation_context": 1800,  # 30 minutes
            "session_context": 14400,      # 4 hours
            "recent_messages": 3600,       # 1 hour
            "current_cart": 604800,        # 7 days
            "user_preferences": 86400,     # 24 hours (cached from DB)
        }
    
    async def initialize(self):
        """Initialize context manager"""
        await self.redis_client.connect()
        logger.info("✅ Context Manager initialized")
    
    async def close(self):
        """Close connections"""
        await self.redis_client.disconnect()
    
    async def get_user_context(self, user_id: str, tenant_id: str) -> UserContext:
        """
        Get complete user context for conversation processing
        Combines all context types into a single object
        """
        context_key = f"{user_id}:{tenant_id}"
        
        # Check in-memory cache first (5-minute TTL)
        if context_key in self.context_cache:
            cached_context = self.context_cache[context_key]
            if datetime.now() - cached_context["cached_at"] < timedelta(minutes=5):
                return UserContext(**cached_context["data"])
        
        # Load from Redis
        conversation_context = await self._get_conversation_context(user_id, tenant_id)
        session_context = await self._get_session_context(user_id, tenant_id)
        recent_messages = await self._get_recent_messages(user_id, tenant_id)
        current_cart = await self._get_current_cart(user_id, tenant_id)
        preferences = await self._get_user_preferences(user_id, tenant_id)
        search_entity = await self.get_search_entity(user_id, tenant_id)
        
        # Create UserContext object
        user_context = UserContext(
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_context.get("session_id", str(uuid.uuid4())),
            conversation_context=conversation_context,
            session_data=session_context,
            recent_messages=recent_messages,
            search_entity=search_entity,
            current_cart=current_cart,
            preferences=preferences,
            last_updated=datetime.now()
        )
        
        # Cache in memory
        self.context_cache[context_key] = {
            "data": user_context.dict(),
            "cached_at": datetime.now()
        }
        
        # Limit cache size (keep last 100 users)
        if len(self.context_cache) > 100:
            oldest_key = min(self.context_cache.keys(), 
                           key=lambda k: self.context_cache[k]["cached_at"])
            del self.context_cache[oldest_key]
        
        return user_context
    
    async def _get_conversation_context(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get current conversation context"""
        key = f"conversation_context:{user_id}:{tenant_id}"
        context = await self.redis_client.get(key)
        
        if context:
            return context
        
        # Initialize new conversation context
        default_context = {
            "current_topic": None,
            "last_intent": None,
            "conversation_stage": "greeting",
            "mentioned_products": [],
            "asked_questions": [],
            "conversation_start": datetime.now().isoformat()
        }
        
        await self.redis_client.set(key, default_context, ttl=self.expiry_times["conversation_context"])
        return default_context
    
    async def _get_session_context(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get session context"""
        key = f"session_context:{user_id}:{tenant_id}"
        context = await self.redis_client.get(key)
        
        if context:
            return context
        
        # Initialize new session
        default_session = {
            "session_id": str(uuid.uuid4()),
            "session_start": datetime.now().isoformat(),
            "channel": None,
            "device_info": {},
            "location": None,
            "referrer": None
        }
        
        await self.redis_client.set(key, default_session, ttl=self.expiry_times["session_context"])
        return default_session
    
    async def _get_recent_messages(self, user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
        """Get recent message history"""
        key = f"recent_messages:{user_id}:{tenant_id}"
        messages = await self.redis_client.get(key)
        return messages if messages else []
    
    async def _get_current_cart(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get current cart contents"""
        key = f"current_cart:{user_id}:{tenant_id}"
        cart = await self.redis_client.get(key)
        
        if cart:
            return cart
        
        # Initialize empty cart
        default_cart = {
            "items": [],
            "total": 0.0,
            "currency": "USD",
            "last_updated": datetime.now().isoformat()
        }
        
        await self.redis_client.set(key, default_cart, ttl=self.expiry_times["current_cart"])
        return default_cart
    
    async def _get_user_preferences(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get user preferences (cached from long-term storage)"""
        key = f"user_preferences:{user_id}:{tenant_id}"
        prefs = await self.redis_client.get(key)
        
        if prefs:
            return prefs
        
        # TODO: Load from PostgreSQL and cache in Redis
        # For now, return default preferences
        default_prefs = {
            "communication_style": "friendly",
            "preferred_categories": [],
            "price_range": {"min": 0, "max": 1000},
            "size_preferences": {},
            "brand_preferences": [],
            "color_preferences": [],
            "language": "en"
        }
        
        await self.redis_client.set(key, default_prefs, ttl=self.expiry_times["user_preferences"])
        return default_prefs
    
    async def get_search_entity(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Get the accumulated search entity for the user
        This maintains context across multiple messages
        """
        key = f"search_entity:{user_id}:{tenant_id}"
        entity = await self.redis_client.get(key)
        
        if entity:
            return entity
        
        # Initialize default search entity
        default_entity = {
            "query": "",
            "category": None,
            "brand": None,
            "color": None,
            "size": None,
            "style": None,
            "material": None,
            "min_price": None,
            "max_price": None,
            "referenced_item_id": None,
            "custom_attributes": {}
        }
        
        await self.redis_client.set(key, default_entity, ttl=self.expiry_times["conversation_context"])
        return default_entity
    
    async def update_search_entity(self, user_id: str, tenant_id: str, updates: Dict[str, Any]):
        """
        Update the search entity with new information
        Merges new data with existing entity
        """
        key = f"search_entity:{user_id}:{tenant_id}"
        current_entity = await self.get_search_entity(user_id, tenant_id)
        
        # Merge updates with current entity
        for field, value in updates.items():
            if value is not None:  # Only update non-null values
                if field == "query":
                    # Append/refine query instead of replacing
                    if current_entity["query"]:
                        current_entity["query"] = f"{current_entity['query']} {value}"
                    else:
                        current_entity["query"] = value
                elif field == "custom_attributes":
                    # Merge custom attributes
                    current_entity["custom_attributes"].update(value)
                else:
                    current_entity[field] = value
        
        # Save updated entity
        await self.redis_client.set(key, current_entity, ttl=self.expiry_times["conversation_context"])
        return current_entity
    
    async def get_intent_history(self, user_id: str, tenant_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent intent classifications for few-shot learning
        Returns list of (message, intent_json) pairs
        """
        key = f"intent_history:{user_id}:{tenant_id}"
        history = await self.redis_client.get(key)
        
        if history:
            return history[-limit:]  # Return last N intents
        
        return []
    
    async def add_intent_to_history(self, user_id: str, tenant_id: str, 
                                   message: str, intent_json: Dict[str, Any]):
        """Add a new intent classification to history for future few-shot learning"""
        key = f"intent_history:{user_id}:{tenant_id}"
        history = await self.redis_client.get(key) or []
        
        history.append({
            "message": message,
            "intent_json": intent_json,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 20 intents
        if len(history) > 20:
            history = history[-20:]
        
        await self.redis_client.set(key, history, ttl=self.expiry_times["recent_messages"])
    
    async def update_conversation_context(self, user_id: str, tenant_id: str, context: Dict[str, Any]):
        """Update conversation context"""
        key = f"conversation_context:{user_id}:{tenant_id}"
        await self.redis_client.set(key, context, ttl=self.expiry_times["conversation_context"])
        
        # Invalidate memory cache
        context_key = f"{user_id}:{tenant_id}"
        if context_key in self.context_cache:
            del self.context_cache[context_key]
    
    async def add_message_to_history(self, user_id: str, tenant_id: str, message: Dict[str, Any]):
        """Add message to recent history"""
        key = f"recent_messages:{user_id}:{tenant_id}"
        
        # Get existing messages
        messages = await self.redis_client.get(key) or []
        
        # Add new message
        messages.append({
            **message,
            "timestamp": message.get("timestamp", datetime.now().isoformat())
        })
        
        # Keep only last 50 messages
        if len(messages) > 50:
            messages = messages[-50:]
        
        # Save back to Redis
        await self.redis_client.set(key, messages, ttl=self.expiry_times["recent_messages"])
    
    async def update_cart(self, user_id: str, tenant_id: str, cart: Dict[str, Any]):
        """Update cart contents"""
        key = f"current_cart:{user_id}:{tenant_id}"
        cart["last_updated"] = datetime.now().isoformat()
        await self.redis_client.set(key, cart, ttl=self.expiry_times["current_cart"])
    
    async def clear_session(self, user_id: str, tenant_id: str):
        """Clear all session data for a user"""
        keys_to_delete = [
            f"conversation_context:{user_id}:{tenant_id}",
            f"session_context:{user_id}:{tenant_id}",
            f"recent_messages:{user_id}:{tenant_id}",
            f"search_entity:{user_id}:{tenant_id}",
            f"intent_history:{user_id}:{tenant_id}"
        ]
        
        for key in keys_to_delete:
            await self.redis_client.delete(key)
        
        # Clear memory cache
        context_key = f"{user_id}:{tenant_id}"
        if context_key in self.context_cache:
            del self.context_cache[context_key]
        
        logger.info(f"Cleared session for user {user_id} in tenant {tenant_id}")