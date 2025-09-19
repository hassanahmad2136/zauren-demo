"""
Core utilities for LLM-based WhatsApp e-commerce chatbot
Contains basic API handling and message preparation functions
"""

import os
import json
import time
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

# Function to safely call the API with retries
def safe_api_call(messages, model="llama-3.3-70b-versatile", max_retries=2, retry_delay=1):
    """
    Make an API call to the LLM with retry logic for rate limiting
    
    Args:
        messages (list): List of message objects to send to the API
        model (str): Model identifier
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Initial delay between retries in seconds
        
    Returns:
        str: The model's response
    """
    retries = 0
    while retries < max_retries:
        try:
            # Validate messages before sending
            if not messages or not isinstance(messages, list):
                print(f"Invalid messages format: {messages}")
                return json.dumps({
                    "error": "Invalid request format",
                    "reply": "Sorry, I'm having trouble understanding your request. Please try again."
                })
            
            # Check for overly long messages
            total_length = sum(len(str(msg.get('content', ''))) for msg in messages)
            if total_length > 50000:  # Reasonable limit
                print(f"Message too long: {total_length} characters")
                return json.dumps({
                    "error": "Message too long",
                    "reply": "Sorry, your request is too long. Please try with shorter text."
                })
            
            # Ensure the word "json" appears in the messages for json_object response format
            has_json_word = any("json" in str(msg.get('content', '')).lower() for msg in messages)
            if not has_json_word:
                # Add json instruction to the last message if it's a system message
                if messages and messages[-1].get('role') == 'system':
                    messages[-1]['content'] += "\n\nRespond with a valid JSON object."
                else:
                    # Add a system message with json instruction
                    messages.append({
                        "role": "system", 
                        "content": "Please respond with a valid JSON object."
                    })
            
            chat_completion = client.chat.completions.create(
                messages=messages,
                model=model,
                response_format={"type": "json_object"}
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            retries += 1
            error_msg = str(e)
            print(f"LLM API Error (attempt {retries}/{max_retries}): {error_msg}")
            
            if "429" in error_msg or "Too Many Requests" in error_msg:
                retry_delay *= 2  # Exponential backoff
                time.sleep(retry_delay)
            elif "400" in error_msg:
                print(f"400 Bad Request details: {error_msg}")
                # For 400 errors, don't retry - fix the request
                return json.dumps({
                    "error": "Sorry, I'm having trouble understanding your request. Please try rephrasing.",
                    "reply": "Sorry, I'm having trouble understanding your request. Please try rephrasing."
                })
            elif retries < max_retries:
                time.sleep(retry_delay)
            else:
                return json.dumps({
                    "error": "Sorry, I'm having trouble connecting. Please try again in a moment.",
                    "reply": "Sorry, I'm having trouble connecting. Please try again in a moment."
                })

def prepare_messages(system_prompt, message, conversation_history):
    """
    Helper function to prepare messages for the API call
    
    Args:
        system_prompt (str): The system prompt
        message (str): The current user message
        conversation_history (list): Previous conversation
        
    Returns:
        list: Prepared messages for the API call
    """
    # Create a new array to avoid modifying the original
    messages = []
    
    # Add the system prompt
    messages.append({"role": "system", "content": system_prompt})
    
    # Add relevant conversation history (up to 5 recent exchanges)
    if conversation_history and len(conversation_history) > 0:
        # Get the last 5 exchanges (10 messages maximum - 5 user, 5 assistant)
        recent_history = conversation_history[-10:]
        for msg in recent_history:
            if msg["role"] in ["user", "assistant"]:
                messages.append(msg)
    
    # Add the current user message if it's not already included
    if not any(msg.get("content") == message and msg.get("role") == "user" for msg in messages):
        messages.append({"role": "user", "content": message})
    
    return messages

def extract_json_field(response, field):
    """
    Helper function to extract a field from a JSON response
    
    Args:
        response (str): JSON response string
        field (str): Field to extract
        
    Returns:
        any: The value of the field or None if not found
    """
    try:
        data = json.loads(response)
        return data.get(field)
    except:
        return None