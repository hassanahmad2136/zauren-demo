"""
Base session management module for WhatsApp bot
Handles core user, session, and database operations
"""

import json
import logging
import datetime
import os
from dotenv import load_dotenv
from supabase import create_client
from uuid import UUID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("INVENTORY_SUPABASE_URL")
SUPABASE_KEY = os.getenv("INVENTORY_SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Missing Supabase credentials in environment variables")
    raise ValueError("Missing Supabase credentials (INVENTORY_SUPABASE_URL and INVENTORY_SUPABASE_KEY)")

try:
    # Create Supabase client
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase client initialized")
except Exception as e:
    logger.error(f"❌ Error initializing Supabase client: {e}")
    raise

def is_valid_uuid(uuid_string):
    """Check if a string is a valid UUID"""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False

def create_new_user(phone_number, username=None):
    """
    Create a new user in the database
    
    Args:
        phone_number (str): User's phone number
        username (str, optional): User's name
        
    Returns:
        dict: User data including ID
    """
    try:
        logger.info(f"🔄 Creating new user with phone number: {phone_number}")
        
        # Insert new user
        response = supabase_client.table('users').insert({
            'phone_number': phone_number,
            'username': username
        }).execute()
        
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            logger.info(f"✅ User created with ID: {user_data['id']}")
            return user_data
        else:
            logger.error(f"❌ Failed to create user: {response}")
            raise Exception("Failed to create user")
    
    except Exception as e:
        logger.error(f"❌ Error creating user: {e}")
        raise

def get_user_by_phone(phone_number):
    """
    Retrieve a user by phone number
    
    Args:
        phone_number (str): User's phone number
        
    Returns:
        dict or None: User data if found, None otherwise
    """
    try:
        logger.info(f"🔍 Looking up user with phone number: {phone_number}")
        
        response = supabase_client.table('users').select('*').eq('phone_number', phone_number).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Found user with ID: {response.data[0]['id']}")
            return response.data[0]
        else:
            logger.info(f"ℹ️ No user found with phone number: {phone_number}")
            return None
    
    except Exception as e:
        logger.error(f"❌ Error retrieving user: {e}")
        return None

def create_user_session(user_id):
    """
    Create a new session for a user
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict: Session data
    """
    try:
        logger.info(f"🔄 Creating new session for user: {user_id}")
        
        # Insert new session
        response = supabase_client.table('sessions').insert({
            'user_id': user_id,
            'is_active': True,
            'session_start': datetime.datetime.now().isoformat(),
            'last_interaction': datetime.datetime.now().isoformat()
        }).execute()
        
        if response.data and len(response.data) > 0:
            session_data = response.data[0]
            logger.info(f"✅ Session created with ID: {session_data['id']}")
            return session_data
        else:
            logger.error(f"❌ Failed to create session: {response}")
            raise Exception("Failed to create session")
    
    except Exception as e:
        logger.error(f"❌ Error creating session: {e}")
        raise

def get_active_user_session(user_id):
    """
    Get the active session for a user
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict or None: Session data if found, None otherwise
    """
    try:
        logger.info(f"🔍 Looking up active session for user: {user_id}")
        
        # Get all active sessions for user
        response = supabase_client.table('sessions') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('is_active', True) \
            .execute()
        
        if response.data and len(response.data) > 0:
            # Sort manually by last_interaction in descending order and take the first one
            sorted_sessions = sorted(
                response.data, 
                key=lambda x: x.get('last_interaction', ''),
                reverse=True
            )
            session = sorted_sessions[0]
            logger.info(f"✅ Found active session with ID: {session['id']}")
            return session
        else:
            logger.info(f"ℹ️ No active session found for user: {user_id}")
            return None
    
    except Exception as e:
        logger.error(f"❌ Error retrieving active session: {e}")
        return None

def update_session_last_interaction(session_id):
    """
    Update the last interaction timestamp for a session
    
    Args:
        session_id (str): Session ID
    """
    try:
        supabase_client.table('sessions').update({
            'last_interaction': datetime.datetime.now().isoformat()
        }).eq('id', session_id).execute()
        
        logger.info(f"✅ Updated last interaction for session: {session_id}")
    
    except Exception as e:
        logger.error(f"❌ Error updating session last interaction: {e}")

def save_conversation_message(session_id, user_id, content, role="user"):
    """
    Save a message to the conversation history
    
    Args:
        session_id (str): Session ID
        user_id (str): User ID
        content (str): Message content
        role (str): Message role (user, assistant, or system)
    """
    try:
        # Validate role
        if role not in ['user', 'assistant', 'system']:
            role = 'user'  # Default to user if invalid role
            
        logger.info(f"💾 Saving {role} message to conversation history")
        
        # Insert conversation message
        response = supabase_client.table('conversation_history').insert({
            'session_id': session_id,
            'user_id': user_id,
            'content': content,
            'role': role,
            'timestamp': datetime.datetime.now().isoformat()
        }).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Message saved to conversation history")
        else:
            logger.error(f"❌ Failed to save message: {response}")
    
    except Exception as e:
        logger.error(f"❌ Error saving conversation message: {e}")

def get_regular_conversation_history(session_id):
    """
    Get conversation history without summarization
    
    Args:
        session_id (str): Session ID
        
    Returns:
        list: Conversation history messages
    """
    try:
        logger.info(f"🔍 Retrieving conversation history for session: {session_id}")
        
        # Get all messages for the session without ordering in the query
        response = supabase_client.table('conversation_history') \
            .select('*') \
            .eq('session_id', session_id) \
            .execute()
        
        if response.data:
            # Sort manually by timestamp
            sorted_messages = sorted(response.data, key=lambda x: x.get('timestamp', ''))
            
            # Convert to expected format
            conversation_history = []
            for message in sorted_messages:
                conversation_history.append({
                    "role": message.get("role", "user"),
                    "content": message.get("content", "")
                })
            
            logger.info(f"✅ Retrieved {len(conversation_history)} messages from history")
            return conversation_history
        else:
            logger.info(f"ℹ️ No conversation history found for session: {session_id}")
            return []
    
    except Exception as e:
        logger.error(f"❌ Error retrieving conversation history: {e}")
        return []

def get_cart_for_user(user_id):
    """
    Get the active cart for a user
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict: Cart data with items
    """
    try:
        logger.info(f"🔍 Looking up active cart for user: {user_id}")
        
        # Get the active cart
        cart_response = supabase_client.table('carts') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('is_active', True) \
            .execute()
        
        if not cart_response.data or len(cart_response.data) == 0:
            # Create a new cart if none exists
            cart_data = create_new_cart(user_id)
            return {'items': [], 'total': 0, 'id': cart_data['id']}
        
        # Get the most recently updated cart (sort manually)
        sorted_carts = sorted(
            cart_response.data,
            key=lambda x: x.get('updated_at', ''),
            reverse=True
        )
        cart_data = sorted_carts[0]
        cart_id = cart_data['id']
        
        # Get the cart items
        items_response = supabase_client.table('cart_items') \
            .select('*') \
            .eq('cart_id', cart_id) \
            .execute()
        
        # Format cart with items
        cart = {
            'id': cart_id,
            'items': [],
            'total': 0
        }
        
        if items_response.data:
            for item in items_response.data:
                cart['items'].append({
                    'id': item['product_id'],
                    'name': item['product_name'],
                    'price': float(item['product_price']),
                    'quantity': item['quantity']
                })
            
            # Calculate total
            cart['total'] = sum(item['price'] * item['quantity'] for item in cart['items'])
        
        logger.info(f"✅ Retrieved cart with {len(cart['items'])} items")
        return cart
    
    except Exception as e:
        logger.error(f"❌ Error retrieving cart: {e}")
        return {'items': [], 'total': 0}

def create_new_cart(user_id):
    """
    Create a new cart for a user
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict: Cart data
    """
    try:
        logger.info(f"🔄 Creating new cart for user: {user_id}")
        
        # Insert new cart
        response = supabase_client.table('carts').insert({
            'user_id': user_id,
            'is_active': True
        }).execute()
        
        if response.data and len(response.data) > 0:
            cart_data = response.data[0]
            logger.info(f"✅ Cart created with ID: {cart_data['id']}")
            return cart_data
        else:
            logger.error(f"❌ Failed to create cart: {response}")
            raise Exception("Failed to create cart")
    
    except Exception as e:
        logger.error(f"❌ Error creating cart: {e}")
        raise

def update_cart(user_id, cart_data):
    """
    Update a user's cart with new data
    
    Args:
        user_id (str): User ID
        cart_data (dict): Cart data with items and total
    """
    try:
        logger.info(f"🔄 Updating cart for user: {user_id}")
        
        # Validate cart_data structure
        if not isinstance(cart_data, dict):
            logger.error(f"❌ Invalid cart_data type: {type(cart_data)}")
            return
            
        # Get the active cart
        cart_response = supabase_client.table('carts') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('is_active', True) \
            .execute()
        
        if not cart_response.data or len(cart_response.data) == 0:
            # Create a new cart if none exists
            cart = create_new_cart(user_id)
            cart_id = cart['id']
        else:
            # Get the most recent cart
            sorted_carts = sorted(
                cart_response.data,
                key=lambda x: x.get('updated_at', ''),
                reverse=True
            )
            cart_id = sorted_carts[0]['id']
        
        # Clear existing cart items
        supabase_client.table('cart_items') \
            .delete() \
            .eq('cart_id', cart_id) \
            .execute()
        
        # Insert new cart items
        items = cart_data.get('items', [])
        if not isinstance(items, list):
            logger.warning(f"❌ Cart items is not a list: {type(items)}")
            items = []
            
        for item in items:
            if not isinstance(item, dict):
                logger.warning(f"❌ Skipping non-dict cart item: {type(item)}")
                continue
                
            # Ensure all required fields exist with proper types
            cart_item = {
                'cart_id': cart_id,
                'product_id': str(item.get('id', '')),
                'product_name': str(item.get('name', 'Unknown Product')),
                'product_price': float(item.get('price', 0)),
                'quantity': int(item.get('quantity', 1))
            }
            
            try:
                supabase_client.table('cart_items').insert(cart_item).execute()
            except Exception as item_error:
                logger.error(f"❌ Error inserting cart item: {item_error}")
        
        # Calculate total
        total = 0
        for item in items:
            if isinstance(item, dict):
                price = float(item.get('price', 0))
                quantity = int(item.get('quantity', 0))
                total += price * quantity
        
        # Update cart record with timestamp only (don't try to update total_amount column)
        supabase_client.table('carts').update({
            'updated_at': datetime.datetime.now().isoformat()
        }).eq('id', cart_id).execute()
        
        logger.info(f"✅ Updated cart with {len(items)} items")
    
    except Exception as e:
        logger.error(f"❌ Error updating cart: {e}")