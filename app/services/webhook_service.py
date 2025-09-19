"""
Webhook service module for WhatsApp bot
Handles incoming webhook events and message processing
"""

import json
import logging
import datetime
import time
import hashlib
from typing import Dict, Any, List, Tuple
import requests
import tempfile
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid

from app.utils.match import find_matching_products, safe_type_conversion
from app.utils.search_match import find_matching_products as find_matching_products_alt

def _is_valid_uuid(value):
    """Check if a value is a valid UUID"""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False

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
    get_product_details
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

# Skip heavy imports if we're starting with fast mode
if os.getenv('SKIP_EMBEDDINGS_ON_STARTUP', 'false').lower() == 'true':
    logger.info("⚡ Fast startup mode - skipping heavy database operations")
    # Initialize with minimal inventory immediately
    global_inventory = {
        'products': [
            {'id': 'sample1', 'name': 'Sample Product', 'category': 'sample', 'price': 10.0, 'stock': 1}
        ]
    }

# Message deduplication cache
processed_messages = {}
DUPLICATE_MESSAGE_TIMEOUT = 60  # seconds

# Initialize search functionality
search_engine = None

try:
    from app.utils.search import FlaskConversationSearcher
    search_engine = FlaskConversationSearcher()
    search_engine.initialize()
    logger.info("✅ Search engine initialized successfully")
except Exception as e:
    logger.error(f"❌ Error initializing search engine: {e}")
    search_engine = None

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
def handle_cart_updates(user_session: Dict, response_data: Dict) -> Dict:
    """
    Enhanced cart update handler with proper status tracking and user feedback
    """
    update_status = {
        "success": False,
        "message": "",
        "cart_changed": False,
        "errors": []
    }
    
    try:
        intent = response_data.get('intent', '').lower()
        
        # Only process if there are products in the response
        if 'products' in response_data or response_data.get('NEED'):
            
            if intent == 'add_to_cart':
                try:
                    # Assuming you have this function implemented
                    status = update_cart_add_products(user_session, response_data)
                    update_status.update(status)
                    
                    if status.get("cart_updated"):
                        update_user_session(user_session['user_id'], {'cart': user_session['cart']})
                        update_status["cart_changed"] = True
                        
                except Exception as e:
                    error_msg = f"Error adding to cart: {e}"
                    logger.error(f"❌ {error_msg}")
                    update_status["errors"].append(error_msg)
                    
            elif intent == 'remove_from_cart':
                try:
                    status = update_cart_remove_products(user_session, response_data)
                    update_status.update(status)
                    
                    if status.get("cart_updated"):
                        update_user_session(user_session['user_id'], {'cart': user_session['cart']})
                        update_status["cart_changed"] = True
                        
                except Exception as e:
                    error_msg = f"Error removing from cart: {e}"
                    logger.error(f"❌ {error_msg}")
                    update_status["errors"].append(error_msg)
        
        # Set overall success
        update_status["success"] = update_status["cart_changed"] and len(update_status["errors"]) == 0
        
        return update_status
        
    except Exception as e:
        logger.error(f"❌ Critical error in handle_cart_updates: {e}")
        update_status["errors"].append(f"System error: {str(e)}")
        return update_status
    
    # Function to generate the response based on the message
def _is_valid_uuid(uuid_str):
    """Helper function to validate UUID format"""
    try:
        import uuid
        uuid.UUID(uuid_str)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def generate_and_send_response(data, message, sender_id, sender_name, user_session, text):
    import hashlib
    import uuid
    import time
    import os
    from supabase import create_client
    
    message_hash = hashlib.md5(f"{sender_id}:{text}:{message.get('id')}".encode()).hexdigest()

    try:
        response_data = generate_llm_response(
            text,
            sender_name,
            user_session['cart'],
            global_inventory,
            user_session['conversation_history'],
            max_retries=3,
            user_id=sender_id
        )

        # Handle case where generate_llm_response returns None
        if response_data is None:
            response_data = {
                'intent': 'smalltalk',
                'reply': f"Hi {sender_name}, I'm having trouble processing your message right now. Please try again in a moment."
            }

        if isinstance(response_data, str):
            reply_text = response_data
        else:
            reply_text = response_data.get('reply', f"Hi {sender_name}, thanks for your message!")
            handle_cart_updates(user_session, response_data)
        
        interactive_message = (False, "")
        try:
            if response_data.get('intent') == 'view_inventory':
                # Check if we have actual product details before setting interactive message
                if response_data.get("show_products") == True and response_data.get("product_details"):
                    interactive_message = (True, "product")
                elif response_data.get("show_categories") == True and response_data.get("category_details"):
                    interactive_message = (True, "category")
            elif response_data.get('intent') == 'view_cart':
                if response_data.get("show_cart_interactive") == True and response_data.get("cart_items"):
                    interactive_message = (True, "cart")
        except:
            interactive_message = (False, "")

        if message_hash not in processed_messages:
            processed_messages[message_hash] = {'time': time.time(), 'status': 'processed'}
            
            # Send WhatsApp message
            if not interactive_message[0]:
                send_whatsapp_message(
                    phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                    recipient_phone=sender_id,
                    message=reply_text,
                    id=message.get("id", None)
                )
            else:
                if interactive_message[1] == "product":
                    # Safety check: Ensure product_details exists and is not None
                    product_details = response_data.get("product_details", [])
                    if not product_details:
                        logger.warning("⚠️ No product_details found in response_data, skipping interactive message creation")
                        send_whatsapp_message(
                            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                            recipient_phone=sender_id,
                            message=reply_text,
                            id=message.get("id", None)
                        )
                        return

                    # Generate a random UUID
                    unique_id = str(uuid.uuid4()) + f"-{sender_id}"
                    
                    # Store all products in database with correct indexing
                    supabase_client = create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY"))
                    
                    for i in range(len(product_details)):
                        # Database entries use 1-based indexing
                        db_index = i + 1
                        uniqueid = f"{unique_id}-{db_index}"
                        
                        # For secondary_id: store the current item's index
                        secondary_id = f"{unique_id}-{db_index}-next"
                        
                        current_product = product_details[i]
                        
                        # Handle both 'id' and 'product_id' field names for compatibility
                        product_id_value = current_product.get('product_id') or current_product.get('id')
                        
                        # Fetch product data from database
                        product_result = supabase_client.table("products").select(
                            "images, description, title, available_sizes, colors, regular_price, sale_price"
                        ).eq("id", product_id_value).execute()
                        
                        product_image = None
                        product_description = current_product.get('reply', current_product.get('title', 'Product Details'))
                        
                        if product_result.data and len(product_result.data) > 0:
                            product_data = product_result.data[0]
                            
                            # Get the last image for interactive message
                            if product_data.get("images"):
                                product_images = product_data["images"]
                                product_image = product_images[-1] if product_images else None
                            
                            # Build comprehensive product description
                            title = product_data.get("title", "Product")
                            description = product_data.get("description", "")
                            colors = product_data.get("colors", [])
                            sizes = product_data.get("available_sizes", [])
                            regular_price = float(product_data.get("regular_price", 0)) if product_data.get("regular_price") else 0
                            sale_price = float(product_data.get("sale_price", 0)) if product_data.get("sale_price") else 0
                            
                            product_description = f"*{title}*\n\n"
                            if description:
                                product_description += f"{description}\n\n"
                            
                            # Add price information
                            if sale_price and sale_price > 0 and sale_price < regular_price:
                                product_description += f"💰 *Price:* PKR {sale_price} _(was PKR {regular_price})_\n"
                            elif regular_price and regular_price > 0:
                                product_description += f"💰 *Price:* PKR {regular_price}\n"
                            
                            # Add colors if available
                            if colors and len(colors) > 0:
                                colors_text = ", ".join(colors[:5])
                                if len(colors) > 5:
                                    colors_text += f" (+{len(colors)-5} more)"
                                product_description += f"🎨 *Colors:* {colors_text}\n"
                            
                            # Add sizes if available
                            if sizes and len(sizes) > 0:
                                sizes_text = ", ".join(map(str, sizes[:8]))
                                if len(sizes) > 8:
                                    sizes_text += f" (+{len(sizes)-8} more)"
                                product_description += f"👠 *Sizes:* {sizes_text}"
                        
                        # Validate product_id is a proper UUID
                        product_id = current_product.get('product_id') or current_product.get('id')
                        if product_id and not _is_valid_uuid(product_id):
                            logger.warning(f"Invalid product_id format: {product_id}, setting to None")
                            product_id = None
                        
                        # Insert into database
                        response = supabase_client.table('interactive_messages').insert({
                            'id': uniqueid,
                            'secondary_id': secondary_id,
                            'media_id': product_image,
                            'body': product_description,
                            'footer': f"Product {db_index} of {len(product_details)}",
                            'buttons': "{'next': 'next', 'addtocart': 'addtocart', 'details': 'details'}",
                            'product_id': product_id
                        }).execute()
                        
                        if response.data and len(response.data) > 0:
                            logger.info(f"✅ Product {db_index} stored with secondary_id: {secondary_id}")
                    
                    # Now prepare and send the first product display
                    # Show the first item (index 1)
                    # Query the database to get the first item we just stored
                    first_item_response = supabase_client.table('interactive_messages').select(
                        'body', 'media_id', 'footer'
                    ).eq('secondary_id', f"{unique_id}-1-next").execute()
                    
                    if first_item_response.data and len(first_item_response.data) > 0:
                        first_item_data = first_item_response.data[0]
                        first_product_description = first_item_data['body']
                        first_product_image = first_item_data['media_id']
                        
                        # Send product images if available
                        first_product_id = product_details[0].get('product_id') or product_details[0].get('id')
                        if first_product_id:
                            first_product_result = supabase_client.table("products").select("images").eq(
                                "id", first_product_id
                            ).execute()
                            
                            if first_product_result.data and len(first_product_result.data) > 0:
                                first_product_images = first_product_result.data[0].get("images", [])
                                
                                # Send first 4 images as separate messages
                                if first_product_images and len(first_product_images) > 0:
                                    images_to_send = min(4, len(first_product_images) - 1) if len(first_product_images) > 1 else 0
                                    
                                    for i in range(images_to_send):
                                        image_url = first_product_images[i]
                                        if image_url:
                                            try:
                                                from app.services.messaging_service import send_media_message
                                                send_media_message(
                                                    phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                                                    recipient_phone=sender_id,
                                                    media_type="image",
                                                    media_url=image_url,
                                                    caption=f"Product Image {i+1}/{len(first_product_images)}"
                                                )
                                                time.sleep(0.5)
                                            except Exception as e:
                                                logger.error(f"Failed to send product image {i+1}: {e}")
                    else:
                        # Fallback if database query fails
                        first_product_description = reply_text
                        first_product_image = None
                    
                    # Prepare buttons for first product
                    total_products = len(product_details)
                    
                    buttons = []
                    if total_products > 1:
                        # Show next button pointing to second item
                        buttons.append({"type": "reply", "reply": {"id": f"{unique_id}-2-next", "title": "Next ➡️"}})
                    buttons.extend([
                        {"type": "reply", "reply": {"id": f"{unique_id}-1-addtocart", "title": "Add to Cart"}},
                        {"type": "reply", "reply": {"id": f"{unique_id}-1-details", "title": "Details"}}
                    ])
                    
                    send_interactive_message(
                        phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={"type": "image", "image": {"link": first_product_image}} if first_product_image else None,
                        body={"text": first_product_description},
                        footer={"text": f"Product 1 of {total_products}"},
                        action={"buttons": buttons},
                        id=message.get("id", None)
                    )
                
                elif interactive_message[1] == "category":
                    # Safety check: Ensure category_details exists and is not None
                    category_details = response_data.get("category_details", [])
                    if not category_details:
                        logger.warning("⚠️ No category_details found in response_data, skipping interactive message creation")
                        send_whatsapp_message(
                            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                            recipient_phone=sender_id,
                            message=reply_text,
                            id=message.get("id", None)
                        )
                        return

                    # Generate a random UUID
                    unique_id = str(uuid.uuid4()) + f"-{sender_id}"
                    
                    # Store all categories in database with correct indexing
                    supabase_client = create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY"))
                    
                    for i in range(len(category_details)):
                        # Database entries use 1-based indexing
                        db_index = i + 1
                        uniqueid = f"{unique_id}-{db_index}"
                        
                        # For secondary_id: store the current item's index
                        secondary_id = f"{unique_id}-{db_index}-next"
                        
                        current_category = category_details[i]
                        
                        # Categories use placeholder images
                        category_image = "https://via.placeholder.com/400x400/f0f0f0/666666?text=Category"
                        
                        # Validate category_id
                        category_id = current_category.get('category_id')
                        if category_id and not _is_valid_uuid(category_id):
                            logger.warning(f"Invalid category_id format: {category_id}, setting to None")
                            category_id = None
                        
                        # Insert into database
                        response = supabase_client.table('interactive_messages').insert({
                            'id': uniqueid,
                            'secondary_id': secondary_id,
                            'media_id': category_image,
                            'body': f"{current_category['reply']}",
                            'footer': f"Category {db_index} of {len(category_details)}",
                            'buttons': "{'next': 'next', 'showproducts': 'showproducts', 'explore': 'explore'}",
                            'category_id': category_id
                        }).execute()
                        
                        if response.data and len(response.data) > 0:
                            logger.info(f"✅ Category {db_index} stored with secondary_id: {secondary_id}")
                    
                    # Send placeholder image for categories
                    placeholder_image = "https://via.placeholder.com/400x400/f0f0f0/666666?text=Category"
                    
                    try:
                        from app.services.messaging_service import send_media_message
                        send_media_message(
                            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                            recipient_phone=sender_id,
                            media_type="image",
                            media_url=placeholder_image,
                            caption="Category"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send category placeholder image: {e}")
                    
                    # Prepare first category display
                    category_text = category_details[0]['reply']
                    total_categories = len(category_details)
                    
                    # Prepare buttons for first category
                    buttons = []
                    if total_categories > 1:
                        buttons.append({"type": "reply", "reply": {"id": f"{unique_id}-2-next", "title": "Next ➡️"}})
                    buttons.extend([
                        {"type": "reply", "reply": {"id": f"{unique_id}-1-showproducts", "title": "Show Products"}},
                        {"type": "reply", "reply": {"id": f"{unique_id}-1-explore", "title": "Explore"}}
                    ])
                    
                    send_interactive_message(
                        phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                        recipient_phone=sender_id,
                        interactive_type="button",
                        header={"type": "image", "image": {"link": placeholder_image}},
                        body={"text": category_text},
                        footer={"text": f"Category 1 of {total_categories}"},
                        action={"buttons": buttons},
                        id=message.get("id", None)
                    )

                elif interactive_message[1] == "cart":
                    # Handle cart interactive messages
                    cart_items = response_data.get("cart_items", [])

                    if cart_items and len(cart_items) > 0:
                        # Generate unique UUID for cart navigation
                        unique_id = str(uuid.uuid4()) + f"-{sender_id}"
                        
                        supabase_client = create_client(os.getenv("INVENTORY_SUPABASE_URL"), os.getenv("INVENTORY_SUPABASE_KEY"))
                        
                        # Store all cart items in database with correct indexing
                        for i, item in enumerate(cart_items):
                            db_index = i + 1
                            item_id = f"{unique_id}-{db_index}"
                            secondary_id = f"{unique_id}-{db_index}-next"
                            
                            # Create description for this item
                            item_desc = f"*{item.get('product_name', 'Cart Item')}*\n\n"
                            if item.get('size'):
                                item_desc += f"👠 Size: {item['size']}\n"
                            if item.get('color'):
                                item_desc += f"🎨 Color: {item['color']}\n"
                            item_desc += f"📦 Quantity: {item.get('quantity', 1)}\n"
                            item_desc += f"💰 Price: PKR {item.get('price', 0)} each\n"
                            item_desc += f"💳 Total: PKR {item.get('item_total', 0)}"
                            
                            # Get product image for this item
                            item_image = None
                            if item.get('product_id'):
                                item_product_result = supabase_client.table("products").select("images").eq(
                                    "id", item['product_id']
                                ).execute()
                                
                                if item_product_result.data and len(item_product_result.data) > 0:
                                    item_product_data = item_product_result.data[0]
                                    if item_product_data.get("images"):
                                        item_image = item_product_data["images"][-1]
                            
                            # Store in interactive_messages table
                            response = supabase_client.table('interactive_messages').insert({
                                'id': item_id,
                                'secondary_id': secondary_id,
                                'media_id': item_image,
                                'body': item_desc,
                                'footer': f"Cart item {db_index} of {len(cart_items)}",
                                'buttons': "{'next': 'next', 'remove': 'remove', 'checkout': 'checkout'}",
                                'product_id': item.get('product_id')
                            }).execute()
                            
                            if response.data and len(response.data) > 0:
                                logger.info(f"✅ Cart item {db_index} stored with secondary_id: {secondary_id}")
                        
                        # Prepare first cart item display
                        first_item = cart_items[0]
                        first_product_id = first_item.get('product_id')
                        first_product_image = None
                        
                        if first_product_id:
                            product_result = supabase_client.table("products").select("images, title").eq(
                                "id", first_product_id
                            ).execute()
                            
                            if product_result.data and len(product_result.data) > 0:
                                product_data = product_result.data[0]
                                if product_data.get("images"):
                                    first_product_image = product_data["images"][-1]
                        
                        # Create cart item description
                        cart_description = f"*{first_item.get('product_name', 'Cart Item')}*\n\n"
                        if first_item.get('size'):
                            cart_description += f"👠 Size: {first_item['size']}\n"
                        if first_item.get('color'):
                            cart_description += f"🎨 Color: {first_item['color']}\n"
                        cart_description += f"📦 Quantity: {first_item.get('quantity', 1)}\n"
                        cart_description += f"💰 Price: PKR {first_item.get('price', 0)} each\n"
                        cart_description += f"💳 Total: PKR {first_item.get('item_total', 0)}"
                        
                        # Prepare buttons for first cart item
                        total_items = len(cart_items)
                        buttons = []
                        if total_items > 1:
                            buttons.append({"type": "reply", "reply": {"id": f"{unique_id}-2-next", "title": "Next ➡️"}})
                        buttons.extend([
                            {"type": "reply", "reply": {"id": f"{unique_id}-1-remove", "title": "Remove"}},
                            {"type": "reply", "reply": {"id": f"{unique_id}-1-checkout", "title": "Checkout"}}
                        ])
                        
                        send_interactive_message(
                            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                            recipient_phone=sender_id,
                            interactive_type="button",
                            header={"type": "image", "image": {"link": first_product_image}} if first_product_image else None,
                            body={"text": cart_description},
                            footer={"text": f"Cart item 1 of {total_items}"},
                            action={"buttons": buttons},
                            id=message.get("id", None)
                        )
                    else:
                        # No cart items - send simple text message
                        send_whatsapp_message(
                            phone_number_id=data.get("metadata", {}).get("phone_number_id"),
                            recipient_phone=sender_id,
                            message=reply_text,
                            id=message.get("id", None)
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
                id=message.get("id", None)
            )

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

    # Skip initialization if embeddings are skipped to speed up startup
    if os.getenv('SKIP_EMBEDDINGS_ON_STARTUP', 'false').lower() == 'true':
        logger.info("⏩ Skipping global inventory initialization (SKIP_EMBEDDINGS_ON_STARTUP=true)")
        # Set a minimal inventory for testing
        global_inventory = {
            'products': [
                {'id': 'sample1', 'name': 'Sample Product', 'category': 'sample', 'price': 10.0, 'stock': 1}
            ]
        }
        return

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
                            process_button_event(button_payload, sender_id, phone_number_id, button_event, name)
                            
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
        # Handle Next button - show next product or category
        next_parts = button_payload.split("-")
        
        logger.info(f"📊 Next button pressed with payload: {button_payload}")
        
        # Extract base parts and indices
        base_parts = next_parts[:-2]  # Everything except index and action
        current_index = int(next_parts[-2])  # The index from the button
        
        # Query for the item at current_index (this is the item to show)
        current_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        logger.info(f"📊 Looking for item with secondary_id: {current_secondary_id}")
        
        # Get the current item to display
        response = supabase_client.table('interactive_messages').select(
            'footer', 'body', 'buttons', 'media_id', 'product_id', 'category_id'
        ).eq('secondary_id', current_secondary_id).execute()
        
        logger.info(f"📊 Current item query response: {response.data}")
        
        if response.data and len(response.data) > 0:
            current_item = response.data[0]
            
            # Check if there's a next item (for the Next button)
            next_secondary_id = "-".join(base_parts + [str(current_index + 1), "next"])
            next_response = supabase_client.table('interactive_messages').select('id').eq(
                'secondary_id', next_secondary_id
            ).execute()
            
            has_next = bool(next_response.data and len(next_response.data) > 0)
            logger.info(f"📊 Has next item: {has_next} (checked for: {next_secondary_id})")
            
            # Get item details
            body_text = current_item.get('body', '').strip()
            buttons_data = current_item.get('buttons', '')
            media_id = current_item.get('media_id', '')
            
            # Validate body text
            if not body_text:
                logger.error(f"❌ Empty body text found for item: {current_secondary_id}")
                body_text = "Loading item..."
            
            # Save navigation event
            save_conversation_message(
                session_id=user_session['session_id'],
                user_id=user_session['user_id'],
                content="[Clicked Next button]",
                role="user"
            )
            
            # Determine if this is product, category, or cart navigation
            is_product_nav = "addtocart" in buttons_data
            is_category_nav = "showproducts" in buttons_data
            is_cart_nav = "remove" in buttons_data and "checkout" in buttons_data
            
            if is_product_nav:
                # Product navigation
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content=f"Now viewing: {body_text[:50]}...",
                    role="assistant"
                )
                
                # Send product images if available
                current_product_id = current_item.get('product_id')
                if current_product_id:
                    try:
                        product_images_response = supabase_client.table("products").select(
                            "images"
                        ).eq("id", current_product_id).execute()
                        
                        if product_images_response.data and len(product_images_response.data) > 0:
                            product_images = product_images_response.data[0].get("images", [])
                            
                            # Send product images
                            if len(product_images) > 0:
                                for i, image_url in enumerate(product_images[:4]):  # Send max 4 images
                                    if image_url:
                                        try:
                                            from app.services.messaging_service import send_media_message
                                            send_media_message(
                                                phone_number_id=phone_number_id,
                                                recipient_phone=sender_id,
                                                media_type="image",
                                                media_url=image_url,
                                                caption=f"Image {i+1}/{min(4, len(product_images))}"
                                            )
                                            time.sleep(0.5)
                                        except Exception as e:
                                            logger.error(f"Failed to send product image {i+1}: {e}")
                    except Exception as e:
                        logger.error(f"Error fetching product images: {e}")
                
                # Build buttons based on navigation position
                if has_next:
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index + 1), "next"])}", "title": "Next ➡️"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "addtocart"])}", "title": "Add to Cart"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "details"])}", "title": "Details"}}
                    ]
                    footer_message = f"Product {current_index} • Swipe for more"
                else:
                    # Last item - show Start Over
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + ["1", "next"])}", "title": "Start Over 🔄"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "addtocart"])}", "title": "Add to Cart"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "details"])}", "title": "Details"}}
                    ]
                    footer_message = "End of products • Tap Start Over to begin"
                
            elif is_category_nav:
                # Category navigation
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content=f"Now viewing category: {body_text[:50]}...",
                    role="assistant"
                )
                
                # Build buttons for category navigation
                if has_next:
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index + 1), "next"])}", "title": "Next ➡️"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "showproducts"])}", "title": "Show Products"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "explore"])}", "title": "Explore"}}
                    ]
                    footer_message = f"Category {current_index} • More categories available"
                else:
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + ["1", "next"])}", "title": "Start Over 🔄"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "showproducts"])}", "title": "Show Products"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "explore"])}", "title": "Explore"}}
                    ]
                    footer_message = "End of categories • Tap Start Over to begin"
                    
            elif is_cart_nav:
                # Cart navigation
                save_conversation_message(
                    session_id=user_session['session_id'],
                    user_id=user_session['user_id'],
                    content=f"Viewing cart item {current_index}",
                    role="assistant"
                )
                
                # Build buttons for cart navigation
                if has_next:
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index + 1), "next"])}", "title": "Next ➡️"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "remove"])}", "title": "Remove"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "checkout"])}", "title": "Checkout"}}
                    ]
                    footer_message = f"Cart item {current_index} • More items in cart"
                else:
                    buttons = [
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + ["1", "next"])}", "title": "Start Over 🔄"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "remove"])}", "title": "Remove"}},
                        {"type": "reply", "reply": {"id": f"{"-".join(base_parts + [str(current_index), "checkout"])}", "title": "Checkout"}}
                    ]
                    footer_message = "Last cart item • Tap Start Over to review"
            else:
                # Unknown navigation type
                buttons = [
                    {"type": "reply", "reply": {"id": "browse_more", "title": "Browse More"}}
                ]
                footer_message = "Navigation"
            
            # Send the interactive message
            send_interactive_message(
                phone_number_id=phone_number_id,
                recipient_phone=sender_id,
                interactive_type="button",
                header={
                    "type": "image",
                    "image": {"link": media_id}
                } if media_id else None,
                body={"text": body_text},
                footer={"text": footer_message},
                action={"buttons": buttons}
            )
        else:
            # No item found - this shouldn't happen with proper data
            logger.error(f"❌ No item found for secondary_id: {current_secondary_id}")
            send_text_message(
                phone_number_id=phone_number_id,
                recipient_phone=sender_id,
                message_text="Sorry, I couldn't find that item. Please try browsing again."
            )
    
    elif "addtocart" in button_payload:
        # Extract the current index from button payload
        parts = button_payload.split("-")
        current_index = int(parts[-2])
        base_parts = parts[:-2]
        
        # Get the product info using the correct secondary_id
        product_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        product_response = supabase_client.table('interactive_messages').select(
            'body', 'product_id'
        ).eq('secondary_id', product_secondary_id).execute()
        
        product_text = ""
        product_id = None
        if product_response.data and len(product_response.data) > 0:
            product_text = product_response.data[0]['body']
            product_id = product_response.data[0].get('product_id')
        
        # Save button click as user action
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Add to Cart button]",
            role="user"
        )
        
        # Save user message to conversation history
        if product_id:
            user_message = f"Add to cart product_id: {product_id}"
        else:
            user_message = f"Add to cart: {product_text[:100]}"
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
        # Similar structure to addtocart
        parts = button_payload.split("-")
        current_index = int(parts[-2])
        base_parts = parts[:-2]
        
        product_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        product_response = supabase_client.table('interactive_messages').select('body').eq(
            'secondary_id', product_secondary_id
        ).execute()
        
        product_text = ""
        if product_response.data and len(product_response.data) > 0:
            product_text = product_response.data[0]['body']
        
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Details button]",
            role="user"
        )
        
        user_message = f"Tell me more about: {product_text[:100]}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "showproducts" in button_payload:
        parts = button_payload.split("-")
        current_index = int(parts[-2])
        base_parts = parts[:-2]
        
        category_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        response = supabase_client.table('interactive_messages').select('body').eq(
            'secondary_id', category_secondary_id
        ).execute()
        
        category_text = ""
        if response.data and len(response.data) > 0:
            category_text = response.data[0]['body']
        
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Show Products button]",
            role="user"
        )
        
        user_message = f"Show products in category: {category_text[:100]}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "explore" in button_payload:
        parts = button_payload.split("-")
        current_index = int(parts[-2])
        base_parts = parts[:-2]
        
        category_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        response = supabase_client.table('interactive_messages').select('body').eq(
            'secondary_id', category_secondary_id
        ).execute()
        
        category_text = ""
        if response.data and len(response.data) > 0:
            category_text = response.data[0]['body']
        
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Explore button]",
            role="user"
        )
        
        user_message = f"Tell me more about category: {category_text[:100]}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )
        
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)
        
    elif "browse_more" in button_payload:
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
        
        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }
        
        generate_and_send_response(data, message, sender_id, name, user_session, user_message)

    elif "remove" in button_payload:
        parts = button_payload.split("-")
        current_index = int(parts[-2])
        base_parts = parts[:-2]
        
        cart_secondary_id = "-".join(base_parts + [str(current_index), "next"])
        cart_response = supabase_client.table('interactive_messages').select('body').eq(
            'secondary_id', cart_secondary_id
        ).execute()
        
        cart_item_text = ""
        if cart_response.data and len(cart_response.data) > 0:
            cart_item_text = cart_response.data[0]['body']

        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=f"[Clicked Remove Item button]",
            role="user"
        )

        user_message = f"Remove from cart: {cart_item_text[:100]}"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )

        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }

        generate_and_send_response(data, message, sender_id, name, user_session, user_message)

    elif "checkout" in button_payload:
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content="[Clicked Checkout button]",
            role="user"
        )

        user_message = "I want to checkout"
        save_conversation_message(
            session_id=user_session['session_id'],
            user_id=user_session['user_id'],
            content=user_message,
            role="user"
        )

        data = {
            "metadata": {
                "phone_number_id": phone_number_id
            }
        }

        generate_and_send_response(data, message, sender_id, name, user_session, user_message)

def update_cart_add_products(user_session, response_data):
    """Helper function to add products to cart from LLM response using CartManager"""

    # Initialize status tracking
    operation_status = {
        "success": False,
        "added_items": [],
        "errors": [],
        "needs_clarification": False,
        "user_message": "",
        "cart_updated": False
    }

    try:
        from .cart_manager import get_cart_manager

        # Check if the response contains a "NEED" key with non-empty value
        if "NEED" in response_data and response_data["NEED"]:
            logger.info(f"🔄 LLM needs more information: {response_data.get('NEED')}")
            operation_status["needs_clarification"] = True
            operation_status["user_message"] = response_data.get("reply", "Please provide more details.")
            return operation_status

        # Get the products from the response
        products = response_data.get('products', [])
        if not products:
            logger.warning("⚠️ No products found in response data")
            operation_status["user_message"] = response_data.get("reply", "No products specified for addition.")
            return operation_status

        logger.info(f"🔄 Processing {len(products)} products for cart addition")

        # Get cart manager instance
        cart_manager = get_cart_manager()

        # Get current cart JSON
        current_cart_json = user_session.get('cart_json', '{}')

        # Process each product
        for product in products:
            try:
                # Extract product information from LLM response
                if isinstance(product, dict):
                    product_name = product.get('product', '')
                    product_id = product.get('product_id') or product.get('id')
                    quantity = int(product.get('quantity', 1))
                    size = product.get('size', '')
                    color = product.get('color', '')
                else:
                    logger.warning(f"⚠️ Unexpected product format: {type(product)}")
                    operation_status["errors"].append(f"Invalid product format: {type(product)}")
                    continue

                # Validate required fields
                if not product_id:
                    logger.warning(f"⚠️ Product ID missing for {product_name}")
                    operation_status["errors"].append(f"Product ID missing for {product_name}")
                    continue

                if not product_name:
                    logger.warning("⚠️ Product name missing")
                    operation_status["errors"].append("Product name missing")
                    continue

                if not size:
                    logger.warning(f"⚠️ Size missing for {product_name}")
                    operation_status["errors"].append(f"Size required for {product_name}")
                    continue

                logger.info(f"🔄 Adding to cart: {product_name} (ID: {product_id}), Size: {size}, Color: {color}, Qty: {quantity}")

                # Use CartManager to add the product
                result = cart_manager.add_to_cart(
                    cart_json=current_cart_json,
                    product_id=product_id,
                    product_name=product_name,
                    color=color,
                    size=size,
                    quantity=quantity
                )

                if result['status'] == 'success':
                    # Update current cart JSON for next iteration
                    current_cart_json = result['cart']

                    operation_status["added_items"].append({
                        "product_name": product_name,
                        "product_id": product_id,
                        "quantity": quantity,
                        "size": size,
                        "color": color,
                        "action": "added_successfully"
                    })
                    operation_status["cart_updated"] = True
                    logger.info(f"✅ {result['message']}")

                else:
                    logger.error(f"❌ Failed to add {product_name}: {result['message']}")
                    operation_status["errors"].append(f"Failed to add {product_name}: {result['message']}")

                    # If color/size not available, include available options
                    if 'available_colors' in result:
                        operation_status["errors"].append(f"Available colors: {', '.join(result['available_colors'])}")
                    if 'available_sizes' in result:
                        operation_status["errors"].append(f"Available sizes: {', '.join(result['available_sizes'])}")

            except Exception as e:
                logger.error(f"❌ Error processing product {product}: {e}")
                operation_status["errors"].append(f"Error processing product: {str(e)}")

        # Update user session with new cart
        if operation_status["cart_updated"]:
            user_session['cart_json'] = current_cart_json

        # Set success status
        operation_status["success"] = len(operation_status["added_items"]) > 0
        operation_status["user_message"] = response_data.get("reply", "Products processed successfully.")

        return operation_status

    except Exception as e:
        logger.error(f"❌ Error in update_cart_add_products: {e}")
        operation_status["errors"].append(f"Cart update failed: {str(e)}")
        operation_status["user_message"] = "Sorry, there was an error updating your cart."
        return operation_status


def update_cart_remove_products(user_session: Dict, response_data: Dict) -> Dict:
    """
    Enhanced function to remove products from cart based on LLM response
    Returns status information about the operation
    """
    operation_status = {
        "success": False,
        "removed_items": [],
        "errors": [],
        "needs_clarification": False,
        "user_message": "",
        "cart_updated": False
    }
    
    try:
        # Check if LLM needs more information
        if "NEED" in response_data and response_data["NEED"]:
            logger.info(f"🔄 LLM needs more information: {response_data.get('NEED')}")
            operation_status["needs_clarification"] = True
            operation_status["user_message"] = response_data.get("reply", "Please provide more details.")
            return operation_status

        # Initialize cart if needed
        if not isinstance(user_session.get('cart'), dict):
            user_session['cart'] = {'items': [], 'total': 0}
        if not isinstance(user_session['cart'].get('items'), list):
            user_session['cart']['items'] = []

        # Get products to remove from response
        products_to_remove = response_data.get('products', [])
        if not products_to_remove:
            logger.warning("⚠️ No products specified for removal")
            operation_status["user_message"] = response_data.get("reply", "No products specified for removal.")
            return operation_status

        logger.info(f"🔄 Processing {len(products_to_remove)} products for removal")
        
        # Process each product removal
        for product_spec in products_to_remove:
            try:
                # Extract product information with validation
                if isinstance(product_spec, dict):
                    product_name = product_spec.get('product_name', product_spec.get('product', ''))
                    product_id = product_spec.get('product_id')
                    quantity_to_remove = product_spec.get('quantity_to_remove', 'all')
                else:
                    product_name = str(product_spec)
                    product_id = None
                    quantity_to_remove = 'all'

                if not product_name:
                    operation_status["errors"].append("Product name missing")
                    continue

                logger.info(f"🔄 Processing removal: {product_name} (qty: {quantity_to_remove})")

                # Handle special case: clear all cart
                if product_name.upper() == 'CLEAR_ALL' or product_name.lower() in ['all', 'everything']:
                    removed_count = len(user_session['cart']['items'])
                    user_session['cart'] = {'items': [], 'total': 0}
                    operation_status["removed_items"].append({
                        "product_name": "All items",
                        "quantity": removed_count,
                        "action": "cleared_cart"
                    })
                    operation_status["cart_updated"] = True
                    logger.info("🧹 Cleared entire cart")
                    continue

                # Find matching products in cart
                matching_items = find_matching_products(product_name, user_session['cart']['items'])
                
                if not matching_items:
                    error_msg = f"Product '{product_name}' not found in cart"
                    operation_status["errors"].append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
                    continue

                # Use the best match (highest similarity score)
                best_match, similarity = matching_items[0]
                
                # Handle quantity removal
                current_quantity = safe_type_conversion(best_match.get('quantity', 0), int, 0)
                
                if quantity_to_remove == 'all':
                    quantity_to_remove = current_quantity
                else:
                    quantity_to_remove = safe_type_conversion(quantity_to_remove, int, 0)

                if quantity_to_remove <= 0:
                    operation_status["errors"].append(f"Invalid quantity for {product_name}")
                    continue

                if quantity_to_remove >= current_quantity:
                    # Remove entire item
                    user_session['cart']['items'] = [
                        item for item in user_session['cart']['items'] 
                        if item is not best_match
                    ]
                    operation_status["removed_items"].append({
                        "product_name": best_match.get('name', product_name),
                        "quantity": current_quantity,
                        "action": "removed_completely"
                    })
                    logger.info(f"✅ Completely removed {best_match.get('name')} (qty: {current_quantity})")
                else:
                    # Reduce quantity
                    best_match['quantity'] = current_quantity - quantity_to_remove
                    operation_status["removed_items"].append({
                        "product_name": best_match.get('name', product_name),
                        "quantity": quantity_to_remove,
                        "action": "reduced_quantity",
                        "remaining": best_match['quantity']
                    })
                    logger.info(f"✅ Reduced {best_match.get('name')} quantity by {quantity_to_remove} (remaining: {best_match['quantity']})")

                operation_status["cart_updated"] = True

            except Exception as e:
                error_msg = f"Error processing {product_name}: {str(e)}"
                operation_status["errors"].append(error_msg)
                logger.error(f"❌ {error_msg}")

        # Recalculate cart total
        if operation_status["cart_updated"]:
            total = 0
            for item in user_session['cart']['items']:
                if isinstance(item, dict):
                    price = safe_type_conversion(item.get('price', 0), float, 0)
                    quantity = safe_type_conversion(item.get('quantity', 0), int, 0)
                    total += price * quantity

            user_session['cart']['total'] = total
            logger.info(f"✅ Cart updated: {len(user_session['cart']['items'])} items, total: ${total:.2f}")

        # Set overall success status
        operation_status["success"] = len(operation_status["removed_items"]) > 0
        operation_status["user_message"] = response_data.get("reply", "Cart update completed.")
        
        # Log final cart state
        logger.info(f"📦 Final cart: {json.dumps(user_session['cart'], indent=2)}")
        
        return operation_status

    except Exception as e:
        logger.error(f"❌ Critical error in update_cart_remove_products: {e}")
        operation_status["errors"].append(f"System error: {str(e)}")
        return operation_status

def process_generic_event(data):
    """Handle other event types."""
    logger.info(f"⚠️ Unhandled event: {json.dumps(data, indent=2)}")

def format_applied_filters_footer(filters: Dict) -> str:
    """Format applied filters for display in footer"""
    if not filters:
        return ""

    filter_parts = []

    # Price range
    price_range = filters.get('price_range', {})
    if price_range and (price_range.get('min') is not None or price_range.get('max') is not None):
        min_price = price_range.get('min')
        max_price = price_range.get('max')
        if min_price is not None and max_price is not None:
            filter_parts.append(f"Price: ₹{min_price}-₹{max_price}")
        elif min_price is not None:
            filter_parts.append(f"Price: ₹{min_price}+")
        elif max_price is not None:
            filter_parts.append(f"Price: Under ₹{max_price}")

    # Colors
    colors = filters.get('colors', [])
    if colors and isinstance(colors, list) and len(colors) > 0:
        if len(colors) == 1:
            filter_parts.append(f"Color: {colors[0]}")
        else:
            filter_parts.append(f"Colors: {', '.join(colors[:3])}")

    # Sizes
    sizes = filters.get('sizes', [])
    if sizes and isinstance(sizes, list) and len(sizes) > 0:
        if len(sizes) == 1:
            filter_parts.append(f"Size: {sizes[0]}")
        else:
            filter_parts.append(f"Sizes: {', '.join(map(str, sizes[:3]))}")

    # Materials
    materials = filters.get('materials', [])
    if materials and isinstance(materials, list) and len(materials) > 0:
        if len(materials) == 1:
            filter_parts.append(f"Material: {materials[0]}")
        else:
            filter_parts.append(f"Materials: {', '.join(materials[:2])}")

    # Occasions
    occasions = filters.get('occasions', [])
    if occasions and isinstance(occasions, list) and len(occasions) > 0:
        if len(occasions) == 1:
            filter_parts.append(f"Occasion: {occasions[0]}")
        else:
            filter_parts.append(f"Occasions: {', '.join(occasions[:2])}")

    if filter_parts:
        return f"🔍 Applied filters: {' | '.join(filter_parts)}"

    return ""

def handle_view_inventory_with_search(user_id: str, message: str, user_name: str = "Customer"):
    """Handle view inventory using search.py instead of LLM"""
    global search_engine

    try:
        # Check if user is asking for non-footwear items
        non_footwear_keywords = [
            "clothes", "clothing", "cotton", "fabric", "shirts", "pants", "dress", "kurta", "kameez",
            "suit", "dupatta", "scarf", "lawn", "cambric", "voile", "linen", "silk", "chiffon"
        ]

        is_non_footwear_query = any(keyword.lower() in message.lower() for keyword in non_footwear_keywords)

        if is_non_footwear_query:
            # Get categories for interactive messages even for non-footwear responses
            try:
                categories_result = get_all_categories()
                category_details = []
                if categories_result['status'] == 'success':
                    categories = categories_result['data']
                    for category in categories:
                        category_details.append({
                            "category_id": category.get('id'),
                            "reply": f"{category.get('name', 'Unknown Category')} - {category.get('description', 'Premium footwear collection')}"
                        })
            except Exception as e:
                logger.error(f"Error loading categories for non-footwear response: {e}")
                category_details = []

            return {
                "intent": "view_inventory",
                "reply": f"Hi {user_name}, I appreciate your interest! However, we are ECS - Ehsan Chappal Store and we specialize exclusively in footwear. We don't carry clothing items like cotton clothes or fabric suits.\n\nWe have a beautiful collection of:\n- Ladies shoes\n- Chappals\n- Sandals\n- Slippers\n\nWould you like to see our footwear collection instead?",
                "show_products": False,
                "show_categories": True,
                "category_details": category_details
            }

        # Check if this is a general query (should show categories)
        general_queries = [
            "kya hai", "kya kya hai", "kya he", "kya kya he", "what do you have",
            "what products", "view inventory", "inventory", "categories", 
            "what is available", "acha apke pas kya kya he"
        ]

        # Special handling for "show me" - only treat as general if not followed by specific terms
        show_me_pattern = "show me"
        specific_product_terms = [
            "heels", "sandals", "slippers", "shoes", "boots", "flats", "pumps", 
            "loafers", "sneakers", "khussas", "chappals", "mules"
        ]
        
        is_general_query = any(query.lower() in message.lower() for query in general_queries)
        
        # Check for "show me" with specific product terms
        if show_me_pattern.lower() in message.lower():
            # If "show me" is followed by a specific product term, treat as specific search
            has_specific_term = any(term.lower() in message.lower() for term in specific_product_terms)
            if has_specific_term:
                is_general_query = False
            else:
                # "show me" without specific terms is general
                is_general_query = True
        
        # Also check for single word "products" - if user just says "products", show categories
        if message.lower().strip() == "products":
            is_general_query = True

        if is_general_query:
            # Show categories for general queries
            try:
                categories_result = get_all_categories()
                if categories_result['status'] == 'success':
                    categories = categories_result['data']
                    category_list = []
                    category_details = []
                    
                    for i, category in enumerate(categories, 1):
                        category_list.append(f"{i}. {category.get('name', 'Unknown Category')}")
                        if category.get('description'):
                            category_list.append(f"   {category.get('description')}")
                        
                        # Build category_details for interactive messages
                        category_details.append({
                            "category_id": category.get('id'),
                            "reply": f"{category.get('name', 'Unknown Category')} - {category.get('description', 'Premium footwear collection')}"
                        })

                    reply_text = f"Hi {user_name}, here are our product categories:\n\n" + "\n".join(category_list)
                    reply_text += f"\n\nWe have {len(categories)} categories available. Please let me know what type of footwear you're looking for!"

                    return {
                        "intent": "view_inventory",
                        "reply": reply_text,
                        "show_products": False,
                        "show_categories": True,
                        "category_details": category_details
                    }
                else:
                    return {
                        "intent": "view_inventory",
                        "reply": f"Hi {user_name}, we have a wide selection of footwear including shoes, sandals, slippers, and more. What type are you looking for?",
                        "show_products": False,
                        "show_categories": True,
                        "category_details": []
                    }
            except Exception as e:
                logger.error(f"Error loading categories: {e}")
                return {
                    "intent": "view_inventory",
                    "reply": f"Hi {user_name}, we have a variety of footwear available. What type are you interested in?",
                    "show_products": False,
                    "show_categories": True,
                    "category_details": []
                }

        # For specific queries, continue with search
        if search_engine is None:
            logger.warning("⚠️ Search engine not initialized, using fallback response")
            return {
                "intent": "view_inventory",
                "reply": f"Hi {user_name}, I'm setting up the inventory search. Please try again in a moment.",
                "show_products": False,
                "show_categories": False
            }

        # Use the search engine to find products with conversation context
        # For WhatsApp integration, we'll pass the conversation history from the user session
        from .session_manager_conversation import get_user_session
        try:
            user_session = get_user_session(user_id, user_name)
            conversation_history = user_session.get('conversation_history', [])
        except:
            conversation_history = []

        search_result = search_engine.conversation_search(user_id, message, top_k=25, external_conversation=conversation_history)

        # Handle case where search_result is None (connection failure)
        if search_result and search_result.get("success") and search_result.get("products"):
            products = search_result["products"]
            total_found = search_result.get("total_found", len(products))

            # Format response
            if total_found == 0:
                reply_text = f"Hi {user_name}, I couldn't find any products matching '{message}'. Please try a different search term."
            else:
                # Create a formatted product list
                product_list = []
                for i, product in enumerate(products[:10], 1):  # Show max 10 products
                    price_text = f"₹{product.get('price', 'N/A')}"
                    if product.get('sale_price') and product.get('is_on_sale'):
                        price_text = f"₹{product.get('sale_price')} (was ₹{product.get('price')})"

                    product_text = f"{i}. {product.get('title', 'Unknown Product')}\n   Price: {price_text}"

                    if product.get('colors'):
                        colors = product.get('colors')
                        if isinstance(colors, list):
                            color_text = ', '.join(colors[:3])  # Show max 3 colors
                            if len(colors) > 3:
                                color_text += f" (+{len(colors)-3} more)"
                        else:
                            color_text = str(colors)
                        product_text += f"\n   Colors: {color_text}"

                    if product.get('available_sizes'):
                        sizes = product.get('available_sizes')
                        if isinstance(sizes, list):
                            size_text = ', '.join(map(str, sizes[:5]))  # Show max 5 sizes
                            if len(sizes) > 5:
                                size_text += f" (+{len(sizes)-5} more)"
                        else:
                            size_text = str(sizes)
                        product_text += f"\n   Sizes: {size_text}"

                    product_list.append(product_text)

                reply_text = f"Hi {user_name}, I found {total_found} products"
                if search_result.get("enhanced_query") and search_result.get("enhanced_query") != message:
                    reply_text += f" for '{search_result.get('enhanced_query')}'"
                reply_text += ":\n\n" + "\n\n".join(product_list)

                if total_found > 10:
                    reply_text += f"\n\n... and {total_found - 10} more products. Try being more specific to see fewer results."

                # Add applied filters footer for interactive messages
                if search_result.get("specifications") and search_result.get("specifications", {}).get("filters"):
                    filters_footer = format_applied_filters_footer(search_result["specifications"]["filters"])
                    if filters_footer:
                        reply_text += f"\n\n{filters_footer}"
        else:
            # Handle case where search_result is None or unsuccessful
            if search_result:
                error_msg = search_result.get("error", "Search failed")
            else:
                error_msg = "Connection failed"
            reply_text = f"Hi {user_name}, I'm having trouble searching the inventory: {error_msg}. Please try again in a moment."

        return {
            "intent": "view_inventory",
            "reply": reply_text,
            "show_products": True,
            "show_categories": False,
            "product_details": search_result.get("products", [])[:10] if search_result and search_result.get("success") else [],
            "applied_filters": search_result.get("specifications", {}).get("filters", {}) if search_result and search_result.get("success") else {}
        }

    except Exception as e:
        logger.error(f"❌ Error in handle_view_inventory_with_search: {e}")
        return {
            "intent": "view_inventory",
            "reply": f"Hi {user_name}, I'm having technical difficulties searching the inventory. Please try again.",
            "show_products": False,
            "show_categories": False
        }

def generate_llm_response(text, sender_name, cart=None, inventory=None, conversation_history=None, max_retries=3, user_id=None):
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
                # Use enhanced search-based handler instead of LLM to handle large inventory efficiently
                search_response = handle_view_inventory_with_search(user_id or "unknown", text, sender_name)
                response = json.dumps(search_response)
                
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