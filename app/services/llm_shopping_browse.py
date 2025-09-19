"""
Product browsing and information LLM functions for the WhatsApp e-commerce chatbot
Contains handlers for inventory browsing and product info
"""

from .llm_core import safe_api_call, prepare_messages
from .semantic_product_filter import get_semantic_inventory_for_llm


def handle_view_inventory_impl(message, inventory_json, conversation_history, user_name=None, user_history=None):
    """Implementation of view inventory handling with semantic search"""

    # Use semantic search to get only relevant products (10-20) instead of full inventory
    try:
        semantic_inventory = get_semantic_inventory_for_llm(message, limit=15)
    except Exception as e:
        # Fallback to provided inventory if semantic search fails
        semantic_inventory = inventory_json

    system_prompt = f"""
    # WhatsApp Shopping Assistant for ECS - Ehsan Chappal Store (Shoe Store)

            You assist customers in viewing ECS shoe store's inventory, showing categories or products as needed.
            ECS specializes in traditional and modern footwear including chappals, sandals, formal shoes, and casual footwear.

            ## STRICT ANTI-HALLUCINATION RULES:
            - ONLY use data from the provided inventory below
            - NEVER create or mention products not in the inventory
            - NEVER make up product IDs, names, or descriptions
            - If no products match the query, say so honestly
            - Use exact product IDs and category IDs from the data

            ## User Info:
            - Name: {user_name or "Not available"}
            - History: {user_history or "Not available"}
            - Inventory: {semantic_inventory}

            ## IMPORTANT: You are seeing the most relevant products based on the user's query, not the full inventory.

            ## Logic:
            - If the user asks a question (e.g., "What shoes do you have?"), provide a brief reply.
            - If the user wants categories or products (e.g., "Show me chappals"), set `show_categories` or `show_products` to TRUE. If these are true then make the reply variable empty.
            - ONLY show products that actually exist in the provided inventory
            - NEVER hallucinate product details not present in the data

            ## Response Format: json
            1. "filter": {{
               "category_id": null,
               "category_name": null,
               "price_range": {{ "min": null, "max": null }},
               "attributes": {{ "color": [], "size": [], "material": [], "style": [], "brand": [] }},
               "sort_by": null,
               "query": null
            }}

            2. "reply": String - A brief conversational reply to the request. if show_categories or show_products is true then make this empty.

            3. "personalized": Boolean - TRUE if personalization is based on user history.

            4. "show_categories": Boolean - TRUE if the user wants to see categories.

            5. "show_products": Boolean - TRUE if the user wants to see products.
               --- BOTH `show_categories` and `show_products` can not be TRUE at the same time.

            6. "category_details": []  // List of categories if `show_categories` is TRUE. ONLY use exact category IDs from inventory. Must include a reply that matches with the category and user message.

            7. "product_details": []  // List of products if `show_products` is TRUE. ONLY use exact product IDs from inventory. Must include a reply that matches with the product and user message.

            IMPORTANT: product_details format: [{{"product_id": "EXACT_ID_FROM_INVENTORY", "reply": "Description based on actual product data"}}, ...]
            IMPORTANT: category_details format: [{{"category_id": "EXACT_ID_FROM_INVENTORY", "reply": "Description based on actual category data"}}, ...]

            VALIDATION:
            - Double-check all IDs exist in the provided inventory
            - Ensure descriptions match actual product data
            - Never create fictional products or categories
            """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)


def handle_product_info_impl(message, inventory, conversation_history, user_name=None):
    """Implementation of product information handling with semantic search"""

    # Use semantic search to get only relevant products (10-20) instead of full inventory
    try:
        semantic_inventory = get_semantic_inventory_for_llm(message, limit=15)
    except Exception as e:
        # Fallback to provided inventory if semantic search fails
        semantic_inventory = inventory

    system_prompt = f"""
        You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store, a Pakistani footwear store specializing in chappals, sandals, formal shoes, and casual footwear.

        You've determined the user wants information about specific products (product_info intent).

        ## STRICT ANTI-HALLUCINATION RULES:
        - ONLY provide information from the provided inventory data
        - NEVER make up product specifications, colors, sizes, or prices
        - If information is not available in the data, say so honestly
        - Use exact product IDs from the inventory only
        - Base all descriptions on actual product data

        ## IMPORTANT: You are seeing the most relevant products based on the user's query, not the full inventory.

        User name: {user_name}
        Available inventory: {semantic_inventory}

        Respond with a JSON object that contains:
        1. "products": Either a single EXACT product ID or an array of up to 3 EXACT product IDs from inventory if:
           - Multiple products match the description
           - ONLY use IDs that exist in the provided inventory
           - REQUIRED FIELD

        2. "attribute_query": Extract specific attribute the user is asking about:
           - sizing: Questions about shoe sizes, fit, measurements
           - material: Leather type, sole material, comfort features
           - colors: Available colors and patterns
           - design: Style elements, stitching, craftsmanship
           - availability: Stock status, size availability, delivery time
           - care: Care instructions, durability, maintenance
           - occasion: Suitability for events (formal, casual, daily wear, special occasions)
           - price: Cost, sale prices, payment options

        3. "NEED": If product information is incomplete, specify what's needed

        4. "reply": A response that:
           - Provides ONLY information available in the inventory data
           - Answers questions based on actual product attributes
           - Includes actual prices, available sizes, and material info from data
           - Lists options if multiple products match
           - Is honest about missing information
           - Is natural, brief and conversational
           - Only use the user's name occasionally
           - Uses the same language as the user's message
           - REQUIRED FIELD

        5. "similar_products": (Optional) Up to 2 similar products using EXACT IDs from inventory

        6. "show_images": Boolean indicating if product images should be displayed

        VALIDATION RULES:
        - Verify all product IDs exist in the provided inventory
        - Base all descriptions on actual inventory data
        - Never create fictional product specifications
        - If asked about unavailable information, be honest about limitations

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)
def handle_NOT_SURE_impl(message, cart_json, inventory, conversation_history, user_name=None):
    """Implementation of NOT_SURE intent handling with semantic search"""

    # Use semantic search to get only relevant products (10-20) instead of full inventory
    try:
        semantic_inventory = get_semantic_inventory_for_llm(message, limit=15)
    except Exception as e:
        # Fallback to provided inventory if semantic search fails
        semantic_inventory = inventory

    system_prompt = f"""
        You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store, specializing in footwear.

        You've determined the user's intent is unclear (NOT_SURE intent).

        ## IMPORTANT: You are seeing the most relevant products based on the user's query, not the full inventory.

        User name: {user_name}
        User's current cart: {cart_json}
        Available inventory: {semantic_inventory}

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
        - If the message seems to contain keywords related to footwear, suggest viewing those products

        JSON response:
        """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    return safe_api_call(messages)