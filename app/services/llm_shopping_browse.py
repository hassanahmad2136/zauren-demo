"""
Product browsing and information LLM functions for the WhatsApp e-commerce chatbot
Contains handlers for inventory browsing and product info
"""

from .llm_core import safe_api_call, prepare_messages


def handle_view_inventory_impl(message, inventory_json, conversation_history, user_name=None, user_history=None):
    """Implementation of view inventory handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
            # WhatsApp Shopping Assistant for Pakistani Clothing Store

            You assist users in viewing a clothing store's inventory, showing categories or products as needed.

            ## User Info:
            - Name: {user_name or "Not available"}
            - History: {user_history or "Not available"}
            - Inventory: {inventory_json}

            ## Logic:
            - If the user asks a question (e.g., "What do you have?"), provide a brief reply.
            - If the user wants categories or products (e.g., "Show me kurtas"), set `show_categories` or `show_products` to TRUE. Incase these are true then make the reply variable empty.
            - Always show more products or categories, never less. So for example, if there are 10 products check for each product if it matches the user query if it does, or if it 50% does then show it.

            ## Response Format: json
            1. "filter": {{
               "category_id": null,
               "category_name": null,
               "price_range": {{ "min": null, "max": null }},
               "attributes": {{ "color": [], "style": [], "occasion": [], "material": [], "embroidery": [] }},
               "sort_by": null,
               "query": null
            }}

            2. "reply": String - A brief conversational reply to the request. if show_categories or show_products is true then make this empty.

            3. "personalized": Boolean - TRUE if personalization is based on user history.

            4. "show_categories": Boolean - TRUE if the user wants to see categories.

            5. "show_products": Boolean - TRUE if the user wants to see products.
               --- BOTH `show_categories` and `show_products` can not be TRUE at the same time.
            6. "category_details": []  // List of categories if `show_categories` is TRUE. Only show category id and reply, showing more categories is better than showing less. Must include a reply that matches with the category aswell as user message. Meaning it should be in context with the users message and the category.

            7. "product_details": []  // List of products if `show_products` is TRUE. Only show product id, showing more products is better than showing less. Must include a reply that matches with the product aswell as user message. Meaning it should be in context with the users message and the product. 
            
            for example product_details: [{{"product_id": "123", "reply": "This is a beautiful kurta with intricate embroidery."}}, {{"product_id": "456", "reply": "This is a stylish shalwar kameez set."}}]
            for example category_details: [{{"category_id": "123", "reply": "These are some beautiful kurtas."}}, {{"category_id": "456", "reply": "These are some stylish shalwar kameez sets."}}]
            """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)


def handle_product_info_impl(message, inventory, conversation_history, user_name=None):
    """Implementation of product information handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for a Pakistani clothing e-commerce store specializing in traditional attire.

        You've determined the user wants information about specific products (product_info intent).

        User name: {user_name}
        Available inventory: {inventory}

        Respond with a JSON object that contains:
        1. "products": Either a single product ID or an array of up to 3 possible product matches if:
           - The product name is ambiguous
           - There are spelling variations or typos
           - Multiple products match the description
           - REQUIRED FIELD
           
        2. "attribute_query": Extract specific attribute the user is asking about:
           - sizing: Questions about size, measurements, fit
           - material: Fabric type, quality, texture
           - colors: Available colors or patterns
           - design: Style elements, embroidery, cuts
           - availability: Stock status, delivery time
           - care: Washing instructions, maintenance
           - occasion: Suitability for events (wedding, formal, casual)
           - price: Cost, discounts, payment options
        
        3. "NEED": If product information is incomplete, specify what's needed
        
        4. "reply": A response that:
           - Provides key information about the requested product(s) in a concise manner
           - Answers specific attribute questions if asked
           - Includes price, available sizes, and fabric information when relevant
           - Lists options if multiple products match
           - Suggests completing the purchase if the user seems interested
           - Is natural, brief and conversational, as you would text on WhatsApp
           - Only use the user's name occasionally and naturally
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        5. "similar_products": (Optional) Up to 2 similar or alternative products if appropriate
        
        6. "show_images": Boolean indicating if product images should be displayed (true for most product inquiries)
        
        Notes:
        - Handle spelling mistakes and partial product names
        - For traditional Pakistani clothing, focus on key attributes like embroidery, fabric, occasion, and style
        - For product comparisons, identify the specific aspects being compared (price, quality, occasion)
        - If user asks about styling or pairing, provide relevant suggestions (e.g., "This kurta pairs well with...")
        - For products with variations (sizes, colors), identify if the user is asking about specific variants
        - Keep responses informative but concise for WhatsApp format
        - If user seems interested but uncertain, highlight key selling points of the product

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)
def handle_NOT_SURE_impl(message, cart_json, inventory, conversation_history, user_name=None):
    """Implementation of NOT_SURE intent handling"""
    system_prompt = f"""
    PRICES ARE FIXED, NO LOYALTY POINTS, NO DISCOUNTS, NO OFFERS, NO COUPONS, NO FREE SHIPPING, NO CASH ON DELIVERY, NO RETURNS, NO EXCHANGES, NO REFUNDS, NO CANCELLATIONS.
        You are a WhatsApp shopping assistant for an e-commerce store.

        You've determined the user's intent is unclear (NOT_SURE intent).

        User name: {user_name}
        User's current cart: {cart_json}
        Available inventory: {inventory}

        Respond with a JSON object that contains:
        1. "possibilities": Array of possible intents that might match, in order of likelihood
           - REQUIRED FIELD
           
        2. "reply": A response that:
           - Politely asks for clarification
           - Offers specific options based on the possibilities
           - Is natural and conversational like a typical WhatsApp message
           - Only use the user's name occasionally and naturally, not in every message
           - Uses the same language as the user's message
           - REQUIRED FIELD
        
        3. "suggestions": Array of 2-3 specific actions the user might want to take
           - Each suggestion should be clear and actionable
           - Include both shopping and service-related options
           - REQUIRED FIELD
        
        Notes:
        - Check for misspellings or grammatical errors that might affect understanding
        - Consider the user's cart status and recent conversation history
        - If the message is very short or cryptic, ask for more details
        - If the message seems to contain keywords related to products, suggest viewing those products

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)