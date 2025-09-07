import os
import logging
import requests
import datetime
from dotenv import load_dotenv
import json
import time
# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def mark_message_as_read(phone_number_id, message_id):
    """
    Mark a WhatsApp message as read.
    
    Args:
        phone_number_id (str): The WhatsApp business phone number ID.
        message_id (str): The message ID of the message to mark as read.
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not access_token:
        raise ValueError("Missing WhatsApp Access Token.")
    
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload, timeout=10)

    if response.status_code == 200:
        logger.info(f"✅ Message {message_id} marked as read successfully!")
    else:
        logger.error(f"❌ Failed to mark message as read: {response.status_code} {response.text}")


def send_whatsapp_message(id, phone_number_id, recipient_phone, message, enable_preview=False):
    """
    Send a WhatsApp text message using the WhatsApp Business API
    
    Parameters:
    phone_number_id (str): Your WhatsApp Business Phone Number ID
    recipient_phone (str): Recipient's phone number with country code (e.g., "+16505551234")
    message (str): The message text to send (max 4096 characters)
    enable_preview (bool): Whether to enable link preview for URLs in the message
    
    Returns:
    dict: The API response as a dictionary
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not access_token:
        logger.error("Missing WhatsApp Access Token")
        return {"error": "Missing access token"}
    
    # Validate input parameters
    if not phone_number_id or not isinstance(phone_number_id, str):
        logger.error("Invalid phone_number_id")
        return {"error": "Invalid phone_number_id"}
    
    if not recipient_phone or not isinstance(recipient_phone, str):
        logger.error("Invalid recipient phone number")
        return {"error": "Invalid recipient phone number"}
        
    if not message or not isinstance(message, str):
        logger.error("Message cannot be empty")
        return {"error": "Message cannot be empty"}
    
    if len(message) > 4096:
        logger.error("Message exceeds maximum length of 4096 characters")
        return {"error": "Message exceeds maximum length of 4096 characters"}
    
    # API endpoint
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    # Request payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "text",
        "context": {
    "message_id": id
  },
        "text": {
            "preview_url": enable_preview,
            "body": message
        }
    }
    
    try:
        # Send the request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Check for successful response
        response.raise_for_status()
        
        logger.info(f"✅ Message sent to {recipient_phone} successfully")
        # Return the response as a dictionary
        return response.json()
    
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        logger.error(f"❌ Error sending WhatsApp message: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return {"error": str(e)}


def send_whatsapp_reply(phone_number_id, recipient_id, message):
    """
    Send a reply message using the WhatsApp API.
    Legacy function maintained for backward compatibility.
    """
    return send_whatsapp_message(phone_number_id, recipient_id, message)


def send_media_message(phone_number_id, recipient_phone, media_type, media_id=None, media_url=None, caption=None):
    """
    Send a WhatsApp media message (image, video, document, etc.)
    
    Args:
        phone_number_id (str): Your WhatsApp Business Phone Number ID
        recipient_phone (str): Recipient's phone number with country code
        media_type (str): 'image', 'video', 'document', 'audio', etc.
        media_id (str, optional): ID of a previously uploaded media
        media_url (str, optional): URL of the media to send
        caption (str, optional): Caption for the media
        
    Returns:
        dict: The API response as a dictionary
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    if not access_token:
        logger.error("Missing WhatsApp Access Token")
        return {"error": "Missing access token"}
    
    # Either media_id or media_url must be provided
    if not media_id and not media_url:
        logger.error("Either media_id or media_url must be provided")
        return {"error": "Either media_id or media_url must be provided"}
    
    # API endpoint
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    # Build media object
    media_obj = {}
    if media_id:
        media_obj["id"] = media_id
    elif media_url:
        media_obj["link"] = media_url
    
    if caption and media_type in ["image", "video", "document"]:
        media_obj["caption"] = caption
    
    # Request payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": media_type,
        media_type: media_obj
    }
    
    try:
        # Send the request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Check for successful response
        response.raise_for_status()
        
        logger.info(f"✅ {media_type.capitalize()} sent to {recipient_phone} successfully")
        # Return the response as a dictionary
        return response.json()
    
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        logger.error(f"❌ Error sending WhatsApp {media_type}: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return {"error": str(e)}


def send_interactive_message(phone_number_id, recipient_phone, interactive_type, header=None, body=None, footer=None, action=None,id=None):
    """
    Send a WhatsApp interactive message (buttons, list, product, etc.)
    
    Args:
        phone_number_id (str): Your WhatsApp Business Phone Number ID
        recipient_phone (str): Recipient's phone number with country code
        interactive_type (str): Type of interactive message ('button', 'list', 'product', etc.)
        header (dict, optional): Header content with 'type' ('text', 'image', etc.) and content
        body (dict, optional): Body content with 'text' field
        footer (dict, optional): Footer content with 'text' field
        action (dict, optional): Interactive elements (buttons, sections, etc.)
        
    Returns:
        dict: The API response as a dictionary
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    if not access_token:
        logger.error("Missing WhatsApp Access Token")
        return {"error": "Missing access token"}
    
    # Validate essential parameters
    if not phone_number_id or not isinstance(phone_number_id, str):
        logger.error("Invalid phone_number_id")
        return {"error": "Invalid phone_number_id"}
    
    if not recipient_phone or not isinstance(recipient_phone, str):
        logger.error("Invalid recipient phone number")
        return {"error": "Invalid recipient phone number"}
    
    if not interactive_type or interactive_type not in ["button", "list", "product", "product_list", "catalog_message"]:
        logger.error(f"Invalid interactive type: {interactive_type}")
        return {"error": f"Invalid interactive type: {interactive_type}"}
    
    # Interactive requires body content
    if not body or not isinstance(body, dict) or not body.get("text"):
        logger.error("Interactive message requires body text")
        return {"error": "Interactive message requires body text"}
    
    # Button type requires action with buttons
    if interactive_type == "button" and (not action or not action.get("buttons")):
        logger.error("Button interactive message requires buttons in action")
        return {"error": "Button interactive message requires buttons in action"}
    
    # List type requires action with sections
    if interactive_type == "list" and (not action or not action.get("sections")):
        logger.error("List interactive message requires sections in action")
        return {"error": "List interactive message requires sections in action"}
    
    # API endpoint
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    # Build interactive object
    interactive_obj = {
        "type": interactive_type
    }
    
    if header:
        interactive_obj["header"] = header
    
    if body:
        interactive_obj["body"] = body
    
    if footer:
        interactive_obj["footer"] = footer
        print("abcx",interactive_obj["footer"]["text"])
        if len(interactive_obj["footer"]["text"]) > 60:
            logger.error("Footer text exceeds maximum length of 60 characters")
            interactive_obj["footer"]["text"] = interactive_obj["footer"]["text"][:60]
    
    if action:
        interactive_obj["action"] = action
    # if id is none skip otherwise add it to payload.context.message_id


    # Request payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "interactive",
        "interactive": interactive_obj
    }
    if id:
        if "context" not in payload:
            payload["context"] = {}
        payload["context"]["message_id"] = id
    
    # DEBUG: Print request information before sending
    logger.info("=== WhatsApp API Request Debug ===")
    logger.info(f"URL: {url}")
    logger.info(f"Headers: {headers}")
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    logger.info("===============================")
    
    try:
        # Send the request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # DEBUG: Print response information after sending
        logger.debug("=== WhatsApp API Response Debug ===")
        logger.debug(f"Status Code: {response.status_code}")
        logger.debug(f"Response Headers: {dict(response.headers)}")
        logger.debug(f"Response Body: {response.text}")
        logger.debug("==============================")
        
        # Check for successful response
        response.raise_for_status()
        
        logger.info(f"✅ Interactive message ({interactive_type}) sent to {recipient_phone} successfully")
        # Return the response as a dictionary
        return response.json()
    
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        logger.error(f"❌ Error sending WhatsApp interactive message: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return {"error": str(e)}
    
def send_typing_indicator(phone_number_id, message_id):
    """
    Send a typing indicator for a WhatsApp conversation.
    
    Args:
        phone_number_id (str): Your WhatsApp Business Phone Number ID
        message_id (str): The message ID to which this typing indicator responds
        
    Returns:
        dict: The API response as a dictionary
    """
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    if not access_token:
        logger.error("Missing WhatsApp Access Token")
        return {"error": "Missing access token"}
    
    # Validate input parameters
    if not phone_number_id or not isinstance(phone_number_id, str):
        logger.error("Invalid phone_number_id")
        return {"error": "Invalid phone_number_id"}
    
    if not message_id or not isinstance(message_id, str):
        logger.error("Invalid message_id")
        return {"error": "Invalid message_id"}
    
    # API endpoint
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    
    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    # Request payload
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        }
    }
    
    try:
        # Send the request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Check for successful response
        response.raise_for_status()
        
        logger.info(f"✅ Typing indicator sent for message {message_id} successfully")
        # Return the response as a dictionary
        return response.json()
    
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        logger.error(f"❌ Error sending typing indicator: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response text: {e.response.text}")
        return {"error": str(e)}