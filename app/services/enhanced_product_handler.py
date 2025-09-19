"""
Enhanced Product Search Handler using Multi-Layer Retrieval
Replaces the existing product search system with intelligent multi-layer approach
"""

import json
import logging
from typing import List, Dict, Any, Optional
from .llm_core import safe_api_call, prepare_messages
from .multilayer_retrieval import search_products_multilayer

logger = logging.getLogger(__name__)

def handle_product_search_enhanced(user_id: str,
                                   message: str,
                                   conversation_history: List[Dict],
                                   user_name: str = None) -> str:
    """
    Enhanced product search handler using multi-layer retrieval system
    
    This function:
    1. Uses conversation context to understand user preferences
    2. Detects if query is general (show categories) or specific (show products)
    3. Applies user memory and preferences automatically
    4. Returns appropriate results without overwhelming the LLM
    """
    
    try:
        # Validate input - check if message is an error JSON string
        if message and (message.startswith('{"error"') or '"reply"' in message):
            logger.warning(f"Detected error JSON as search query: {message[:100]}...")
            return _create_error_response("product search", user_name, "Invalid search query")
        
        # Step 1: Use multi-layer retrieval to get intelligent results
        retrieval_result = search_products_multilayer(
            user_id=user_id,
            message=message,
            conversation_history=conversation_history,
            user_name=user_name
        )        # Step 2: Handle different result types
        if retrieval_result['type'] == 'category_overview':
            return _handle_category_overview(retrieval_result, message, conversation_history, user_name)
        
        elif retrieval_result['type'] == 'direct_results':
            return _handle_direct_results(retrieval_result, message, conversation_history, user_name)
        
        elif retrieval_result['type'] == 'clustered_results':
            return _handle_clustered_results(retrieval_result, message, conversation_history, user_name)
        
        elif retrieval_result['type'] == 'no_results':
            return _handle_no_results(retrieval_result, message, conversation_history, user_name)
        
        elif retrieval_result['type'] == 'error':
            return _handle_error(retrieval_result, message, conversation_history, user_name)
        
        else:
            # Fallback to direct results
            return _handle_direct_results(retrieval_result, message, conversation_history, user_name)
            
    except Exception as e:
        logger.error(f"Error in enhanced product search: {e}")
        return _create_error_response(message, user_name, str(e))

def _handle_category_overview(retrieval_result: Dict[str, Any],
                             message: str,
                             conversation_history: List[Dict],
                             user_name: str) -> str:
    """Handle general queries by showing category summaries"""
    
    categories = retrieval_result.get('categories', [])
    user_profile = retrieval_result.get('user_profile', {})
    
    # Create focused data for LLM - categories with summaries, not individual products
    category_summaries = []
    for category in categories:
        summary = {
            'category_id': category['category_id'],
            'category_name': category['category_name'],
            'description': category['description'],
            'product_count': category['product_count'],
            'price_range': category['price_range'],
            'available_colors': category['available_colors'][:5],  # Limit for LLM
            'available_materials': category['available_materials'][:3],
            'matches_preferences': category['matches_user_preferences'],
            'sample_product_names': [p.get('title', 'Unnamed') for p in category['sample_products'][:2]]
        }
        category_summaries.append(summary)
    
    # Prepare context for LLM
    focused_data = {
        'categories': category_summaries,
        'user_preferences': {
            'budget': user_profile.get('budget_range'),
            'preferred_colors': user_profile.get('preferred_colors', []),
            'preferred_styles': user_profile.get('preferred_styles', [])
        },
        'total_categories': len(category_summaries)
    }
    
    system_prompt = f"""
    You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store, specializing in Pakistani footwear.
    
    The user made a general query: "{message}"
    
    Instead of showing individual products, you should present category summaries to help them narrow down their search.
    
    Available categories with summaries:
    {json.dumps(focused_data, indent=2)}
    
    Respond with a JSON object containing:
    
    1. "reply": A brief, conversational response that:
       - Acknowledges their general request
       - Presents 2-3 most relevant categories as options
       - Mentions key features of each category (price range, colors, styles)
       - Asks them to choose a category or be more specific
       - Incorporates their preferences if any were detected
       - Keeps it conversational and WhatsApp-friendly
    
    2. "show_categories": true (to trigger category display)
    
    3. "category_details": Array of 2-3 most relevant categories, each with:
       - "category_id": The category ID
       - "reply": A brief description focusing on what makes this category appealing
    
    4. "suggested_action": "choose_category" or "be_more_specific"
    
    Guidelines:
    - Don't overwhelm with all categories, show only the most relevant 2-3
    - If user has preferences, highlight categories that match
    - Keep descriptions brief but appealing
    - Encourage interaction to narrow down the search
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    response = safe_api_call(messages)
    
    try:
        # Validate and enhance the response
        response_data = json.loads(response) if isinstance(response, str) else response
        
        # Ensure we have the required fields
        if 'show_categories' not in response_data:
            response_data['show_categories'] = True
        
        if 'category_details' not in response_data and categories:
            # Create fallback category details
            response_data['category_details'] = [
                {
                    'category_id': cat['category_id'],
                    'reply': f"{cat['category_name']} - {cat['description']}"
                }
                for cat in categories[:3]
            ]
        
        return json.dumps(response_data)
        
    except (json.JSONDecodeError, TypeError):
        return _create_fallback_category_response(categories, message, user_name)

def _handle_direct_results(retrieval_result: Dict[str, Any],
                          message: str,
                          conversation_history: List[Dict],
                          user_name: str) -> str:
    """Handle specific queries with direct product results"""
    
    products = retrieval_result.get('products', [])
    user_profile = retrieval_result.get('user_profile', {})
    refined_query = retrieval_result.get('refined_query', message)
    
    if not products:
        return _handle_no_results(retrieval_result, message, conversation_history, user_name)
    
    # Prepare focused product data for LLM (limit to prevent overwhelming)
    focused_products = []
    for product in products[:10]:  # Limit to 10 products max for LLM
        focused_product = {
            'id': product.get('id'),
            'title': product.get('title'),
            'description': product.get('description', '')[:200],  # Truncate long descriptions
            'price': product.get('sale_price') or product.get('regular_price') or product.get('price'),
            'colors': product.get('colors', [])[:5],  # Limit colors
            'sizes': product.get('sizes', [])[:8],  # Limit sizes
            'material': product.get('material'),
            'category': product.get('categories', {}).get('name'),
            'is_on_sale': product.get('is_on_sale', False),
            'available_sizes': product.get('available_sizes', [])
        }
        focused_products.append(focused_product)
    
    system_prompt = f"""
    You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store.
    
    The user searched for: "{message}"
    Refined query based on context: "{refined_query}"
    
    Found {len(products)} relevant products. Here are the top matches:
    {json.dumps(focused_products, indent=2)}
    
    User preferences from conversation:
    - Budget: {user_profile.get('budget_range')}
    - Preferred colors: {user_profile.get('preferred_colors', [])}
    - Preferred styles: {user_profile.get('preferred_styles', [])}
    
    Respond with a JSON object containing:
    
    1. "products": Array of 1-3 most relevant product IDs that EXACTLY match the user's criteria
    
    2. "attribute_query": The main aspect user is asking about:
       - "availability" - checking if products exist
       - "comparison" - comparing multiple products  
       - "details" - wanting specific product information
       - "sizing" - asking about sizes or fit
       - "pricing" - asking about cost or deals
    
    3. "reply": A response that:
       - Confirms we found products matching their criteria
       - Highlights key features of the recommended products
       - Mentions prices, colors, materials as relevant
       - Uses their name naturally (not every time)
       - Incorporates their preferences if detected
       - Asks if they want to see details or add to cart
       - Keeps it conversational for WhatsApp
    
    4. "show_images": true (to display product images)
    
    5. "total_found": Total number of products found
    
    Guidelines:
    - Only recommend products that truly match the user's request
    - If user specified color/material/style, only show matching products
    - Mention why these products are good matches
    - Be helpful but not overwhelming
    - Focus on quality over quantity
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    response = safe_api_call(messages)
    
    try:
        response_data = json.loads(response) if isinstance(response, str) else response
        
        # Validate the response
        if 'products' not in response_data:
            response_data['products'] = [p['id'] for p in focused_products[:3]]
        
        if 'show_images' not in response_data:
            response_data['show_images'] = True
            
        if 'total_found' not in response_data:
            response_data['total_found'] = len(products)
        
        return json.dumps(response_data)
        
    except (json.JSONDecodeError, TypeError):
        return _create_fallback_product_response(focused_products, message, user_name)

def _handle_clustered_results(retrieval_result: Dict[str, Any],
                             message: str,
                             conversation_history: List[Dict],
                             user_name: str) -> str:
    """Handle queries that returned too many results - show clusters"""
    
    clusters = retrieval_result.get('clusters', [])
    total_products = retrieval_result.get('total_products', 0)
    refined_query = retrieval_result.get('refined_query', message)
    
    # Prepare cluster summaries for LLM
    cluster_summaries = []
    for cluster in clusters[:4]:  # Limit to 4 clusters
        cluster_summary = {
            'cluster_name': cluster['cluster_name'],
            'category': cluster['category'],
            'price_range': cluster['price_range'],
            'product_count': cluster['product_count'],
            'representative_product': {
                'title': cluster['representative_product'].get('title'),
                'price': cluster['representative_product'].get('sale_price') or cluster['representative_product'].get('regular_price')
            },
            'sample_products': [p.get('title') for p in cluster['products'][:3]]
        }
        cluster_summaries.append(cluster_summary)
    
    system_prompt = f"""
    You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store.
    
    The user searched for: "{message}"
    We found {total_products} products, which is quite a lot! 
    
    Here are the main categories of products we found:
    {json.dumps(cluster_summaries, indent=2)}
    
    Respond with a JSON object containing:
    
    1. "reply": A response that:
       - Acknowledges we found many options
       - Presents the main categories/clusters as choices
       - Suggests they can be more specific or choose a category
       - Keeps it friendly and helpful
       - Uses their name occasionally
    
    2. "show_categories": true
    
    3. "category_details": Array of cluster summaries, each with:
       - "category_id": Use cluster name as ID
       - "reply": Brief description of this cluster/category
    
    4. "suggested_action": "refine_search"
    
    5. "total_found": {total_products}
    
    Guidelines:
    - Help them narrow down from many options
    - Don't overwhelm with all products at once
    - Encourage more specific search or category selection
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    response = safe_api_call(messages)
    
    try:
        response_data = json.loads(response) if isinstance(response, str) else response
        
        # Ensure required fields
        if 'show_categories' not in response_data:
            response_data['show_categories'] = True
            
        if 'category_details' not in response_data:
            response_data['category_details'] = [
                {
                    'category_id': cluster['cluster_name'],
                    'reply': f"{cluster['cluster_name']} - {cluster['product_count']} products available"
                }
                for cluster in clusters[:3]
            ]
            
        response_data['total_found'] = total_products
        
        return json.dumps(response_data)
        
    except (json.JSONDecodeError, TypeError):
        return _create_fallback_cluster_response(clusters, message, user_name, total_products)

def _handle_no_results(retrieval_result: Dict[str, Any],
                      message: str,
                      conversation_history: List[Dict],
                      user_name: str) -> str:
    """Handle cases where no products were found"""
    
    suggestion = retrieval_result.get('suggestion', 'Try browsing our categories')
    user_profile = retrieval_result.get('user_profile', {})
    
    # Create helpful response
    response_data = {
        'products': [],
        'attribute_query': 'availability',
        'reply': f"Sorry {user_name}, I couldn't find any products that exactly match '{message}'. {suggestion}. Would you like to browse our categories or try different keywords?",
        'show_images': False,
        'suggested_action': 'browse_categories',
        'total_found': 0
    }
    
    return json.dumps(response_data)

def _handle_error(retrieval_result: Dict[str, Any],
                 message: str,
                 conversation_history: List[Dict],
                 user_name: str) -> str:
    """Handle error cases"""
    
    error_message = retrieval_result.get('message', 'An error occurred')
    
    response_data = {
        'products': [],
        'attribute_query': 'error',
        'reply': f"Sorry {user_name}, I'm having trouble processing your request right now. Please try again or browse our categories.",
        'show_images': False,
        'suggested_action': 'try_again',
        'total_found': 0
    }
    
    return json.dumps(response_data)

def _create_error_response(message: str, user_name: str, error_details: str) -> str:
    """Create standardized error response"""
    
    response_data = {
        'products': [],
        'attribute_query': 'error',
        'reply': f"Sorry {user_name}, I'm experiencing some technical difficulties. Please try again in a moment.",
        'show_images': False,
        'suggested_action': 'try_again',
        'total_found': 0
    }
    
    logger.error(f"Product search error for query '{message}': {error_details}")
    return json.dumps(response_data)

def _create_fallback_category_response(categories: List[Dict], message: str, user_name: str) -> str:
    """Create fallback response for category overview"""
    
    category_details = []
    for cat in categories[:3]:
        category_details.append({
            'category_id': cat['category_id'],
            'reply': f"{cat['category_name']} - {cat.get('description', 'Various styles available')}"
        })
    
    response_data = {
        'reply': f"Hi {user_name}! I found several categories that might interest you. Which type are you looking for?",
        'show_categories': True,
        'category_details': category_details,
        'suggested_action': 'choose_category'
    }
    
    return json.dumps(response_data)

def _create_fallback_product_response(products: List[Dict], message: str, user_name: str) -> str:
    """Create fallback response for direct products"""
    
    product_ids = [p['id'] for p in products[:3]]
    
    response_data = {
        'products': product_ids,
        'attribute_query': 'availability',
        'reply': f"Hi {user_name}! I found some great options for you. Here are the products that match your search.",
        'show_images': True,
        'total_found': len(products)
    }
    
    return json.dumps(response_data)

def _create_fallback_cluster_response(clusters: List[Dict], message: str, user_name: str, total_products: int) -> str:
    """Create fallback response for clustered results"""
    
    category_details = []
    for cluster in clusters[:3]:
        category_details.append({
            'category_id': cluster['cluster_name'],
            'reply': f"{cluster['cluster_name']} - {cluster['product_count']} products"
        })
    
    response_data = {
        'reply': f"Hi {user_name}! I found {total_products} products. Here are the main categories to help you choose:",
        'show_categories': True,
        'category_details': category_details,
        'suggested_action': 'refine_search',
        'total_found': total_products
    }
    
    return json.dumps(response_data)
