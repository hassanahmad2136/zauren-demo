"""
Webhook service module for WhatsApp bot
Handles incoming webhook events and message processing
"""

import json
import logging
import datetime
import time
import hashlib
import requests
import tempfile
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid

from .LLM import (
    classify_intent,
    handle_smalltalk,
    handle_view_cart,
    handle_confirm_action,
    handle_confirm_order,
    handle_add_to_cart,
    handle_remove_from_cart,
    handle_NOT_SURE,
    handle_product_info,
    handle_view_inventory,
    handle_track_order
)
from .messaging_service import (
    mark_message_as_read,
    send_whatsapp_message,
    send_interactive_message,
    send_typing_indicator
)
from .db_inventory import (
    get_all_categories,
    get_all_products,
    create_nested_inventory_json,
    get_product_details,
    reserve_stock,
    release_reserved_stock,
    get_available_stock,
    cleanup_expired_reservations,
    finalize_purchase
)
from .session_manager_conversation import (
    get_user_session,
    update_user_session,
    save_conversation_message
)
from .audio import transcribe_audio  # Import the transcription function

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global inventory - will be initialized during startup
global_inventory = None

def initialize_global_inventory():
    """Initialize the global inventory from database"""
    global global_inventory
    try:
        categories_result = get_all_categories()
        products_result = get_all_products()
        
        if categories_result['status'] == 'success' and products_result['status'] == 'success':
            categories = categories_result['data']
            products = products_result['data']
            global_inventory = create_nested_inventory_json(categories, products)
            logger.info("✅ Global inventory initialized successfully")
        else:
            logger.error("❌ Failed to fetch inventory data from database")
            global_inventory = '{"categories": []}'
    except Exception as e:
        logger.error(f"❌ Error initializing global inventory: {e}")
        global_inventory = '{"categories": []}'

def refresh_global_inventory():
    """Refresh the global inventory (call this when inventory changes)"""
    initialize_global_inventory()

# Initialize inventory on module load
initialize_global_inventory()

# Message deduplication cache
processed_messages = {}
DUPLICATE_MESSAGE_TIMEOUT = 60  # seconds

def download_media_file(media_id, media_type="audio"):
    """
    Download media file from WhatsApp Cloud API
    
    Args:
        media_id (str): The media ID from WhatsApp
        media_type (str): Type of media (audio, image, video, etc.)
        
    Returns:
        str: Path to the downloaded file, or None if failed
    """
    try:
        # Get WhatsApp access token from environment
        access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        if not access_token:
            logger.error("❌ WhatsApp access token not found in environment variables")
            return None
        
        # Step 1: Get media URL
        media_url_endpoint = f"https://graph.facebook.com/v17.0/{media_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        logger.info(f"🔄 Getting media URL for ID: {media_id}")
        url_response = requests.get(media_url_endpoint, headers=headers)
        
        if url_response.status_code != 200:
            logger.error(f"❌ Failed to get media URL: {url_response.status_code} - {url_response.text}")
            return None
        
        media_data = url_response.json()
        media_url = media_data.get("url")
        mime_type = media_data.get("mime_type", "")
        
        if not media_url:
            logger.error("❌ No media URL found in response")
            return None
        
        # Step 2: Download the actual media file
        logger.info(f"🔄 Downloading media from URL: {media_url}")
        download_response = requests.get(media_url, headers=headers)
        
        if download_response.status_code != 200:
            logger.error(f"❌ Failed to download media: {download_response.status_code}")
            return None
        
        # Step 3: Save to temporary file
        # Determine file extension based on mime type
        file_extension = ".ogg"  # Default for WhatsApp audio
        if "audio" in mime_type:
            if "ogg" in mime_type:
                file_extension = ".ogg"
            elif "mp4" in mime_type or "m4a" in mime_type:
                file_extension = ".m4a"
            elif "mp3" in mime_type:
                file_extension = ".mp3"
            elif "wav" in mime_type:
                file_extension = ".wav"
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        temp_filename = f"whatsapp_{media_type}_{media_id}_{int(time.time())}{file_extension}"
        temp_filepath = os.path.join(temp_dir, temp_filename)
        
        # Write the media content to file
        with open(temp_filepath, 'wb') as f:
            f.write(download_response.content)
        
        logger.info(f"✅ Media downloaded successfully: {temp_filepath}")
        return temp_filepath
        
    except Exception as e:
        logger.error(f"❌ Error downloading media file: {e}")
        return None

def cleanup_temp_file(file_path):
    """
    Clean up temporary downloaded file
    
    Args:
        file_path (str): Path to the temporary file
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🧹 Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup temporary file {file_path}: {e}")

# Function to extract message content based on the message type
def extract_message_content(message):
    msg_type = message.get("type", "unknown")
    text = None
    
    if msg_type == "text":
        text = message.get("text", {}).get("body")
    elif msg_type == "image" and "caption" in message.get("image", {}):
        text = message.get("image", {}).get("caption")
    elif msg_type == "interactive":
        interactive = message.get("interactive", {})
        if "button_reply" in interactive:
            text = interactive["button_reply"].get("title", "")
        elif "list_reply" in interactive:
            text = interactive["list_reply"].get("title", "")
    elif msg_type == "audio":
        # Handle audio messages
        audio_data = message.get("audio", {})
        media_id = audio_data.get("id")
        
        if not media_id:
            logger.error("❌ No media ID found in audio message")
            return "I received an audio message but couldn't process it."
        
        logger.info(f"🎵 Processing audio message with ID: {media_id}")
        
        # Download the audio file
        audio_file_path = download_media_file(media_id, "audio")
        
        if not audio_file_path:
            logger.error("❌ Failed to download audio file")
            return "I received an audio message but couldn't download it."
        
        try:
            # Transcribe the audio
            model_name = "whisper-large-v3-turbo"  # or whatever model you're using
            transcription_result = transcribe_audio(model_name, audio_file_path)
            
            # Handle different possible return types from transcribe_audio
            if transcription_result:
                # Check if it's a Transcription object with a 'text' attribute
                if hasattr(transcription_result, 'text'):
                    transcription_text = transcription_result.text
                    logger.info(f"✅ Audio transcribed: {transcription_text[:100]}...")
                    text = transcription_text.strip()
                # Check if it's already a string
                elif isinstance(transcription_result, str):
                    logger.info(f"✅ Audio transcribed: {transcription_result[:100]}...")
                    text = transcription_result.strip()
                # Check if it's a dictionary with 'text' key
                elif isinstance(transcription_result, dict) and 'text' in transcription_result:
                    transcription_text = transcription_result['text']
                    logger.info(f"✅ Audio transcribed: {transcription_text[:100]}...")
                    text = transcription_text.strip()
                else:
                    logger.error(f"❌ Unexpected transcription result type: {type(transcription_result)}")
                    text = "I received an audio message but couldn't understand the format."
            else:
                logger.error("❌ Audio transcription failed or returned empty")
                text = "I received an audio message but couldn't understand what was said."
                
        except Exception as e:
            logger.error(f"❌ Error transcribing audio: {e}")
            # Log the full exception for debugging
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            text = "I received an audio message but had trouble processing it."
        
        finally:
            # Clean up the temporary file
            cleanup_temp_file(audio_file_path)
    else:
        text = f"Received a {msg_type} message"
    
    return text
# Function to mark the message as read
def mark_message_read(data, message):
    try:
        mark_message_as_read(
            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
            message_id=message.get("id")
        )
    except Exception as e:
        logger.error(f"❌ Error marking message as read: {e}")

# Function to get or create the user session
def get_or_create_user_session(sender_id, sender_name):
    user_session = get_user_session(sender_id, sender_name)
    return user_session

# Function to save the user message to the conversation history
def save_user_message_to_history(user_session, text):
    if text:
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=text,
            role="user"
        )

# Function to handle cart updates based on the response data
def handle_cart_updates(user_session, response_data):
    if 'products' in response_data:
        if response_data.get('intent') == 'add_to_cart':
            try:
                update_cart_add_products(user_session, response_data)
                update_user_session(user_session['user_id'], {'cart': user_session['cart']})
            except Exception as e:
                logger.error(f"❌ Error updating cart (add): {e}")
        elif response_data.get('intent') == 'remove_from_cart':
            try:
                update_cart_remove_products(user_session, response_data)
                update_user_session(user_session['user_id'], {'cart': user_session['cart']})
            except Exception as e:
                logger.error(f"❌ Error updating cart (remove): {e}")

# Function to generate the response based on the message
def generate_and_send_response(data, message, sender_id, sender_name, user_session, text):
    message_hash = hashlib.md5(f"{sender_id}:{text}:{message.get('id')}".encode()).hexdigest()

    try:
        response_data = generate_llm_response(
            text, 
            sender_name, 
            user_session['cart'], 
            global_inventory,
            user_session['conversation_history']
        )
        
        if isinstance(response_data, str):
            reply_text = response_data
        else:
            reply_text = response_data.get('reply', f"Hi {sender_name}, thanks for your message!")
            handle_cart_updates(user_session, response_data)
            
            # Check if order is completed and finalize it
            if response_data.get('intent') == 'confirm_order' and response_data.get('checkout_stage') == 'completed':
                try:
                    # Extract order details from conversation history
                    order_details = extract_order_details_from_history(user_session['conversation_history'])
                    
                    # Finalize the order
                    from .llm_checkout import finalize_checkout_order
                    finalization_result = finalize_checkout_order(
                        user_session['user_id'], 
                        user_session['cart']['items'], 
                        order_details
                    )
                    
                    if finalization_result['status'] == 'success':
                        # Clear cart after successful order
                        user_session['cart'] = {'items': [], 'total': 0}
                        update_user_session(user_session['user_id'], {'cart': user_session['cart']})
                        
                        # Update response with order confirmation
                        order_id = finalization_result['order_id']
                        total_amount = finalization_result['total_amount']
                        reply_text += f"\n\n🎉 Your order #{order_id[:8]} has been confirmed! Total: ${total_amount:.2f}\n\nYou'll receive a confirmation message shortly with delivery details."
                    else:
                        logger.error(f"❌ Order finalization failed: {finalization_result.get('error')}")
                        reply_text += "\n\nSorry, there was an issue processing your order. Please try again."
                except Exception as e:
                    logger.error(f"❌ Error processing order completion: {e}")
                    reply_text += "\n\nSorry, there was an issue processing your order. Please try again."
        interactive_message = (False,"")
        try:
            if response_data.get('intent') == 'view_inventory':
                if response_data.get("show_products") == True: 
                    interactive_message = (True,"product")
                if response_data.get("show_categories") == True:
                    interactive_message = (True,"category")
        except:
            interactive_message = False

        if message_hash not in processed_messages:
            processed_messages[message_hash] = {'time': time.time(), 'status': 'processed'}
            # Send WhatsApp message
            if not interactive_message[0]:
                send_whatsapp_message(
                    phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                    recipient_phone=sender_id,
                    message=reply_text,
                    id = message.get("id", None)
                )
            else:
                if interactive_message[1] == "product":
                    

                    # Generate a random UUID (UUID4)
                    unique_id = uuid.uuid4()
                    current_id = str(unique_id)
                    # Convert the UUID to a string
                    unique_id = str(unique_id)
                    # Append sender ID
                    unique_id += f"-{sender_id}"
                    current_id += f"-{sender_id}"
                    # Append message order number
                    
                        
                    
                    current_id += f"-1"
                    # Generate unique ID for different buttons
                    current_id_next = f"{current_id}-next"
                    current_id_addtocart = f"{current_id}-addtocart"
                    current_id_details = f"{current_id}-details"
                    # current_id_previous = f"{current_id}-previous"

                    for i in range(1, len(response_data.get("product_details")) + 1):
                        # Append the order number to the unique ID
                        uniqueid = unique_id + f"-{i}"
                        supabase_client = create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY"))
                        
                        response = supabase_client.table('interactive_messages').insert({
                            'id': uniqueid,
                            'secondary_id': f"{unique_id}-{i-1}-next",
                            'media_id': create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY")).table("products").select("image_path").eq("id", response_data.get("product_details")[i-1]['product_id']).execute().data[0]["image_path"],
                            'body': f"{response_data.get("product_details")[i-1]['reply']}",
                            'footer': f"Navigate with the buttons below",
                            'buttons': "{'next': 'next', 'addtocart': 'addtocart', 'details': 'details'}"
                        }).execute()
                        
                        if response.data and len(response.data) > 0:
                            user_data = response.data[0]
                            logger.info(f"✅ Interactive Message created with ID: {user_data['id']}")
                            
                    send_interactive_message(
                        phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={"type": "image", "image": {"link": create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY")).table("products").select("image_path").eq("id", response_data.get("product_details")[0]['product_id']).execute().data[0]["image_path"]}},
                        body={"text": f"{response_data.get("product_details")[0]['reply']}"},
                        footer={"text": f"Navigate with the buttons below"},
                        action={"buttons": [
                            {"type": "reply", "reply": {"id": f"{current_id_next}", "title": "Next"}},
                            {"type": "reply", "reply": {"id": f"{current_id_addtocart}", "title": "Add to Cart"}},
                            {"type": "reply", "reply": {"id": f"{current_id_details}", "title": "Details"}}
                        ]},
                        id = message.get("id", None)
                    )

                    
                elif interactive_message[1] == "category":
                    # Generate a random UUID (UUID4)
                    unique_id = uuid.uuid4()
                    current_id = str(unique_id)
                    # Convert the UUID to a string
                    unique_id = str(unique_id)
                    # Append sender ID
                    unique_id += f"-{sender_id}"
                    current_id += f"-{sender_id}"
                    # Append message order number
                    current_id += f"-1"
                    
                    # Generate unique ID for different buttons
                    current_id_next = f"{current_id}-next"
                    current_id_show_products = f"{current_id}-showproducts"
                    current_id_explore = f"{current_id}-explore"
                    
                    # Save category data to database for retrieval in button handlers
                    for i in range(1, len(response_data.get("category_details", [])) + 1):
                        # Append the order number to the unique ID
                        uniqueid = unique_id + f"-{i}"
                        supabase_client = create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY"))
                        
                        response = supabase_client.table('interactive_messages').insert({
                            'id': uniqueid,
                            'secondary_id': f"{unique_id}-{i-1}-next",
                            'media_id': create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY")).table("categories").select("image_path").eq("id", response_data.get("category_details")[i-1]['category_id']).execute().data[0]["image_path"],
                            'body': f"{response_data.get('category_details')[i-1]['reply']}",
                            'footer': f"Navigate with the buttons below",
                            'buttons': "{'next': 'next', 'showproducts': 'showproducts', 'explore': 'explore'}"
                        }).execute()
                        
                        if response.data and len(response.data) > 0:
                            user_data = response.data[0]
                            logger.info(f"✅ Interactive Message created with ID: {user_data['id']}")
                    
                    # Initial category display - show first category
                    category_text = ""
                    if response_data.get("category_details") and len(response_data.get("category_details")) > 0:
                        category_text = response_data.get("category_details")[0]['reply']
                    
                    send_interactive_message(
                        phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={"type": "image", "image": {"link": create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY")).table("categories").select("image_path").eq("id", response_data.get("category_details")[0]['category_id']).execute().data[0]["image_path"]}},
                        body={"text": category_text},
                        footer={"text": f"Navigate with the buttons below"},
                        action={"buttons": [
                            {"type": "reply", "reply": {"id": f"{current_id_next}", "title": "Next"}},
                            {"type": "reply", "reply": {"id": f"{current_id_show_products}", "title": "Show Products"}},
                            {"type": "reply", "reply": {"id": f"{current_id_explore}", "title": "Explore"}}
                        ]}
                        , id = message.get("id", None)
                    )

            # Save assistant response to conversation history in database
            save_conversation_message(
                session_id=user_session['session_id'],
                user_id=user_session['user_id'],
                content=reply_text,
                role="assistant"
            )

            logger.info(f"📤 Sent message {message.get('id')}: {reply_text[:50]}...")

    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        # Send error message only if we haven't processed this message already
        if message_hash not in processed_messages:
            send_whatsapp_message(
                phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                recipient_phone=sender_id,
                message=f"Sorry, I'm having technical difficulties. Please try again in a moment.",
                id = message.get("id", None)
            )

# Main process function, calling all the helper functions
def process_message_event(data):
    message = data.get('message', {})
    sender = data.get('sender', {})
    sender_id = sender.get("id")
    sender_name = sender.get("profile_name", "Customer")
    
    # Extract message content
    text = extract_message_content(message)

    # Log the message
    logger.info(f"📨 Message from {sender_id} ({sender_name}): {text}")

    # Mark message as read
    mark_message_read(data, message)
    send_typing_indicator(data['metadata']['phone_number_id'],message['id'])
    # Get or create the user session
    user_session = get_or_create_user_session(sender_id, sender_name)

    # Save user message to history
    save_user_message_to_history(user_session, text)

    # Generate and send the response
    generate_and_send_response(data, message, sender_id, sender_name, user_session, text)

# [Rest of your functions remain the same - initialize_global_inventory, refresh_global_inventory, 
# is_duplicate_message, process_webhook_event, process_button_event, update_cart_add_products, 
# update_cart_remove_products, process_generic_event, generate_llm_response]

def initialize_global_inventory():
    """Initialize the global inventory from the database"""
    global global_inventory
    
    try:
        logger.info("🔄 Initializing global inventory...")
        
        # Get categories and products from database
        categories_result = get_all_categories()
        products_result = get_all_products()
        
        if categories_result['status'] == 'success' and products_result['status'] == 'success':
            # Create nested inventory JSON
            global_inventory = create_nested_inventory_json(
                categories_result['data'],
                products_result['data']
            )
            logger.info(f"✅ Global inventory initialized with {len(products_result['data'])} products across {len(categories_result['data'])} categories")
        else:
            # Fallback to sample inventory if database access fails
            logger.warning("⚠️ Failed to load inventory from database, using fallback sample inventory")
            global_inventory = {
                'products': [
                    {'id': 'p1', 'name': 'T-shirt', 'category': 'clothing', 'price': 19.99, 'stock': 50},
                    {'id': 'p2', 'name': 'Jeans', 'category': 'clothing', 'price': 39.99, 'stock': 30},
                    {'id': 'p3', 'name': 'Smartphone', 'category': 'electronics', 'price': 499.99, 'stock': 10}
                ]
            }
    except Exception as e:
        logger.error(f"❌ Error initializing global inventory: {e}")
        # Set a basic fallback inventory
        global_inventory = {
            'products': [
                {'id': 'p1', 'name': 'T-shirt', 'category': 'clothing', 'price': 19.99, 'stock': 50},
                {'id': 'p2', 'name': 'Jeans', 'category': 'clothing', 'price': 39.99, 'stock': 30},
                {'id': 'p3', 'name': 'Smartphone', 'category': 'electronics', 'price': 499.99, 'stock': 10}
            ]
        }

def refresh_global_inventory():
    """Refresh the global inventory from the database"""
    initialize_global_inventory()
    logger.info("🔄 Global inventory refreshed")

def is_duplicate_message(message_id, timestamp=None):
    """
    Check if a message has been processed recently to avoid duplicates due to retries.
    
    Args:
        message_id (str): The WhatsApp message ID
        timestamp (str, optional): The message timestamp
        
    Returns:
        bool: True if this is a duplicate message, False otherwise
    """
    current_time = time.time()
    
    # Clean up old entries
    expired_messages = [mid for mid, data in processed_messages.items() 
                       if current_time - data['time'] > DUPLICATE_MESSAGE_TIMEOUT]
    
    for mid in expired_messages:
        del processed_messages[mid]
    
    # Check if this message is already processed
    if message_id in processed_messages:
        logger.info(f"🔄 Duplicate message detected: {message_id}")
        return True
    
    # Mark as processed
    processed_messages[message_id] = {
        'time': current_time,
        'timestamp': timestamp
    }
    return False

def process_webhook_event(data):
    """
    Process incoming WhatsApp webhook events.
    """
    # Ensure global inventory is initialized
    if global_inventory is None:
        initialize_global_inventory()
        
    logger.info(f"📥 Received webhook: {json.dumps(data, indent=2)}")
    
    event_type = "unknown"
    response = {"status": "processed", "event_type": event_type}
    
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                field = change.get("field")
                
                # Process incoming messages
                if field == "messages" and "messages" in value and value["messages"][0].get("type") != "interactive":
                    event_type = "message"
                    
                    for message in value["messages"]:
                        message_id = message.get("id")
                        timestamp = message.get("timestamp")
                        
                        # Skip duplicate messages (prevents processing the same message multiple times)
                        if is_duplicate_message(message_id, timestamp):
                            response = {"status": "skipped_duplicate", "event_type": event_type}
                            continue
                        
                        normalized_data = {
                            "type": "message",
                            "message": message,
                            "sender": {
                                "id": message.get("from"),
                                "profile_name": value.get("contacts", [{}])[0].get("profile", {}).get("name")
                            },
                            "metadata": value.get("metadata", {})
                        }
                        
                        # Process the message
                        process_message_event(normalized_data)
                
                # Process status updates
                elif field == "messages" and "statuses" in value:
                    event_type = "status_update"
                    
                    for status_update in value["statuses"]:
                        message_id = status_update.get("id")
                        status = status_update.get("status")
                        recipient_id = status_update.get("recipient_id")
                        
                        if message_id and status:
                            logger.info(f"📊 Status update for message {message_id}: {status}")
                            
                            # If read receipt, log it
                            if status == "read" and recipient_id:
                                logger.info(f"📱 Message {message_id} was read by {recipient_id}")
                                
                elif field == "messages" and value["messages"][0].get("type") == "interactive":
                    event_type = "button_pressed"
                    phone_number_id = value.get("metadata", {}).get("phone_number_id")

                    for button_event in value["messages"]:
                        interactive = button_event.get("interactive", {})
                        if interactive.get("type") == "button_reply":
                            button_payload = interactive.get("button_reply", {}).get("id")
                            sender_id = button_event.get("from")
                            name = value.get("contacts", [{}])[0].get("profile", {}).get("name")
                            process_button_event(button_payload, sender_id, phone_number_id, button_event,name)

                            
                # Process other event types
                else:
                    process_generic_event(change)
    
    response["event_type"] = event_type
    return response

def process_button_event(button_payload, sender_id, phone_number_id, message, name):
    """Process button press events"""
    logger.info(f"🔘 Button pressed: {button_payload} by {sender_id}")
    mark_message_as_read(
        phone_number_id=phone_number_id,
        message_id=message.get("id")
    )
    send_typing_indicator(phone_number_id, message['id'])
    
    # Get user session first
    user_session = get_or_create_user_session(sender_id, name)
    
    # Create Supabase client
    url = os.getenv("INVENTORY_SUPABASE_URL")
    key = os.getenv("INVENTORY_SUPABASE_KEY")
    supabase_client = create_client(url, key)
    
    # Extract the action from button payload
    if "next" in button_payload:
        is_last = True
        response = supabase_client.table('interactive_messages').select('footer', 'body', 'buttons').eq(
            'secondary_id',
            "-".join(button_payload.split("-")[:-2] + [str(int(button_payload.split("-")[-2]) + 1), "next"])
        ).execute()

        if response.data and len(response.data) > 0:
            is_last = False
        # Handle Next button - show next product or category
        next_parts = button_payload.split("-")
        
        # The index in the button payload is already the correct one
        logger.info(f"📊 Button payload: {button_payload}")
        
        # Query the table to find next item
        response = supabase_client.table('interactive_messages').select('footer', 'body', 'buttons', 'media_id').eq('secondary_id', button_payload).execute()
        
        # Log the response for debugging
        logger.info(f"📊 Next item query response: {response.data}")
        
        if response.data and len(response.data) > 0 and not is_last:
            next_item = response.data[0]
            
            # Validate the data before sending
            body_text = next_item.get('body', '').strip()
            footer_text = next_item.get('footer', '').strip()
            buttons_data = next_item.get('buttons', '')
            id = next_item.get('media_id', '')
            
            # Check if body_text is empty - this might be causing the 400 error
            if not body_text:
                logger.error(f"❌ Empty body text found for next item: {button_payload}")
                # Fallback to a generic message
                body_text = "Loading next item..."
            
            # Extract the base parts and current index from the button payload
            base_parts = next_parts[:-2]  # Everything except the last two parts (index and action)
            current_index = int(next_parts[-2])  # The current index
            
            # When moving to next item, we're now showing the next item (current_index)
            # All buttons should use this index for Add to Cart and Details
            # But Next button uses current_index + 1
            show_index = current_index

            # Save navigation event to conversation history
            save_conversation_message(
                session_id=user_session['session_id'],
                user_id=user_session['user_id'],
                content="[Clicked Next button]",
                role="user"
            )

            # Check if this is product or category navigation
            if "addtocart" in buttons_data:
                # This is product navigation
                # Save what the user is now viewing
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content=f"Now viewing: {body_text}",
                    role="assistant"
                )
                
                send_interactive_message(
                    phone_number_id=phone_number_id,
                    recipient_phone=sender_id,
                    interactive_type="button",
                    header={
                        "type": "image",
                        "image": {"link": id}
                    },
                    body={"text": body_text},
                    footer={"text": "Navigate with the buttons below"},
                    action={"buttons": [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index + 1), "next"])}", "title": "Next"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index+1), "addtocart"])}", "title": "Add to Cart"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index+1), "details"])}", "title": "Details"}}
                    ]}
                )
            elif "showproducts" in buttons_data:
                # This is category navigation
                # Save what the user is now viewing
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content=f"Now viewing category: {body_text}",
                    role="assistant"
                )
                
                send_interactive_message(
                    phone_number_id=phone_number_id,
                    recipient_phone=sender_id,
                    interactive_type="button",
                    header={
                        "type": "image",
                        "image": {"link": id}
                    },
                    body={"text": body_text},
                    footer={"text": "Navigate with the buttons below"},
                    action={"buttons": [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index + 1), "next"])}", "title": "Next"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index+1), "showproducts"])}", "title": "Show Products"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(show_index+1), "explore"])}", "title": "Explore"}}
                    ]}
                )
        else:
            # No more items to show, show end of list message
            logger.info(f"📊 No more items found. Showing end of list message.")
            
            # Extract parts from the button payload
            base_parts = next_parts[:-2]
            current_index = int(next_parts[-2])
            
            # Get current item data by constructing the right ID
            current_item_id = "-".join(base_parts + [str(current_index)])
            
            # Get current item data for fallback
            curr_response = supabase_client.table('interactive_messages').select('buttons', 'body', 'footer','media_id').eq('id', current_item_id).execute()
            
            if curr_response.data and len(curr_response.data) > 0:
                button_data = curr_response.data[0].get('buttons', '')
                body_text = curr_response.data[0].get('body', 'End of list')
                footer_text = curr_response.data[0].get('footer', '')
                id = curr_response.data[0].get('media_id', '')
                
                # Save navigation event to conversation history
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content="[Clicked Next button - reached end of list]",
                    role="user"
                )
                
                # Check if this is product or category navigation
                if "addtocart" in button_data:
                    # This is product list end
                    save_conversation_message(
                        session_id=user_session['session_id'],
                        user_id=user_session['user_id'],
                        content=f"You've reached the end of the product list. Current product: {body_text}",
                        role="assistant"
                    )
                    
                    send_interactive_message(
                        phone_number_id=phone_number_id,
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={
                            "type": "image",
                            "image": {"link": id}
                        },
                        body={"text": body_text},
                        footer={"text": "End of product list. What would you like to do?"},
                        action={"buttons": [
                            {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index+1), "addtocart"])}", "title": "Add to Cart"}},
                            {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index+1), "details"])}", "title": "Details"}},
                            {"type": "reply", "reply": {"id": "browse_more", "title": "Browse More"}}
                        ]}
                    )
                elif "showproducts" in button_data:
                    # This is category list end
                    save_conversation_message(
                        session_id=user_session['session_id'],
                        user_id=user_session['user_id'],
                        content=f"You've reached the end of the category list. Current category: {body_text}",
                        role="assistant"
                    )
                    
                    send_interactive_message(
                        phone_number_id=phone_number_id,
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={
                            "type": "image",
                            "image": {"link": id}
                        },
                        body={"text": body_text},
                        footer={"text": "End of category list. What would you like to do?"},
                        action={"buttons": [
                            {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index+1), "showproducts"])}", "title": "Show Products"}},
                            {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index+1), "explore"])}", "title": "Explore"}},
                            {"type": "reply", "reply": {"id": "browse_more", "title": "Browse More"}}
                        ]}
                    )

    if "addtocart" in button_payload:
        # Get the current product info
        product_response = supabase_client.table('interactive_messages').select('body').eq('secondary_id', "-".join(button_payload.split("-")[:-2]+[str(int(button_payload.split("-")[-2])-1),"next"])).execute()
        product_text = ""
        if product_response.data and len(product_response.data) > 0:
            product_text = product_response.data[0]['body']
        
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Add to Cart button for: {product_text}]",
            role="user"
        )
        
        # Save user message to conversation history
        user_message = f"Add to cart: {product_text}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        # Create data structure similar to process_message_event
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        # Now call generate_and_send_response to process the add to cart request
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)

    elif "details" in button_payload:
        # Get the current product info
        product_response = supabase_client.table('interactive_messages').select('body').eq('secondary_id', "-".join(button_payload.split("-")[:-2]+[str(int(button_payload.split("-")[-2])-1),"next"])).execute()
        product_text = ""
        if product_response.data and len(product_response.data) > 0:
            product_text = product_response.data[0]['body']
        
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Details button for: {product_text}]",
            role="user"
        )
        
        # Save user message to conversation history
        user_message = f"Tell me more about: {product_text}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        # Create data structure similar to process_message_event
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        # Now call generate_and_send_response to process the product details request
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "showproducts" in button_payload:
        # Handle show products button press
        response = supabase_client.table('interactive_messages').select('body').eq('secondary_id', "-".join(button_payload.split("-")[:-2]+[str(int(button_payload.split("-")[-2])-1),"next"])).execute()
        category_text = ""
        if response.data and len(response.data) > 0:
            category_text = response.data[0]['body']
        
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Show Products button for category: {category_text}]",
            role="user"
        )
        
        # Save user message to conversation history
        user_message = f"Show products in category: {category_text}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        # Create data structure similar to process_message_event
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        # Now call generate_and_send_response to process the show products request
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "explore" in button_payload:
        # Handle explore button press
        response = supabase_client.table('interactive_messages').select('body').eq('secondary_id', "-".join(button_payload.split("-")[:-2]+[str(int(button_payload.split("-")[-2])-1),"next"])).execute()
        category_text = ""
        if response.data and len(response.data) > 0:
            category_text = response.data[0]['body']
        
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Explore button for category: {category_text}]",
            role="user"
        )
        
        # Save user message to conversation history
        user_message = f"Tell me more about category: {category_text}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        # Create data structure similar to process_message_event
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        # Now call generate_and_send_response to process the explore category request
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "browse_more" in button_payload:
        # Handle browse more button press - takes user back to category view
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content="[Clicked Browse More button]",
            role="user"
        )
        
        user_message = "Show me categories"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        # Create data structure similar to process_message_event
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        # Now call generate_and_send_response to process the browse more request
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)


def update_cart_add_products(user_session, response_data):
    """Helper function to add products to cart from LLM response"""
    try:
        # Import the get_product_details function (add this at the top of your file)
        from .db_inventory import get_product_details
        
        # Check if the response contains a "NEED" key with non-empty value
        if "NEED" in response_data and response_data["NEED"]:
            logger.info(f"🔄 LLM needs more information: {response_data.get('NEED')}")
            return
        
        # Get the products from the response
        products = response_data.get('products', [])
        if not products:
            logger.warning("⚠️ No products found in response data")
            return
            
        logger.info(f"🔄 Processing {len(products)} products for cart addition")
        
        # Initialize cart if needed
        if not isinstance(user_session.get('cart'), dict):
            user_session['cart'] = {'items': [], 'total': 0}
        if not isinstance(user_session['cart'].get('items'), list):
            user_session['cart']['items'] = []
        
        # Process each product
        for product in products:
            try:
                # Get product details - handle various formats that might come from LLM
                if isinstance(product, dict):
                    product_name = product.get('product', '')
                    product_id = product.get('product_id', None)
                    product_price = product.get('price', None)  # Get price if provided in response
                    quantity = int(product.get('quantity', 1))
                    description = product.get('description', '')
                    variant = product.get('variant', '')
                elif isinstance(product, str):
                    # If product is a simple string
                    product_name = product
                    product_id = None
                    product_price = None
                    quantity = 1
                    description = ''
                    variant = ''
                else:
                    logger.warning(f"⚠️ Unexpected product format: {type(product)}")
                    continue
                
                if not product_name:
                    logger.warning("⚠️ Skipping product with no name")
                    continue
                
                logger.info(f"🔄 Adding product: {product_name}, quantity: {quantity}")
                
                # Find product in database using product_id if available
                found_product = None
                if product_id:
                    product_result = get_product_details(product_id)
                    
                    if product_result['status'] == 'success' and product_result['data']:
                        found_product = product_result['data']
                        product_price = found_product.get('unit_price')  # Update price if found
                        logger.info(f"📦 Found product by ID: {found_product.get('name')}")
                
                # If product not found by ID or ID not provided
                if not found_product:
                    # We need to use the global inventory to find by name
                    # Handle global_inventory as string (JSON) if needed
                    inventory_dict = global_inventory
                    if isinstance(global_inventory, str):
                        try:
                            inventory_dict = json.loads(global_inventory)
                        except json.JSONDecodeError:
                            logger.error("❌ Failed to parse global_inventory as JSON")
                            inventory_dict = {"products": []}
                    
                    # Safe check for inventory structure
                    if isinstance(inventory_dict, dict):
                        inventory_products = inventory_dict.get('products', [])
                        
                        # Try to find by name
                        for p in inventory_products:
                            if not isinstance(p, dict):
                                continue
                            p_name = p.get('name', '')
                            if p_name and p_name.lower() == product_name.lower():
                                # Found by name, now get details by ID
                                p_id = p.get('id', '')
                                if p_id:
                                    product_result = get_product_details(p_id)
                                    if product_result['status'] == 'success' and product_result['data']:
                                        found_product = product_result['data']
                                        logger.info(f"📦 Found product by name: {found_product.get('name')}, price: {found_product.get('price')}")
                                        break
                
                if not found_product:
                    logger.warning(f"⚠️ Product not found in database: {product_name}")
                    # Add a placeholder product if not found - use price from response if available
                    price_to_use = 0.0
                    if product_price is not None:
                        try:
                            price_to_use = float(product_price)
                        except (ValueError, TypeError):
                            logger.warning(f"⚠️ Invalid price in product data: {product_price}")
                    
                    new_item = {
                        'id': product_id or f"placeholder_{product_name.replace(' ', '_')}",
                        'name': product_name,
                        'quantity': quantity,
                        'price': price_to_use
                    }
                    # Add description and variant if available
                    if description:
                        new_item['description'] = description
                    if variant:
                        new_item['variant'] = variant
                        
                    user_session['cart']['items'].append(new_item)
                    logger.info(f"✅ Added placeholder product to cart: {product_name}, price: {price_to_use}")
                    continue
                    
                # Check if product already in cart
                existing_product = None
                for item in user_session['cart']['items']:
                    if not isinstance(item, dict):
                        continue  # Skip if not a dictionary
                    
                    # Match by ID if available, otherwise by name
                    if product_id and item.get('id') == product_id:
                        existing_product = item
                        break
                    elif item.get('name', '').lower() == product_name.lower():
                        existing_product = item
                        break
                
                # Get the price to use (with priority order)
                price_to_use = 0.0
                # 1. Try price from database
                if found_product.get('price') is not None:
                    try:
                        price_to_use = float(found_product['price'])
                        logger.info(f"📦 Using price from database: {price_to_use}")
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Invalid price in database: {found_product.get('price')}")
                
                # 2. If database price is 0 or invalid, try price from response
                if price_to_use == 0.0 and product_price is not None:
                    try:
                        price_to_use = float(product_price)
                        logger.info(f"📦 Using price from response: {price_to_use}")
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Invalid price in response: {product_price}")
                
                if existing_product:
                    # Check if we have enough available stock for the additional quantity
                    if found_product.get('id'):
                        stock_check = get_available_stock(found_product['id'])
                        if stock_check['status'] == 'success':
                            available = stock_check['available_stock']
                            if available < quantity:
                                logger.warning(f"⚠️ Insufficient stock for {product_name}. Available: {available}, Requested: {quantity}")
                                continue
                    
                    # Reserve additional stock
                    if found_product.get('id'):
                        reservation_result = reserve_stock(found_product['id'], quantity, user_session['user_id'])
                        if reservation_result['status'] != 'success':
                            logger.warning(f"⚠️ Could not reserve stock for {product_name}: {reservation_result.get('error')}")
                            continue
                    
                    # Update quantity of existing product
                    existing_product['quantity'] = int(existing_product.get('quantity', 0)) + quantity
                    logger.info(f"✅ Updated quantity for {product_name} to {existing_product['quantity']}")
                else:
                    # Check if we have enough available stock for new item
                    if found_product.get('id'):
                        stock_check = get_available_stock(found_product['id'])
                        if stock_check['status'] == 'success':
                            available = stock_check['available_stock']
                            if available < quantity:
                                logger.warning(f"⚠️ Insufficient stock for {product_name}. Available: {available}, Requested: {quantity}")
                                continue
                        
                        # Reserve stock
                        reservation_result = reserve_stock(found_product['id'], quantity, user_session['user_id'])
                        if reservation_result['status'] != 'success':
                            logger.warning(f"⚠️ Could not reserve stock for {product_name}: {reservation_result.get('error')}")
                            continue
                    
                    # Add new product to cart
                    new_item = {
                        'id': found_product.get('id', f"product_{product_name.replace(' ', '_')}"),
                        'name': found_product.get('name', product_name),
                        'quantity': quantity,
                        'price': price_to_use  # Use the determined price
                    }
                    # Add description and variant if available from database or provided
                    if found_product.get('description'):
                        new_item['description'] = found_product['description']
                    elif description:
                        new_item['description'] = description
                        
                    if found_product.get('variant'):
                        new_item['variant'] = found_product['variant']
                    elif variant:
                        new_item['variant'] = variant
                        
                    # Add category if available
                    if found_product.get('categories') and isinstance(found_product['categories'], dict):
                        new_item['category'] = found_product['categories'].get('name', '')
                        
                    user_session['cart']['items'].append(new_item)
                    logger.info(f"✅ Added new product to cart: {product_name}, price: {price_to_use}")
            
            except Exception as e:
                logger.error(f"❌ Error processing product {product}: {str(e)}")
        
        # Calculate cart total
        total = 0
        for item in user_session['cart']['items']:
            if isinstance(item, dict):
                price = float(item.get('price', 0))
                quantity = int(item.get('quantity', 0))
                total += price * quantity
        
        user_session['cart']['total'] = total
        logger.info(f"✅ Cart updated with {len(user_session['cart']['items'])} items, total: {total}")
        
        # Debug - log the entire cart
        logger.info(f"📦 Current cart state: {json.dumps(user_session['cart'])}")
        
    except Exception as e:
        logger.error(f"❌ Error in update_cart_add_products: {str(e)}")
        # Even if error, try to return a valid cart
        if not isinstance(user_session.get('cart'), dict):
            user_session['cart'] = {'items': [], 'total': 0}


def update_cart_remove_products(user_session, response_data):
    """Helper function to remove products from cart based on LLM response"""
    try:
        # Check if the response contains a "NEED" key with non-empty value
        if "NEED" in response_data and response_data["NEED"]:
            logger.info(f"🔄 LLM needs more information: {response_data.get('NEED')}")
            return
        
        # Get the products from the response
        products = response_data.get('products', [])
        if not products:
            logger.warning("⚠️ No products found in response data for removal")
            return
            
        logger.info(f"🔄 Processing {len(products)} products for cart removal")
        
        # Initialize cart if needed
        if not isinstance(user_session.get('cart'), dict):
            user_session['cart'] = {'items': [], 'total': 0}
            return
        if not isinstance(user_session['cart'].get('items'), list):
            user_session['cart']['items'] = []
            return
        
        # Process each product to remove
        for product in products:
            try:
                # Get product details
                if isinstance(product, dict):
                    product_name = product.get('product', '')
                    quantity_to_remove = int(product.get('quantity', 0)) if product.get('quantity') else None
                    product_id = product.get('product_id', None)
                else:
                    product_name = str(product)
                    quantity_to_remove = None
                    product_id = None
                
                if not product_name:
                    logger.warning("⚠️ Skipping removal of product with no name")
                    continue
                
                logger.info(f"🔄 Removing product: {product_name}, quantity: {quantity_to_remove}")
                
                # Check for 'all' to clear the cart
                if product_name.lower() == 'all':
                    # Release reserved stock for all items before clearing cart
                    for item in user_session['cart']['items']:
                        if isinstance(item, dict) and item.get('id'):
                            release_reserved_stock(item.get('id'), item.get('quantity', 0), user_session['user_id'])
                    user_session['cart'] = {'items': [], 'total': 0}
                    logger.info("🧹 Cleared all items from cart and released reserved stock")
                    return
                
                # Find the product in cart
                found_item = None
                for i, item in enumerate(user_session['cart']['items']):
                    if not isinstance(item, dict):
                        continue
                    
                    # Match by ID if available, otherwise by name
                    if product_id and item.get('id') == product_id:
                        found_item = (i, item)
                        break
                    elif item.get('name', '').lower() == product_name.lower():
                        found_item = (i, item)
                        break
                
                if not found_item:
                    logger.warning(f"⚠️ Product not found in cart: {product_name}")
                    continue
                
                item_index, cart_item = found_item
                current_quantity = int(cart_item.get('quantity', 0))
                
                # Determine how much to remove
                if quantity_to_remove is None or quantity_to_remove >= current_quantity:
                    # Remove entire item
                    removed_quantity = current_quantity
                    # Release reserved stock
                    if cart_item.get('id'):
                        release_reserved_stock(cart_item.get('id'), removed_quantity, user_session['user_id'])
                    user_session['cart']['items'].pop(item_index)
                    logger.info(f"✅ Removed entire item: {product_name} (quantity: {removed_quantity})")
                else:
                    # Remove partial quantity
                    new_quantity = current_quantity - quantity_to_remove
                    cart_item['quantity'] = new_quantity
                    # Release reserved stock for removed quantity
                    if cart_item.get('id'):
                        release_reserved_stock(cart_item.get('id'), quantity_to_remove, user_session['user_id'])
                    logger.info(f"✅ Reduced quantity of {product_name} from {current_quantity} to {new_quantity}")
            
            except Exception as e:
                logger.error(f"❌ Error removing product {product}: {str(e)}")
        
        # Calculate cart total
        total = 0
        for item in user_session['cart']['items']:
            if isinstance(item, dict):
                price = float(item.get('price', 0))
                quantity = int(item.get('quantity', 0))
                total += price * quantity
        
        user_session['cart']['total'] = total
        logger.info(f"✅ Cart updated after removal, {len(user_session['cart']['items'])} items remain, total: {total}")
        
        # Debug - log the entire cart
        logger.info(f"📦 Current cart state: {json.dumps(user_session['cart'])}")
        
    except Exception as e:
        logger.error(f"❌ Error in update_cart_remove_products: {e}")


def extract_order_details_from_history(conversation_history):
    """Extract order details from conversation history"""
    order_details = {
        'payment_method': 'unknown',
        'payment_details': 'unknown', 
        'phone_number': 'unknown',
        'delivery_address': 'unknown'
    }
    
    # Look through conversation history for order details
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            content = msg["content"]
            try:
                data = json.loads(content)
                if "payment_method" in data and data["payment_method"] != "unknown":
                    order_details["payment_method"] = data["payment_method"]
                if "payment_details" in data and data["payment_details"] != "unknown":
                    order_details["payment_details"] = data["payment_details"]
                if "phone_number" in data and data["phone_number"] != "unknown":
                    order_details["phone_number"] = data["phone_number"]
                if "delivery_address" in data and data["delivery_address"] != "unknown":
                    order_details["delivery_address"] = data["delivery_address"]
            except:
                pass
                
    return order_details

def process_generic_event(data):
    """Handle other event types."""
    logger.info(f"⚠️ Unhandled event: {json.dumps(data, indent=2)}")

def generate_llm_response(text, sender_name, cart=None, inventory=None, conversation_history=None, max_retries=3):
    """
    Generate a response using LLM.py functions with retry logic for rate limiting
    
    Args:
        text (str): The user's message
        sender_name (str): Name of the sender
        cart (dict): User's current cart
        inventory (dict): Global inventory
        conversation_history (list): Previous messages
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        dict or str: The generated response data or text
    """
    if conversation_history is None:
        conversation_history = []
    
    # Prepare cart and inventory for LLM
    cart_json = json.dumps(cart) if cart else "{}"
    inventory_json = json.dumps(inventory) if inventory else "{}"
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            # Step 1: Classify intent
            intent_response = classify_intent(text, cart_json, inventory_json, conversation_history)
            intent_data = json.loads(intent_response)
            intent = intent_data.get('intent', '').lower()
            
            # Log the intent
            logger.info(f"🧠 Classified intent: {intent}")
            
            # Step 2: Based on intent, call the appropriate handler
            response = None
            
            if intent == "smalltalk":
                response = handle_smalltalk(text, sender_name, conversation_history)
                
            elif intent == "view_inventory":
                response = handle_view_inventory(text, inventory_json, conversation_history, sender_name)
                
            elif intent == "add_to_cart":
                response = handle_add_to_cart(text, cart_json, inventory_json, conversation_history, sender_name)
                
            elif intent == "remove_from_cart":
                response = handle_remove_from_cart(text, cart_json, conversation_history, sender_name)
                
            elif intent == "view_cart":
                response = handle_view_cart(text, cart_json, conversation_history, sender_name)
                
            elif intent == "product_info":
                response = handle_product_info(text, inventory_json, conversation_history, sender_name)
                
            elif intent == "confirm_order":
                response = handle_confirm_order(text, cart_json, conversation_history, sender_name)
                
            elif intent == "confirm_action":
                response = handle_confirm_action(text, conversation_history, None, sender_name)
                
            elif intent == "track_order":
                response = handle_track_order(text, conversation_history, None, sender_name)
                
            elif intent == "not_sure" or intent == "not sure" or intent == "not_sure":
                response = handle_NOT_SURE(text, cart_json, inventory_json, conversation_history, sender_name)
                
            else:
                # Default fallback 
                response = json.dumps({
                    "intent": "unknown",
                    "reply": f"Hi {sender_name}, I'm not sure how to help with that. Can you try rephrasing?"
                })
            
            # Parse the response JSON
            if isinstance(response, str):
                try:
                    response_data = json.loads(response)
                    # Add the intent to the response data
                    response_data['intent'] = intent
                    return response_data
                except json.JSONDecodeError:
                    # If the response is not valid JSON, return as is
                    return response
            else:
                # If response is already parsed
                if isinstance(response, dict):
                    response['intent'] = intent
                return response
                
        except Exception as e:
            last_error = e
            retry_count += 1
            
            # Check if it's a rate limit error
            if "429" in str(e) or "Too Many Requests" in str(e):
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.warning(f"⏱️ Rate limit exceeded, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                # For other errors, don't retry
                logger.error(f"❌ Error generating LLM response: {e}")
                break
    
    logger.error(f"❌ Failed to generate response after {retry_count} attempts: {last_error}")
    return f"Hi {sender_name}, I'm having some technical issues. Please try again in a moment."       