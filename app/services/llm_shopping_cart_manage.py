"""
Cart management LLM functions for the WhatsApp e-commerce chatbot
Contains handlers for viewing and removing items from cart
"""

from .llm_core import safe_api_call, prepare_messages

def handle_view_cart_impl(message, cart_json, conversation_history, user_name=None):
    """Implementation of view cart handling"""
    system_prompt = f"""
         PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.
        You've determined the user wants to view their shopping cart (view_cart intent).
        Your job is to show to users what they have in their shopping cart. This is the shopping cart and your response should be based on this:
        {cart_json}
        
        IMPORTANT RULE: Dont go to conversation history to find the cart, always use the cart_json provided in the input.
        IMPORTANT RULE: If the cart is empty, indicate this in your response.
        
        
        Respond with a JSON object that contains:
        1. "reply": A response that:
           - Acknowledges their request to view the cart
           - Mentions the number of items if appropriate
           - Mentions total cost if appropriate
           - Indicates if the cart is empty
           - Is natural and conversational like a typical WhatsApp message
           - Only use the user's name occasionally and naturally, not in every message
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        2. "next_action_prompt": A brief suggestion for what they might want to do next:
           - If cart has items: ask if they want to checkout, continue shopping, or modify cart
           - If cart is empty: suggest browsing products
           - REQUIRED FIELD
        3. products: An array of objects with:
         - product id's of all the products in the cart
        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)

def handle_remove_from_cart_impl(message, cart_json, conversation_history, user_name=None):
    """Implementation of remove from cart handling with improved validation"""
    system_prompt = f"""
    You are a WhatsApp shopping assistant for an e-commerce store.
    Your job is to help users remove products from their shopping cart.
    
    IMPORTANT RULES:
    - Always use the cart_json provided in the input, never go to conversation history for cart data
    - If the cart is empty, indicate this clearly in your response
    - Be precise about product identification and quantities

    User name: {user_name}
    User's current cart: {cart_json}

    VALIDATION REQUIREMENTS:
    Before removing any product, you MUST verify:
    1. The user has specified enough details to identify a SPECIFIC product in their cart
    2. The user has specified a quantity or implied they want to remove all of that product
    3. The product actually exists in their current cart

    Respond with a JSON object containing:

    1. "products": Array of products to remove (ONLY if specific products are identified):
       - "product_name": Exact name of the product as it appears in cart
       - "product_id": Product ID from cart (if available)
       - "quantity_to_remove": Number to remove (use "all" for complete removal)
       - "current_quantity": Current quantity in cart for validation

    2. "matched_products": If user's description matches multiple cart items:
       - Array of matching products with: name, current_quantity, price, product_id
       - Use this when user's description is ambiguous

    3. "NEED": Array of missing information required:
       - "product_selection": User needs to choose from multiple matches
       - "quantity_specification": User needs to specify how many to remove
       - "product_clarification": User's product description doesn't match anything in cart

    4. "reply": Natural WhatsApp-style response that:
       - Lists matching products if selection needed
       - Asks for quantity if not specified
       - Confirms removal if all info provided
       - Explains if product not found in cart
       - Uses user's language and tone
       - Uses user's name occasionally, not in every message

    5. "cart_summary": Brief description of cart state after removal

    SPECIAL CASES:
    - "remove all", "empty cart", "clear cart" → set product_name to "CLEAR_ALL"
    - Product not in cart → explain in reply, set NEED to ["product_clarification"]
    - Ambiguous quantity → ask for clarification, set NEED to ["quantity_specification"]

    Handle typos and variations in product names using fuzzy matching logic.

    JSON response:
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)
 