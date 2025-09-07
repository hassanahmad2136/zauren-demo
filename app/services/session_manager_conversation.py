"""
Improved conversation management module for WhatsApp bot
- Only tracks user and assistant messages in history
- Summarizes after 30 messages of each type
- Stores summaries in the oldest message of each type
"""

import json
import logging
import datetime
import re
from typing import List, Dict, Any

# Import base module
from .session_manager_base import (
    supabase_client,
    get_active_user_session,
    create_user_session,
    update_session_last_interaction,
    get_user_by_phone,
    create_new_user,
    save_conversation_message,
    get_cart_for_user,
    update_cart
)

# Import LLM summarization
from .LLM import generate_summary

# Configure logging
logger = logging.getLogger(__name__)

def is_session_over_limit(session_id, max_messages=30):
    """
    Check if the session has exceeded the specified message limit for user or assistant
    
    Args:
        session_id (str): Session ID
        max_messages (int): Maximum number of messages per role before summarizing
        
    Returns:
        bool: True if either user or assistant messages exceed the limit
    """
    try:
        # We only need to check user and assistant messages (not system)
        for role in ['user', 'assistant']:
            response = supabase_client.table('conversation_history') \
                .select('id') \
                .eq('session_id', session_id) \
                .eq('role', role) \
                .execute()
            
            if response.data and len(response.data) > max_messages:
                logger.info(f"🔄 Session has exceeded the limit for {role} messages")
                return True
        
        return False
    
    except Exception as e:
        logger.error(f"❌ Error checking session limits: {e}")
        return False  # Default to not over limit in case of error

def get_conversation_history(session_id, summarize=False, max_messages=30):
    """
    Get conversation history with optional summarization.
    Only retrieves user and assistant messages.
    
    Args:
        session_id (str): Session ID
        summarize (bool): Whether to summarize if over limit
        max_messages (int): Maximum number of messages per role before summarizing
        
    Returns:
        list: Conversation history messages
    """
    try:
        logger.info(f"🔍 Retrieving conversation history for session: {session_id}")
        
        # Get all messages for the session without ordering in the query
        # Only select user and assistant messages (no system messages)
        response = supabase_client.table('conversation_history') \
            .select('*') \
            .eq('session_id', session_id) \
            .execute()
        
        if not response.data:
            logger.info(f"ℹ️ No conversation history found for session: {session_id}")
            return []
        
        # Filter to only user and assistant messages and sort by timestamp
        all_messages = [
            msg for msg in response.data 
            if msg.get('role') in ['user', 'assistant']
        ]
        all_messages.sort(key=lambda x: x.get('timestamp', ''))
        
        # If we're not summarizing or don't need to, return the messages as is
        if not summarize:
            conversation_history = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in all_messages
            ]
            logger.info(f"✅ Retrieved {len(conversation_history)} messages from history")
            return conversation_history
        
        # Check if we need to summarize
        messages_by_role = {
            'user': [],
            'assistant': []
        }
        
        # Group messages by role
        for message in all_messages:
            role = message.get('role')
            if role in messages_by_role:
                messages_by_role[role].append(message)
        
        # Check if any role exceeds the limit
        need_summary = False
        for role, messages in messages_by_role.items():
            if len(messages) > max_messages:
                need_summary = True
                break
        
        if not need_summary:
            # If we don't need to summarize, return as is
            conversation_history = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in all_messages
            ]
            logger.info(f"✅ Retrieved {len(conversation_history)} messages without summarization")
            return conversation_history
        
        # We need to summarize - handle each role that needs it
        for role, messages in messages_by_role.items():
            if len(messages) > max_messages:
                # We need to summarize this role's messages
                messages_to_summarize = messages[:-max_messages]  # All except the most recent max_messages
                
                try:
                    # Generate summary for older messages
                    summary = generate_summary(messages_to_summarize, role)
                    
                    # Find the oldest message we're keeping (to put the summary there)
                    oldest_kept_message = messages[-max_messages]
                    
                    # Update the oldest kept message with the summary prepended
                    updated_content = f"{summary}\n\n{oldest_kept_message['content']}"
                    
                    # Update the message in the database
                    supabase_client.table('conversation_history').update({
                        'content': updated_content
                    }).eq('id', oldest_kept_message['id']).execute()
                    
                    logger.info(f"✅ Added summary to oldest kept {role} message")
                    
                    # Also update our local copy for returning
                    oldest_kept_message['content'] = updated_content
                    
                except Exception as e:
                    logger.error(f"❌ Error generating/storing summary for {role} messages: {e}")
                    # Continue without summarization if it fails
        
        # Return the conversation history with summaries included
        # This will be the max_messages most recent messages from each role
        final_history = []
        
        # Interleave messages to maintain conversation flow
        remaining_messages = []
        for role in ['user', 'assistant']:
            if len(messages_by_role[role]) > max_messages:
                # Include only the most recent max_messages (with summary in the first one)
                remaining_messages.extend(messages_by_role[role][-max_messages:])
            else:
                # Include all messages for this role
                remaining_messages.extend(messages_by_role[role])
        
        # Sort remaining messages by timestamp
        remaining_messages.sort(key=lambda x: x.get('timestamp', ''))
        
        # Convert to the expected format
        conversation_history = [
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            for msg in remaining_messages
        ]
        
        logger.info(f"✅ Created summarized conversation history with {len(conversation_history)} messages")
        return conversation_history
        
    except Exception as e:
        logger.error(f"❌ Error retrieving conversation history: {e}")
        return []  # Return empty history if all else fails

def get_user_session(user_phone, user_name=None):
    """
    Get or create a user session based on phone number
    
    Args:
        user_phone (str): User's phone number
        user_name (str, optional): User's name
        
    Returns:
        dict: Session data with user info and conversation history
    """
    try:
        # Look up user by phone number
        user = get_user_by_phone(user_phone)
        
        # Create user if not exists
        if not user:
            user = create_new_user(user_phone, user_name)
        elif user_name and user.get('username') != user_name:
            # Update username if changed
            supabase_client.table('users').update({
                'username': user_name,
                'updated_at': datetime.datetime.now().isoformat()
            }).eq('id', user['id']).execute()
            user['username'] = user_name
        
        user_id = user['id']
        
        # Get active session or create new one
        session = get_active_user_session(user_id)
        if not session:
            session = create_user_session(user_id)
        else:
            # Update last interaction time
            update_session_last_interaction(session['id'])
        
        # Check if conversation history is over the limit
        is_over_limit = is_session_over_limit(session['id'])
        
        # Get conversation history with summarization if needed
        conversation_history = get_conversation_history(
            session['id'],
            summarize=is_over_limit
        )
        
        # Get cart
        cart = get_cart_for_user(user_id)
        
        # Combine all data
        return {
            'user_id': user_id,
            'user_name': user.get('username'),
            'phone_number': user.get('phone_number'),
            'session_id': session['id'],
            'conversation_history': conversation_history,
            'cart': cart
        }
    
    except Exception as e:
        logger.error(f"❌ Error retrieving user session: {e}")
        raise

def end_session(session_id):
    """
    End a session by marking it as inactive
    
    Args:
        session_id (str): Session ID
        
    Returns:
        bool: Success status
    """
    try:
        logger.info(f"🔄 Ending session: {session_id}")
        
        supabase_client.table('sessions').update({
            'is_active': False,
            'session_end': datetime.datetime.now().isoformat()
        }).eq('id', session_id).execute()
        
        logger.info(f"✅ Session ended successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error ending session: {e}")
        return False

def update_user_session(user_id, update_data):
    """
    Update user session data
    
    Args:
        user_id (str): User ID
        update_data (dict): Data to update
        
    Returns:
        bool: Success status
    """
    try:
        logger.info(f"🔄 Updating session data for user: {user_id}")
        
        # Update cart if included
        if 'cart' in update_data:
            update_cart(user_id, update_data['cart'])
        
        # Update user record if needed
        update_fields = {}
        if 'user_name' in update_data:
            update_fields['username'] = update_data['user_name']
            update_fields['updated_at'] = datetime.datetime.now().isoformat()
            
        if update_fields:
            supabase_client.table('users').update(update_fields).eq('id', user_id).execute()
        
        # Get the active session and update last interaction
        session = get_active_user_session(user_id)
        if session:
            update_session_last_interaction(session['id'])
        
        logger.info(f"✅ User session updated successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error updating user session: {e}")
        return False
    
