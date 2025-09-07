"""
Checkout and customer service LLM functions for WhatsApp e-commerce chatbot
Contains handlers for order processing, smalltalk, and tracking
"""

import json
from typing import List, Dict, Any
from datetime import datetime
from .llm_core import safe_api_call, prepare_messages

def determine_checkout_stage(conversation_history):
    """
    Analyze conversation history to determine the current checkout stage
    
    Stages:
    1. initial - First-time confirmation of checkout
    2. payment_method - Asking for payment method
    3. payment_details - Asking for specific payment details
    4. phone_number - Asking for contact number
    5. address - Asking for delivery address
    6. final_confirmation - Final order confirmation
    7. completed - Order completed
    """
    if not conversation_history or len(conversation_history) == 0:
        return "initial"
    
    # First, check for explicit stage information in JSON responses
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            content = msg["content"]
            try:
                data = json.loads(content)
                if "checkout_stage" in data:
                    return data["checkout_stage"]
            except:
                pass
    
    # Default to initial if no stage is found
    return "initial"

def extract_information_from_history(conversation_history):
    """
    Extract payment method, payment details, phone number, and address from conversation history
    
    Returns:
        dict: Dictionary containing extracted information
    """
    extracted_info = {
        "payment_method": "unknown",
        "payment_details": "unknown",
        "phone_number": "unknown",
        "delivery_address": "unknown",
        "confirmed": False
    }
    
    # Look through assistant responses first to find confirmed information
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            try:
                data = json.loads(msg["content"])
                # Extract confirmed information from assistant responses
                if "payment_method" in data and data["payment_method"] not in ["unknown", ""]:
                    extracted_info["payment_method"] = data["payment_method"]
                
                if "payment_details" in data and data["payment_details"] not in ["unknown", ""]:
                    extracted_info["payment_details"] = data["payment_details"]
                
                if "phone_number" in data and data["phone_number"] not in ["unknown", ""]:
                    extracted_info["phone_number"] = data["phone_number"]
                
                if "delivery_address" in data and data["delivery_address"] not in ["unknown", ""]:
                    extracted_info["delivery_address"] = data["delivery_address"]
                
                # Check if order was already confirmed
                if "checkout_stage" in data:
                    if data["checkout_stage"] in ["final_confirmation", "completed"]:
                        extracted_info["confirmed"] = True
            except:
                pass
    
    return extracted_info

def handle_smalltalk_impl(message, user_name, conversation_history, cart_status=None):
    """Implementation of smalltalk handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a friendly WhatsApp shopping assistant for a Pakistani clothing store.

        You've determined the user's intent is casual conversation (smalltalk).

        User name: {user_name}
        Cart status: {cart_status}

        Respond with a JSON object that contains:
        1. "reply": A friendly response that:
           - Maintains a warm, helpful tone
           - Responds appropriately to greetings, questions, or casual conversation
           - Only use the user's name occasionally and naturally, not in every message
           - Responds in the same language as the user's message
           - Gently steers the conversation back to shopping when appropriate
           - If the cart has items, subtly remind the user about them
           - Is conversational and natural, similar to how a real person would text on WhatsApp
           - REQUIRED FIELD, must be present in the JSON response
           
        2. "suggested_action": (Optional) A suggested next action for the user, such as:
           - "view_products": If the user seems interested in shopping
           - "view_cart": If the user has items in their cart
           - "continue_chat": If no specific shopping action is appropriate
        
        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)

def handle_confirm_order_impl(message, cart_json, conversation_history, user_name=None, user_address=None, payment_methods=None):
    """Implementation of order confirmation handling with strictly sequential flow"""
    
    # Analyze conversation history to determine where we are in the checkout flow
    checkout_stage = determine_checkout_stage(conversation_history)
    
    # Extract any information that may have been collected already
    extracted_info = extract_information_from_history(conversation_history)
    
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.

        You've determined the user wants to confirm their order (confirm_order intent).

        User name: {user_name}
        User's current cart: {cart_json}
        User's saved address: {user_address if user_address else "None"}
        User's payment methods: {payment_methods if payment_methods else "None"}
        Current checkout stage: {checkout_stage}
        
        Previously collected information:
        - Payment method: {extracted_info['payment_method']}
        - Payment details: {extracted_info['payment_details']}
        - Phone number: {extracted_info['phone_number']}
        - Delivery address: {extracted_info['delivery_address']}

        IMPORTANT - Order Confirmation Flow:
        The order confirmation MUST follow this EXACT sequence with STRICT ADHERENCE:
        1. initial - Ask if user wants to proceed with checkout
        2. payment_method - Ask for preferred payment method (COD, card, etc.)
        3. payment_details - For card payments, ask for card details; for other methods, confirm method
        4. phone_number - Ask for contact phone number
        5. address - Ask for delivery address
        6. final_confirmation - Summarize order and confirm
        7. completed - Inform user that order confirmation email will be sent and session made inactive

        CRITICAL RULES:
        - You MUST process stages IN ORDER - never skip a stage even if information is provided out of sequence
        - NEVER allow the user to skip steps - if they provide information for a future step, acknowledge but stay on current step
        - ONLY advance to the next stage after explicitly confirming the information for the current stage
        - If user provides address when asked for phone number, store it but STILL ASK for phone number
        - If user provides phone number when asked for address, store it but STILL ASK for address
        - ALL steps are mandatory - payment method, payment details (for certain methods), phone number, and address
        - NEVER complete the order unless ALL required information has been collected in the correct sequence

        Respond with a JSON object that contains:
        1. "checkout_stage": Current stage in the checkout process
           - Use exactly one of: "initial", "payment_method", "payment_details", "phone_number", "address", "final_confirmation", "completed"
           - This MUST reflect the current stage based on the conversation flow
           - REQUIRED FIELD
           
        2. "payment_method": Extract payment method if mentioned (COD, card, etc.)
           - Set to previous value if already collected
           - Set to "unknown" if not yet collected
           - REQUIRED FIELD
           
        3. "payment_details": For card payments, include any card details provided
           - Set to "not_required" for cash on delivery or other methods that don't need additional details
           - Set to previous value if already collected
           - Set to "unknown" if needed but not yet collected
           - REQUIRED FIELD
           
        4. "phone_number": Extract phone number if mentioned
           - Set to previous value if already collected
           - Set to "unknown" if not yet collected
           - REQUIRED FIELD
        
        5. "delivery_address": Extract delivery address if mentioned
           - Set to previous value if already collected
           - Set to "unknown" if not yet collected
           - REQUIRED FIELD
        
        6. "NEED": Array of information that is REQUIRED for the CURRENT stage:
           - For "payment_method" stage: ["payment_method"] if not provided
           - For "payment_details" stage: ["payment_details"] if needed and not provided
           - For "phone_number" stage: ["phone_number"] if not provided
           - For "address" stage: ["address"] if not provided
           - For "final_confirmation" stage: ["confirmation"] if not confirmed
           - Empty array only if the required information for the CURRENT stage is provided
           - REQUIRED FIELD
        
        7. "reply": A response that:
           - FOCUSES EXCLUSIVELY on the CURRENT stage of the checkout process
           - Asks ONLY for the specific information needed at the CURRENT stage
           - Acknowledges any information provided for future stages but does not advance to them
           - Is natural and conversational like a typical WhatsApp message
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        8. "order_summary": Brief summary of the order (items, total cost)
           - More detailed during final confirmation stage
           - REQUIRED FIELD
        
        Notes:
        - If cart is empty, indicate this and suggest browsing products
        - IMPORTANT: Never skip steps in the process, even if the user provides information out of sequence
        - At the final confirmation stage, provide a complete summary of the order
        - At the completed stage, tell the user an email with order details will be sent

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    response = safe_api_call(messages)
    
    # Post-process response to ensure it adheres to the correct sequence
    try:
        data = json.loads(response)
        current_stage = data.get("checkout_stage")
        
        # Enforce proper stage progression
        if current_stage == "initial" and checkout_stage == "initial":
            pass  # This is correct - initial stage
        elif current_stage == "payment_method" and checkout_stage in ["initial", "payment_method"]:
            pass  # This is correct - progressed to payment method or staying at payment method
        elif current_stage == "payment_details" and checkout_stage in ["payment_method", "payment_details"]:
            pass  # This is correct - progressed to payment details or staying at payment details
        elif current_stage == "phone_number" and checkout_stage in ["payment_details", "phone_number"]:
            pass  # This is correct - progressed to phone number or staying at phone number
        elif current_stage == "address" and checkout_stage in ["phone_number", "address"]:
            pass  # This is correct - progressed to address or staying at address
        elif current_stage == "final_confirmation" and checkout_stage in ["address", "final_confirmation"]:
            pass  # This is correct - progressed to final confirmation or staying at final confirmation
        elif current_stage == "completed" and checkout_stage in ["final_confirmation", "completed"]:
            pass  # This is correct - progressed to completed or staying at completed
        else:
            # Stage progression is incorrect - revert to correct stage
            data["checkout_stage"] = checkout_stage
            if "reply" in data:
                data["reply"] += " (I need to process your order step by step. Let's continue with the current step.)"
            
            # Update response
            response = json.dumps(data)
    except:
        pass  # If we can't parse the JSON, return the original response
    
    return response

def handle_confirm_action_impl(message, conversation_history, previous_action=None, user_name=None):
    """Implementation of action confirmation handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.

        You've determined the user is confirming a previous action (confirm_action intent).

        User name: {user_name}
        Previous action suggested: {previous_action if previous_action else "Unknown"}

        Respond with a JSON object that contains:
        1. "action_type": Type of action being confirmed:
           - "add_to_cart"
           - "remove_from_cart" 
           - "empty_cart"
           - "confirm_order"
           - "cancel_order"
           - "other" (if none of the above)
           - REQUIRED FIELD
           
        2. "confirmed": Boolean indicating if the user confirmed (true) or denied (false) the action
           - REQUIRED FIELD
        
        3. "reply": A response that:
           - Acknowledges their confirmation or denial
           - Describes what will happen next
           - Is natural and conversational like a real WhatsApp message
           - Only use the user's name occasionally and naturally, not in every message
           - Uses the same language as the user's message
           - If confirming checkout, begins the checkout process flow
           - REQUIRED FIELD
        
        4. "next_step": Suggested next step in the conversation:
           - "proceed" (execute the confirmed action)
           - "clarify" (get more information)
           - "cancel" (abort the action)
           - "suggest_alternatives" (offer other options)
           - REQUIRED FIELD
        
        Notes:
        - Look for affirming words like "yes," "ok," "sure," "proceed"
        - Look for negating words like "no," "cancel," "stop," "don't"
        - Consider the context of the previous message in the conversation
        - If the confirmation is ambiguous, lean toward safety (asking for clarification)
        - If confirming checkout, transition to the order confirmation flow

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)

def handle_track_order_impl(message, conversation_history, order_history=None, user_name=None):
    """Implementation of order tracking handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.

        You've determined the user wants to track their order status (track_order intent).

        User name: {user_name}
        User's order history: {order_history if order_history else "No recent orders"}

        Respond with a JSON object that contains:
        1. "order_id": Extract order ID if mentioned by user
           - If no specific order mentioned but recent orders exist, set to "recent"
           - If no orders exist, set to null
           - REQUIRED FIELD
           
        2. "NEED": If order ID is required but missing, set to "order_id", otherwise null
           - REQUIRED FIELD
        
        3. "reply": A response that:
           - Provides tracking information if available
           - Asks for order ID if NEED is "order_id"
           - Informs if no orders exist
           - Is natural and conversational like a typical WhatsApp message
           - Only use the user's name occasionally and naturally, not in every message
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        4. "order_details": If a specific order is identified, include relevant details:
           - Status (processing, shipped, delivered, etc.)
           - Estimated delivery date
           - Tracking number if available
           - Last update timestamp
        
        Notes:
        - If multiple recent orders exist, ask which one they want to track
        - Handle cases where the order may not exist or be found
        - Format dates in a user-friendly way
        - Respond in the same language as the user's message

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)

def finalize_checkout_order(user_id: str, cart_items: List[Dict], order_details: Dict[str, str]) -> Dict[str, Any]:
    """
    Finalize the checkout process by creating an order and updating inventory
    
    Args:
        user_id: User ID placing the order
        cart_items: List of cart items
        order_details: Dictionary containing payment_method, payment_details, phone_number, delivery_address
        
    Returns:
        Dict with order creation results
    """
    try:
        # Import Supabase client
        from .db_inventory import get_supabase_client, finalize_purchase
        import uuid
        
        supabase = get_supabase_client()
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Calculate total
        total_amount = sum(item.get('price', 0) * item.get('quantity', 0) for item in cart_items)
        
        # Create order record
        order_data = {
            'id': order_id,
            'user_id': user_id,
            'total_amount': total_amount,
            'status': 'confirmed',
            'payment_method': order_details.get('payment_method', 'unknown'),
            'payment_details': order_details.get('payment_details', 'unknown'),
            'phone_number': order_details.get('phone_number', 'unknown'),
            'delivery_address': order_details.get('delivery_address', 'unknown'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Insert order
        order_response = supabase.table('orders').insert(order_data).execute()
        
        if not order_response.data:
            return {
                'status': 'error',
                'error': 'Failed to create order'
            }
        
        # Create order items
        order_items = []
        for item in cart_items:
            order_item = {
                'order_id': order_id,
                'product_id': item.get('id'),
                'product_name': item.get('name'),
                'quantity': item.get('quantity', 0),
                'unit_price': item.get('price', 0),
                'total_price': item.get('price', 0) * item.get('quantity', 0)
            }
            order_items.append(order_item)
        
        # Insert order items
        supabase.table('order_items').insert(order_items).execute()
        
        # Finalize purchase (reduce stock and clear reservations)
        finalize_result = finalize_purchase(user_id, cart_items)
        
        if finalize_result['status'] != 'success':
            # If stock finalization fails, we might want to handle this
            # For now, we'll log it but continue
            print(f"Warning: Stock finalization had issues: {finalize_result.get('error')}")
        
        return {
            'status': 'success',
            'order_id': order_id,
            'total_amount': total_amount,
            'message': 'Order successfully created and inventory updated'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }