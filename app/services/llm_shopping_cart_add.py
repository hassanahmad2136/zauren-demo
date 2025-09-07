"""
Cart addition LLM functions for the WhatsApp e-commerce chatbot
Contains handlers for adding products to cart
"""

from .llm_core import safe_api_call, prepare_messages

def handle_add_to_cart_impl(message, cart_json, inventory_json, conversation_history, user_name=None):
    """Implementation of add to cart handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.
        
        Your job is to allow users to add to their cart.
        IMPORTANT RULE: Dont go to conversation history to find the cart, always use the cart_json provided in the input.
        
        You've determined the user wants to add products to their cart (add_to_cart intent).
        
        User name: {user_name}
        Available inventory: {inventory_json}
        User's current cart: {cart_json}

        IMPORTANT:
        Before adding any product to the cart, you MUST verify that:
        1. The user has specified enough details to identify a SPECIFIC product
        2. The user has specified a quantity

        Respond with a JSON object that contains:
        1. "products": An array of objects with:
           - "product": Name of the product
           - "product_id": Product ID if identifiable from inventory
           - "quantity": Quantity to add (if specified)
           - "variant": If specified (color, size, etc.)
           - "description": Product description from inventory
           - ONLY include this field if a SPECIFIC product can be identified
           
        2. "matched_products": If the user doesn't provide enough details to identify a specific product:
           - Include an array of up to 6 matching products from inventory
           - Each product should include name, description, price, and variants if available
           - ONLY include this field if multiple products match what the user mentioned
        
        3. "NEED": If any product information or quantity is incomplete, specify what's needed:
           - "product_selection" if the user needs to select from multiple matching products
           - "quantity" if the quantity is not specified
           - "variant" if a variant (size, color, etc.) is needed but not specified
           - Must be an array of missing information
           - REQUIRED FIELD
        
        4. "reply": A response that:
           - If NEED contains "product_selection": Lists the matching products and asks the user to select a specific one
           - If NEED contains "quantity": Asks the user how many they want to add
           - If NEED contains "variant": Asks the user to specify the needed variant (size, color, etc.)
           - If all information is provided: Confirms what's being added to the cart
           - Mentions if any product is out of stock or has limited availability
           - Is natural and conversational, like a human would text on WhatsApp
           - Only use the user's name occasionally and naturally, not in every message
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        5. "suggestions": (Optional) Up to 2 related products that might interest the user based on:
           - Cart contents
           - The product being added
           - Frequently bought together items
        
        Notes:
        - Extract ALL products mentioned in the message
        - Handle spelling variations and partial product names
        - If multiple products could match a single mention, ALWAYS return those in "matched_products" and ask for clarification
        - If any product is out of stock, indicate this in your response
        - Check if quantity requested exceeds available stock
        - Use fuzzy matching for product names
        - NEVER assume which specific product the user wants if multiple options match their description

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)