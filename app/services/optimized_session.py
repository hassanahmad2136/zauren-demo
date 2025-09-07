"""
Optimized session management for database operations
Provides caching and background updates for better performance
"""

import os
import time
import json
import threading
from typing import Dict, Any, Optional
from supabase import create_client, Client

class OptimizedSessionManager:
    """Optimized session manager with caching and background operations"""
    
    def __init__(self):
        self.supabase = create_client(
            os.getenv("INVENTORY_SUPABASE_URL"),
            os.getenv("INVENTORY_SUPABASE_KEY")
        )
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
        
    def get_user_session_fast(self, user_id: str, user_name: str) -> Dict[str, Any]:
        """Get user session with caching"""
        cache_key = f"session_{user_id}"
        current_time = time.time()
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            if current_time - cache_time < self.cache_timeout:
                # Update cache in background if it's getting old
                if current_time - cache_time > 240:  # 4 minutes
                    threading.Thread(
                        target=self._refresh_session_cache,
                        args=(user_id, user_name, cache_key),
                        daemon=True
                    ).start()
                return cached_data
        
        # Fetch from database
        session_data = self._fetch_session_from_db(user_id, user_name)
        self.cache[cache_key] = (session_data, current_time)
        return session_data
    
    def _refresh_session_cache(self, user_id: str, user_name: str, cache_key: str):
        """Refresh session cache in background"""
        try:
            session_data = self._fetch_session_from_db(user_id, user_name)
            self.cache[cache_key] = (session_data, time.time())
        except Exception as e:
            print(f"Error refreshing session cache: {e}")
    
    def _fetch_session_from_db(self, user_id: str, user_name: str) -> Dict[str, Any]:
        """Fetch session from database"""
        try:
            # Your existing session fetch logic here
            response = self.supabase.table('user_sessions').select('*').eq('user_id', user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                # Create new session
                new_session = {
                    'user_id': user_id,
                    'session_id': f"session_{user_id}_{int(time.time())}",
                    'user_name': user_name,
                    'cart': {'items': [], 'total': 0},
                    'conversation_history': []
                }
                
                self.supabase.table('user_sessions').insert(new_session).execute()
                return new_session
                
        except Exception as e:
            print(f"Error fetching session: {e}")
            # Return default session
            return {
                'user_id': user_id,
                'session_id': f"session_{user_id}_{int(time.time())}",
                'user_name': user_name,
                'cart': {'items': [], 'total': 0},
                'conversation_history': []
            }
    
    def save_message_async(self, session_id: str, user_id: str, content: str, role: str):
        """Save message in background thread"""
        def _save():
            try:
                self.supabase.table('conversation_history').insert({
                    'session_id': session_id,
                    'user_id': user_id,
                    'content': content,
                    'role': role,
                    'timestamp': time.time()
                }).execute()
            except Exception as e:
                print(f"Error saving message: {e}")
        
        threading.Thread(target=_save, daemon=True).start()

# Global instance
optimized_session = OptimizedSessionManager()
