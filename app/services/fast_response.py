"""
Fast response optimization for WhatsApp bot
Implements immediate acknowledgment and background processing
"""

import threading
import time
import json
import logging
from functools import lru_cache
from typing import Dict, Any, Optional
import requests
import os

logger = logging.getLogger(__name__)

class FastResponseManager:
    """Manages fast response patterns for WhatsApp bot"""
    
    def __init__(self):
        self.session = requests.Session()  # Reuse HTTP connections
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
        
    @lru_cache(maxsize=100)
    def get_quick_intent(self, message_lower: str) -> Optional[str]:
        """Quick pattern matching for common intents"""
        quick_patterns = {
            'view_inventory': ['show', 'see', 'view', 'products', 'items', 'catalog', 'stock', 'browse'],
            'smalltalk': ['hi', 'hello', 'hey', 'good', 'thanks', 'bye', 'thank you'],
            'add_to_cart': ['buy', 'order', 'purchase', 'want', 'need', 'add'],
            'view_cart': ['cart', 'basket', 'my order'],
            'price_inquiry': ['price', 'cost', 'how much', 'rate', 'expensive', 'cheap']
        }
        
        for intent, keywords in quick_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return intent
        return None
    
    def get_quick_response(self, intent: str, sender_name: str) -> str:
        """Get immediate response templates"""
        quick_responses = {
            'smalltalk': f"Hello {sender_name}! 👋 How can I help you today?",
            'view_inventory': "Let me show you our products! 📱 Loading...",
            'add_to_cart': "Great choice! 🛒 Let me add that to your cart...",
            'view_cart': "Let me check your cart! 🛍️",
            'price_inquiry': "I'll check the pricing for you! 💰",
            'default': f"Got your message, {sender_name}! 📨 Let me help you with that..."
        }
        return quick_responses.get(intent, quick_responses['default'])
    
    def send_immediate_ack(self, phone_number_id: str, recipient_phone: str, message: str, message_id: str):
        """Send immediate acknowledgment without blocking"""
        def _send():
            try:
                access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
                url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                
                payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient_phone,
                    "text": {"body": message}
                }
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                self.session.post(url, json=payload, headers=headers, timeout=5)
            except Exception as e:
                logger.error(f"❌ Error sending immediate ack: {e}")
        
        threading.Thread(target=_send, daemon=True).start()

    def process_in_background(self, func, *args, **kwargs):
        """Execute function in background thread"""
        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

# Global instance
fast_response = FastResponseManager()
