"""
Cart management LLM functions for the WhatsApp e-commerce chatbot
Contains handlers for viewing and removing items from cart
"""

import json
from .llm_core import safe_api_call, prepare_messages

def handle_view_cart_impl(message, cart_json, conversation_history, user_name=None):
    """Implementation of view cart handling with detailed cart data extraction"""

    # Parse cart to extract real data for LLM processing
    cart_data = {}
    try:
        if cart_json:
            cart_data = json.loads(cart_json) if isinstance(cart_json, str) else cart_json
    except json.JSONDecodeError as e:
        print(f"Error parsing cart JSON: {e}")
        cart_data = {}
    except Exception as e:
        print(f"Unexpected error parsing cart: {e}")
        cart_data = {}

    # Extract cart summary for LLM - matching CartManager's structure
    cart_summary = {
        "items": [],
        "total_items": 0,
        "total_price": 0.0,
        "is_empty": True
    }

    if cart_data and isinstance(cart_data, dict) and len(cart_data) > 0:
        cart_summary["is_empty"] = False

        for cart_key, item in cart_data.items():
            if isinstance(item, dict):
                try:
                    # Extract item details with proper validation
                    product_id = item.get("product_id", "")
                    product_name = item.get("product_name", "Unknown Product")
                    quantity = max(1, int(item.get("quantity", 1)))
                    price = float(item.get("price", 0))
                    color = item.get("color", "")
                    size = item.get("size", "")
                    
                    # Calculate item total
                    item_total = quantity * price
                    
                    # Add to cart summary
                    cart_item = {
                        "cart_key": cart_key,
                        "product_id": product_id,
                        "product_name": product_name,
                        "color": color,
                        "size": size,
                        "quantity": quantity,
                        "price": price,
                        "item_total": round(item_total, 2)
                    }
                    
                    cart_summary["items"].append(cart_item)
                    cart_summary["total_items"] += quantity
                    cart_summary["total_price"] += item_total
                
                except (ValueError, TypeError) as e:
                    print(f"Error processing cart item {cart_key}: {e}")
                    continue
        
        # Round total price to 2 decimal places
        cart_summary["total_price"] = round(cart_summary["total_price"], 2)

    system_prompt = f"""
        You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store.
        You've determined the user wants to view their shopping cart (view_cart intent).

        IMPORTANT RULES:
        - Only use the cart data provided below, never hallucinate cart contents
        - If cart is empty, clearly indicate this
        - Be accurate about quantities, prices, and product details
        - Never make up products that aren't in the cart
        - Show prices in Pakistani Rupees (PKR/Rs.) format
        - Use natural, conversational WhatsApp-style language

        User name: {user_name or 'Customer'}
        Cart data: {cart_summary}

        Respond with a JSON object that contains:
        1. "reply": A response that:
           - If cart is empty: "🛒 Your cart is empty! Browse our amazing footwear collection to find something you like! 👟"
           - If cart has items: 
             * Use emojis to make it engaging (🛒 for cart, 👟 for shoes, etc.)
             * List each item clearly with product name, size, color (if applicable), quantity and price
             * Show individual item totals (quantity × price)
             * Show grand total items count and total price
             * Format: "Product Name - Size: X, Color: Y\\nQty: Z × Rs. XXXX = Rs. YYYY"
           - Is natural and conversational like a typical WhatsApp message
           - Only use the user's name occasionally and naturally
           - Uses the same language as the user's message
           - REQUIRED FIELD

        2. "next_action_prompt": Suggestion for next action:
           - If cart has items: "Ready to checkout, continue shopping, or modify your cart?"
           - If cart is empty: "Browse our footwear collection or ask about specific shoes!"
           - REQUIRED FIELD

        3. "show_cart_interactive": Boolean - true if cart has items and should show interactive message
           - REQUIRED FIELD

        4. "cart_items": If cart has items, array of cart item objects with:
           - cart_key: Unique cart key from CartManager
           - product_id: Product ID from cart
           - product_name: Product name
           - quantity: Quantity in cart
           - size: Size specification
           - color: Color specification (if applicable)
           - price: Unit price
           - item_total: Total for this item (quantity × price)
           - ONLY include if cart has items

        Notes:
        - Be honest about cart contents - never make up items
        - If cart is empty, don't include cart_items field
        - Prices should be exactly as stored in cart
        - Maintain accuracy for all product details
        - Format sizes and colors appropriately for display
        - Keep the tone friendly and helpful

        Example format for cart with items:
        {{
            "reply": "🛒 Your Cart:\\n\\n👟 Nike Air Max - Size: 42, Color: Black\\n   Qty: 2 × Rs. 15,000 = Rs. 30,000\\n\\n👟 Adidas Ultra Boost - Size: 41\\n   Qty: 1 × Rs. 18,000 = Rs. 18,000\\n\\n📊 Total: 3 items - Rs. 48,000\\n\\nReady to checkout? 🛍️",
            "next_action_prompt": "Ready to checkout, continue shopping, or modify your cart?",
            "show_cart_interactive": true,
            "cart_items": [
                {{
                    "cart_key": "nike air max|black|42",
                    "product_id": "uuid-123",
                    "product_name": "Nike Air Max",
                    "quantity": 2,
                    "size": "42",
                    "color": "Black",
                    "price": 15000,
                    "item_total": 30000
                }},
                {{
                    "cart_key": "adidas ultra boost||41",
                    "product_id": "uuid-456",
                    "product_name": "Adidas Ultra Boost",
                    "quantity": 1,
                    "size": "41",
                    "color": "",
                    "price": 18000,
                    "item_total": 18000
                }}
            ]
        }}

        JSON response:
        """

    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)

def handle_remove_from_cart_impl(message, cart_json, conversation_history, user_name=None):
    """Implementation of remove from cart handling with improved validation"""
    
    # Parse cart to extract real data for better validation
    cart_data = {}
    cart_items = []
    try:
        if cart_json:
            cart_data = json.loads(cart_json) if isinstance(cart_json, str) else cart_json
            
            # Convert CartManager format to list for easier processing
            if isinstance(cart_data, dict):
                for cart_key, item in cart_data.items():
                    if isinstance(item, dict):
                        item_with_key = item.copy()
                        item_with_key['cart_key'] = cart_key
                        cart_items.append(item_with_key)
    except json.JSONDecodeError as e:
        print(f"Error parsing cart JSON: {e}")
        cart_data = {}
        cart_items = []
    except Exception as e:
        print(f"Unexpected error parsing cart: {e}")
        cart_data = {}
        cart_items = []

    # Create cart summary for LLM
    cart_summary = {
        "items": cart_items,
        "total_items": len(cart_items),
        "is_empty": len(cart_items) == 0
    }

    # Calculate total quantities and price
    total_quantity = 0
    total_price = 0.0
    for item in cart_items:
        quantity = item.get('quantity', 0)
        price = item.get('price', 0)
        total_quantity += quantity
        total_price += (quantity * price)

    cart_summary['total_quantity'] = total_quantity
    cart_summary['total_price'] = round(total_price, 2)

    system_prompt = f"""
    You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store.
    Your job is to help users remove products from their shopping cart.
    
    IMPORTANT RULES:
    - Only use the cart data provided below, never hallucinate cart contents
    - If the cart is empty, indicate this clearly in your response
    - Be precise about product identification and quantities
    - Handle product variants (different colors/sizes) as separate items
    - Use natural WhatsApp-style language with emojis
    - Show prices in Pakistani Rupees (PKR/Rs.) format

    User name: {user_name or 'Customer'}
    User's current cart data: {cart_summary}

    VALIDATION REQUIREMENTS:
    Before removing any product, you MUST verify:
    1. The user has specified enough details to identify a SPECIFIC product variant in their cart
    2. The user has specified a quantity or implied they want to remove all of that product
    3. The product variant actually exists in their current cart
    4. Handle cases where multiple variants of same product exist (different colors/sizes)

    Respond with a JSON object containing:

    1. "products": Array of products to remove (ONLY if specific products are identified):
       - "cart_key": The cart key from CartManager (product_name|color|size format)
       - "product_name": Exact name of the product as it appears in cart
       - "product_id": Product ID from cart
       - "color": Color variant (if applicable)
       - "size": Size variant (if applicable)
       - "quantity_to_remove": Number to remove (use "all" for complete removal)
       - "current_quantity": Current quantity in cart for validation
       - "price": Unit price for reference

    2. "matched_products": If user's description matches multiple cart items:
       - Array of matching products with: cart_key, product_name, color, size, current_quantity, price
       - Use this when user's description is ambiguous (e.g., "remove Nike shoes" but multiple Nike variants exist)

    3. "NEED": Array of missing information required:
       - "product_selection": User needs to choose from multiple matches
       - "quantity_specification": User needs to specify how many to remove
       - "product_clarification": User's product description doesn't match anything in cart
       - "variant_selection": User needs to specify color/size when multiple variants exist

    4. "reply": Natural WhatsApp-style response that:
       - If cart is empty: "🛒 Your cart is already empty! Add some shoes to get started! 👟"
       - If multiple variants found: List options with details (name, color, size, quantity)
       - If quantity needed: Ask how many to remove
       - If product not found: Suggest similar products or show what's in cart
       - If removal successful: Confirm what will be removed
       - Uses emojis appropriately (🛒, 👟, ❌, ✅, etc.)
       - Uses user's language and tone
       - Uses user's name occasionally, not in every message
       - Be helpful and conversational

    5. "action_type": One of:
       - "clear_all": Remove all items from cart
       - "remove_specific": Remove specific product variants
       - "need_clarification": Need more information from user
       - "product_not_found": Requested product not in cart

    SPECIAL CASES:
    - "remove all", "empty cart", "clear cart", "delete everything" → set action_type to "clear_all"
    - Product name matches but multiple variants exist → list variants for selection
    - Fuzzy matching for typos (e.g., "addidas" → "adidas")
    - Partial matches (e.g., "nike shoes" when cart has "Nike Air Max")

    EXAMPLES:

    Example 1 - Multiple variants exist:
    User: "Remove Nike shoes"
    Cart has: Nike Air Max (Black, Size 42), Nike Air Max (White, Size 41)
    Response: Ask user to specify which variant

    Example 2 - Specific removal:
    User: "Remove 1 black Nike Air Max size 42"
    Cart has matching item with quantity 2
    Response: Confirm removal of 1 item, 1 will remain

    Example 3 - Complete removal:
    User: "Remove all Adidas shoes"
    Response: Remove all Adidas variants from cart

    Example 4 - Product not found:
    User: "Remove Puma shoes"
    Cart has no Puma products
    Response: Explain product not found, show what's available

    JSON response:
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)