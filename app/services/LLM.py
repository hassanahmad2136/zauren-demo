"""
Main LLM module for WhatsApp e-commerce chatbot
This file maintains the original function signatures for compatibility
"""

# Import from utility modules
import os
import json
import datetime
import requests
import time
import threading
from typing import List, Dict, Any
from .llm_core import safe_api_call, prepare_messages

# Import from shopping modules
from .llm_shopping_browse import (
    handle_product_info_impl,
    handle_view_inventory_impl,
    handle_NOT_SURE_impl
)
from .llm_shopping_cart_add import (
    handle_add_to_cart_impl
)
from .llm_shopping_cart_manage import (
    handle_remove_from_cart_impl,
    handle_view_cart_impl
)

# Import from checkout module
from .llm_checkout import (
    determine_checkout_stage,
    handle_smalltalk_impl,
    handle_confirm_order_impl,
    handle_confirm_action_impl,
    handle_track_order_impl
)

# Directory for storing LLM responses
LOG_DIR = os.environ.get('LLM_LOG_DIR', 'llm_logs')

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

def threaded_api_call(func):
    """Decorator to run a function in a background thread."""
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    return wrapper

@threaded_api_call
def log_response(sender_id, intent, message, response):
    """
    Log LLM response to a text file asynchronously to avoid blocking main thread
    
    Args:
        sender_id (str): User identifier (phone number)
        intent (str): The detected intent
        message (str): The user's original message
        response (str): The LLM's response
    """
    def _log():
        try:
            # Create a timestamped filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize sender_id for filename (remove special chars)
            safe_sender = "".join([c if c.isalnum() else "_" for c in str(sender_id)])
            
            # Create unique filename
            filename = f"{timestamp}_{safe_sender}_{intent}.txt"
            filepath = os.path.join(LOG_DIR, filename)
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
                f.write(f"User ID: {sender_id}\n")
                f.write(f"Intent: {intent}\n")
                f.write(f"User Message: {message}\n")
                f.write(f"LLM Response: {response}\n")
                
                # Try to parse JSON for more detailed logging
                try:
                    response_data = json.loads(response)
                    f.write("\nParsed Response:\n")
                    for key, value in response_data.items():
                        f.write(f"{key}: {json.dumps(value, ensure_ascii=False)}\n")
                except:
                    pass
        except Exception as e:
            print(f"Error logging response: {e}")
    _log()
    return True

def generate_summary(messages: List[Dict[str, str]], role: str, max_retries: int = 2) -> str:
    """
    Generate a summary of conversation messages using Groq API
    
    Args:
        messages: List of messages to summarize
        role: Role of the messages (system, user, or assistant)
        max_retries: Maximum number of retry attempts
        
    Returns:
        str: Generated summary
    """
    if not messages:
        return f"No previous {role} messages."
        
    # Extract message contents
    contents = [msg.get('content', '') for msg in messages if msg.get('content')]
    
    if not contents:
        return f"No content in previous {role} messages."
    
    # Prepare the messages to summarize
    messages_to_summarize = "\n\n".join([f"Message {i+1}: {content}" for i, content in enumerate(contents)])
    
    # Prepare prompt for different roles
    if role == 'user':
        system_prompt = "You are a helpful assistant that creates concise summaries of user messages in a conversation."
        user_prompt = f"""Please summarize the following user messages into a concise paragraph. 
Focus on the main topics, questions, and requests. Include key details that would be important for future reference.

USER MESSAGES TO SUMMARIZE:
{messages_to_summarize}

Your summary should be under 150 words and capture the essential points."""
    
    elif role == 'assistant':
        system_prompt = "You are a helpful assistant that creates concise summaries of assistant responses in a conversation."
        user_prompt = f"""Please summarize the following assistant responses into a concise paragraph.
Focus on the key information provided, recommendations made, and questions answered.

ASSISTANT MESSAGES TO SUMMARIZE:
{messages_to_summarize}

Your summary should be under 150 words and highlight the most important information."""
    
    else:  # system
        system_prompt = "You are a helpful assistant that creates concise summaries of system instructions."
        user_prompt = f"""Please summarize the following system instructions into a concise paragraph.
Focus on the essential guidance, context, and instruction provided.

SYSTEM MESSAGES TO SUMMARIZE:
{messages_to_summarize}

Your summary should be under 150 words and capture the critical information."""
    
    # Get Groq API credentials
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY environment variable not set")
        return f"Summary unavailable due to missing API credentials"
    
    # Set the model to use
    model = os.getenv("GROQ_MODEL", "llama3-8b-8192")  # Default to Llama 3 8B
    
    # Try to call Groq API with retries
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,  # Lower temperature for more consistent summaries
                "max_tokens": 300     # Limit summary length
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=10  # Lowered timeout for faster failover
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Clean up the summary
                summary = summary.strip()
                if summary:
                    return f"Summary of {len(messages)} previous {role} messages: {summary}"
                else:
                    return f"No meaningful content found in previous {role} messages."
            
            elif response.status_code == 429:  # Rate limit
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                time.sleep(wait_time)
                
            else:
                # Log the error
                error_text = f"HTTP {response.status_code}: {response.text}"
                
                # For certain errors, we might want to retry
                if response.status_code in [500, 502, 503, 504]:  # Server errors
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    time.sleep(wait_time)
                else:
                    # For other errors, don't retry
                    return f"Summary generation failed for {len(messages)} {role} messages due to API error."
                
        except Exception as e:
            last_error = str(e)
            retry_count += 1
            wait_time = 2 ** retry_count
            time.sleep(wait_time)
    
    # If we exhausted retries
    return f"Summary of {len(messages)} previous {role} messages (generation failed after multiple attempts)."

# Export these functions to maintain backward compatibility
def classify_intent(message, cart, inventory, conversation_history, user_name=None):
    """Classify the user's intent from their message"""
    system_prompt = f"""
        You are a WhatsApp ordering assistant for a Pakistani clothing e-commerce store specializing in traditional attire.
        Your task is to accurately classify the user's intent into one of these categories:
        - smalltalk: General conversation, greetings, questions not related to ordering
        - view_inventory: User wants to see available products or categories
        - add_to_cart: User wants to add products to their cart
        - remove_from_cart: User wants to remove products from their cart
        - view_cart: User wants to see what's in their cart
        - confirm_order: User wants to complete their order
        - product_info: User wants information about specific products, if user asks for product information with images then send to view inventory
        - track_order: User wants to know the status of their order
        - NOT_SURE: When intent is genuinely ambiguous
        
        Examples:
        - "hello" → smalltalk
        - "show me your kurtas" → view_inventory
        - "I want to buy a shalwar kameez" → add_to_cart
        - "remove embroidered waistcoat from cart" → remove_from_cart
        - "what's in my cart" → view_cart
        - "I want to complete my order" → confirm_order
        - "tell me about the wedding sherwani" → product_info
        - "where is my order" → track_order
        
        
        Contextual guidance:
        - When a user asks about availability, styles, or browsing products, or even if user is just starting to buy something and he probably needs information classify as view_inventory
        - When a user asks detailed questions about a specific product, classify as product_info
        - When a user mentions buying, getting, or wanting a specific product, and has selected the product or has specified the exact prodcut classify as add_to_cart
        - For messages like "I want to see shalwar kameez", classify as view_inventory not add_to_cart
        - Messages about purchasing in general without specifying a product are view_inventory
        - "I'm looking for" statements should typically be view_inventory unless a very specific product(not category) is mentioned
        - When uncertain between multiple intents, prioritize transaction intents over smalltalk
        - Messages containing only product names should be classified as product_info
        
        -----IMPORTANT---------------------------------------- 
        NEED TO FOLLOW THE FOLLOWING FORMAT STRICTLY                              
        Respond with a JSON object that includes:
        1. "intent": One of the categories listed above
        2. For NOT_SURE intent only: Include a "reply" field with a question asking for clarification
           - The reply should be concise and natural for WhatsApp, similar in length to how a human would text
           - Always respond in the same language the user used in their message
        ----------------------------------------------------------------------
        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    response = safe_api_call(messages)
    
    # Extract sender_id from conversation history if available
    sender_id = "unknown"
    if conversation_history and len(conversation_history) > 0:
        for msg in reversed(conversation_history):
            if msg.get("role") == "user" and msg.get("sender_id"):
                sender_id = msg.get("sender_id")
                break
    
    # Try to get intent for logging
    try:
        intent_data = json.loads(response)
        intent = intent_data.get("intent", "unknown")
        log_response(sender_id, f"classify_{intent}", message, response)
    except:
        log_response(sender_id, "classify_error", message, response)
    
    return response
def handle_smalltalk(message, user_name, conversation_history, cart_status=None):
    """Handle casual conversation with the user"""
    response = handle_smalltalk_impl(message, user_name, conversation_history, cart_status)
    log_response(user_name, "smalltalk", message, response)
    return response
    
def handle_view_inventory(message, inventory_json, conversation_history, user_name=None, user_history=None):
    """Handle requests to view available products"""
    response = handle_view_inventory_impl(message, inventory_json, conversation_history, user_name, user_history)
    log_response(user_name, "view_inventory", message, response)
    return response

def handle_add_to_cart(message, cart_json, inventory_json, conversation_history, user_name=None):
    """Handle requests to add products to the cart"""
    response = handle_add_to_cart_impl(message, cart_json, inventory_json, conversation_history, user_name)
    log_response(user_name, "add_to_cart", message, response)
    return response

def handle_remove_from_cart(message, cart_json, conversation_history, user_name=None):
    """Handle requests to remove products from the cart"""
    response = handle_remove_from_cart_impl(message, cart_json, conversation_history, user_name)
    log_response(user_name, "remove_from_cart", message, response)
    return response

def handle_product_info(message, inventory, conversation_history, user_name=None):
    """Handle requests for product information"""
    response = handle_product_info_impl(message, inventory, conversation_history, user_name)
    log_response(user_name, "product_info", message, response)
    return response

def handle_view_cart(message, cart_json, conversation_history, user_name=None):
    """Handle requests to view the cart contents"""
    response = handle_view_cart_impl(message, cart_json, conversation_history, user_name)
    log_response(user_name, "view_cart", message, response)
    return response

def handle_NOT_SURE(message, cart_json, inventory, conversation_history, user_name=None):
    """Handle ambiguous user intents"""
    response = handle_NOT_SURE_impl(message, cart_json, inventory, conversation_history, user_name)
    log_response(user_name, "not_sure", message, response)
    return response

def handle_confirm_order(message, cart_json, conversation_history, user_name=None, user_address=None, payment_methods=None):
    """Handle order confirmation requests with structured flow"""
    response = handle_confirm_order_impl(message, cart_json, conversation_history, user_name, user_address, payment_methods)
    # Try to get checkout stage for more detailed logging
    try:
        data = json.loads(response)
        stage = data.get("checkout_stage", "unknown")
        log_response(user_name, f"confirm_order_{stage}", message, response)
    except:
        log_response(user_name, "confirm_order", message, response)
    return response

def handle_confirm_action(message, conversation_history, previous_action=None, user_name=None):
    """Handle confirmation of previous actions"""
    response = handle_confirm_action_impl(message, conversation_history, previous_action, user_name)
    # Try to log action type
    try:
        data = json.loads(response)
        action_type = data.get("action_type", "unknown")
        confirmed = data.get("confirmed", False)
        log_response(user_name, f"confirm_action_{action_type}_{confirmed}", message, response)
    except:
        log_response(user_name, "confirm_action", message, response)
    return response

def handle_track_order(message, conversation_history, order_history=None, user_name=None):
    """Handle requests to track order status"""
    response = handle_track_order_impl(message, conversation_history, order_history, user_name)
    log_response(user_name, "track_order", message, response)
    return response