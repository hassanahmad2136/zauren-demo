"""
Optimized product search and information LLM functions for large inventories
Uses hybrid approach: database search + targeted LLM processing
"""

import json
import re
from typing import List, Dict, Any, Optional
from .llm_core import safe_api_call, prepare_messages
from .guardrails_config import validate_llm_response
from .db_inventory import search_products, get_product_details, strict_product_search
from .product_search_enhanced import search_products_enhanced
from .price_manager import get_price_manager


class ProductSearchOptimizer:
    """Optimizes product searches for large inventories"""
    
    def __init__(self):
        self.max_search_results = 15  # Limit initial search results from semantic search
        self.max_llm_products = 10    # Maximum products to send to LLM
    
    def extract_search_terms(self, message: str) -> List[str]:
        """Extract relevant search terms from user message using LLM"""
        system_prompt = """
        Extract the most relevant and SPECIFIC search terms from the user's product inquiry.
        Focus on EXACT requirements:
        - Specific colors (black, white, blue, red, etc.) - be precise about color names
        - Product types (kurta, shalwar, kameez, waistcoat, sherwani, etc.)
        - Materials (cotton, silk, velvet, linen, etc.)
        - Occasions (formal, casual, wedding, party, etc.)
        - Styles (embroidered, plain, textured, etc.)
        
        IMPORTANT: 
        - Extract ONLY the exact terms mentioned by the user
        - Do NOT add related or similar terms
        - If user says "blue", only extract "blue", not "navy" or "light blue"
        - If user says "formal", only extract "formal", not "semi-formal"
        
        Return only a JSON array of 2-4 most important EXACT search terms.
        Example: ["blue", "kurta", "cotton"]
        """
        
        messages = prepare_messages(system_prompt, f"Extract exact search terms from: {message}", [])
        response = safe_api_call(messages)
        
        try:
            terms = json.loads(response)
            return terms if isinstance(terms, list) else []
        except:
            # Fallback: simple exact keyword extraction for ECS chappal store
            keywords = ['chappal', 'khussa', 'sandal', 'shoe', 'slipper', 'peshawari', 'kolhapuri', 'formal', 'casual', 'leather', 'synthetic', 'black', 'white', 'brown', 'tan', 'beige', 'size', 'comfortable', 'wedding', 'office', 'daily', 'traditional', 'modern']
            found_terms = [word for word in keywords if word.lower() in message.lower()]
            return found_terms[:3]
    
    def search_relevant_products(self, search_terms: List[str]) -> List[Dict]:
        """Search database for products using enhanced semantic search"""
        try:
            # Use enhanced search with semantic capabilities
            query = ' '.join(search_terms)
            result = search_products_enhanced(query, limit=self.max_search_results)

            if result.get('status') == 'success' and result.get('data'):
                products = []
                for item in result['data']:
                    # Handle different result structures from enhanced search
                    if 'product' in item:
                        products.append(item['product'])
                    else:
                        products.append(item)
                return products

            # Fallback to traditional search if enhanced search fails
            return self._fallback_search(search_terms)

        except Exception as e:
            print(f"Enhanced search failed, using fallback: {e}")
            return self._fallback_search(search_terms)

    def _fallback_search(self, search_terms: List[str]) -> List[Dict]:
        """Fallback to traditional search methods"""
        # First try strict search for exact matches
        strict_search_result = strict_product_search(search_terms, exact_match=True)
        all_results = []
        seen_ids = set()

        if strict_search_result['status'] == 'success' and strict_search_result['data']:
            for product in strict_search_result['data']:
                if product['id'] not in seen_ids:
                    all_results.append(product)
                    seen_ids.add(product['id'])

                    if len(all_results) >= self.max_search_results:
                        break

        # If we don't have enough results from strict search, try fuzzy search
        if len(all_results) < 5:  # Minimum threshold
            for term in search_terms:
                if len(all_results) >= self.max_search_results:
                    break

                search_result = search_products(term)
                if search_result['status'] == 'success' and search_result['data']:
                    for product in search_result['data']:
                        if product['id'] not in seen_ids:
                            all_results.append(product)
                            seen_ids.add(product['id'])

                            if len(all_results) >= self.max_search_results:
                                break

        return all_results
    
    def create_focused_inventory(self, products: List[Dict]) -> str:
        """Create a focused inventory JSON with only relevant products"""
        focused_products = []
        
        for product in products[:self.max_llm_products]:
            # Get price manager for effective pricing
            price_manager = get_price_manager()
            effective_price = price_manager.get_effective_price(product)

            focused_product = {
                "id": product.get("id"),
                "product_id": product.get("product_id"),
                "name": product.get("title") or product.get("name"),
                "description": product.get("description"),
                "price": product.get("price"),
                "regular_price": product.get("regular_price"),
                "sale_price": product.get("sale_price"),
                "effective_price": effective_price,
                "discount_percentage": product.get("discount_percentage"),
                "is_on_sale": product.get("is_on_sale", False),
                "sku": product.get("sku"),
                "quantity": product.get("quantity", 0),
                "category": product.get("categories", {}).get("name") if product.get("categories") else None,
                "material": product.get("material"),
                "colors": product.get("colors", []),
                "sizes": product.get("sizes", []),
                "available_sizes": product.get("available_sizes", []),
                "out_of_stock_sizes": product.get("out_of_stock_sizes", []),
                "size_availability": product.get("size_availability", {}),
                "style": product.get("style"),
                "brand": product.get("brand"),
                "images": product.get("images", []),
                "image_count": product.get("image_count", 0),
                "url": product.get("url"),
                "product_sections": product.get("product_sections", {}),
                "other_options": product.get("other_options", [])
            }
            focused_products.append(focused_product)
        
        return json.dumps({"products": focused_products}, ensure_ascii=False)


def handle_product_info_optimized(message: str, conversation_history: List[Dict], user_name: str = None) -> str:
    """
    Optimized product info handler for large inventories
    
    Process:
    1. Extract search terms from user message using LLM
    2. Search database for relevant products (limited results)
    3. Send only relevant products to LLM for detailed analysis
    4. Return structured response
    """
    
    optimizer = ProductSearchOptimizer()
    
    # Step 1: Extract search terms from message
    search_terms = optimizer.extract_search_terms(message)
    
    if not search_terms:
        # Fallback if no terms extracted
        return json.dumps({
            "products": [],
            "attribute_query": "clarification",
            "NEED": "search_terms",
            "reply": f"Hi {user_name}, could you please be more specific about what footwear you're looking for? For example, mention the type (chappal, khussa, sandal, formal shoes), color, size, or style from ECS Ehsan Chappal Store.",
            "similar_products": [],
            "show_images": False
        })
    
    # Step 2: Search database for relevant products
    relevant_products = optimizer.search_relevant_products(search_terms)
    
    if not relevant_products:
        return json.dumps({
            "products": [],
            "attribute_query": "availability",
            "NEED": None,
            "reply": f"Sorry {user_name}, I couldn't find any footwear matching '{', '.join(search_terms)}' at ECS Ehsan Chappal Store. Could you try different keywords like 'chappal', 'sandal', or 'formal shoes'?",
            "similar_products": [],
            "show_images": False
        })
    
    # Step 3: Create focused inventory for LLM
    focused_inventory = optimizer.create_focused_inventory(relevant_products)
    
    # Step 4: Send to LLM for detailed analysis
    system_prompt = f"""
    You are a WhatsApp shopping assistant for ECS - Ehsan Chappal Store, Pakistan's premier footwear destination specializing in traditional chappals, modern sandals, formal shoes, and quality footwear for all occasions.

    You've determined the user wants information about specific products (product_info intent).

    User name: {user_name}
    Available products (pre-filtered for relevance): {focused_inventory}
    
    Search terms used: {search_terms}

    STRICT MATCHING RULES - ABSOLUTELY NO COMPROMISES:
    
    COLOR MATCHING:
    - If user asks for "blue", ACCEPT products that are blue OR legitimate blue shades (navy blue, royal blue, sky blue, light blue, dark blue, midnight blue)
    - If user asks for "green", ACCEPT products that are green OR legitimate green shades (olive green, emerald green, forest green, light green, dark green, mint green)
    - If user asks for "red", ACCEPT products that are red OR legitimate red shades (maroon, crimson, burgundy, cherry red, wine red, deep red)
    - If user asks for "black", ACCEPT products that are black OR very dark shades (charcoal, jet black, midnight black, coal black)
    - If user asks for "white", ACCEPT products that are white OR off-white shades (ivory, cream, off-white, pearl white, bone white)
    - If user asks for "brown", ACCEPT products that are brown OR brown shades (beige, tan, khaki, chocolate brown, coffee brown)
    - If user asks for "grey/gray", ACCEPT products that are grey OR grey shades (silver grey, charcoal grey, light grey, dark grey)
    - REJECT products that are completely different base colors (e.g. green when user asks for blue, red when user asks for black)
    - REJECT mixed colors or combinations unless user specifically asks for them (e.g. "blue-green", "red-orange")
    - The requested color or its legitimate shade must be the DOMINANT/PRIMARY color
    
    PAKISTANI CLOTHING COLOR TERMINOLOGY:
    - "Safed" means white → ACCEPT white, ivory, cream, off-white
    - "Kala" means black → ACCEPT black, charcoal, jet black
    - "Lal" means red → ACCEPT red, maroon, crimson, burgundy
    - "Neela" means blue → ACCEPT blue, navy, royal blue, sky blue
    - "Hara" means green → ACCEPT green, olive, emerald, forest green
    
    EXAMPLES OF CORRECT COLOR MATCHING:
    - User asks for "blue" → ACCEPT: "Navy Blue Kurta", "Royal Blue Shirt", "Light Blue Dress", "Blue Denim Shalwar"
    - User asks for "blue" → REJECT: "Green Kurta with blue accents", "Red Shirt with blue trim", "Teal Dress"
    - User asks for "green" → ACCEPT: "Olive Green Shalwar", "Emerald Green Kameez", "Forest Green Kurta"
    - User asks for "green" → REJECT: "Blue Kurta with green embroidery", "Navy with green hints"
    - User asks for "white" → ACCEPT: "White Cotton Kurta", "Ivory Wedding Sherwani", "Cream Shalwar Kameez"
    - User asks for "white" → REJECT: "Light Grey Kurta", "Beige with white accents"
    - User asks for "black" → ACCEPT: "Black Formal Suit", "Charcoal Waistcoat", "Jet Black Kurta"
    - User asks for "black" → REJECT: "Dark Grey Suit", "Navy with black trim"
    
    MATERIAL MATCHING:
    - If user asks for "cotton", ONLY show products explicitly described as cotton
    - REJECT "cotton blend", "cotton-silk mix" unless user asks for blends
    - Material must be the PRIMARY material mentioned in product description
    
    STYLE MATCHING:
    - If user asks for "embroidered", ONLY show products with embroidery mentioned
    - If user asks for "plain", ONLY show products WITHOUT embroidery or patterns
    - REJECT products that don't explicitly mention the requested style feature
    
    OCCASION MATCHING:
    - If user asks for "formal", ONLY show products described as formal/wedding/special occasion
    - If user asks for "casual", ONLY show products described as casual/everyday/daily wear
    - REJECT products that don't explicitly match the occasion requirement
    
    VALIDATION PROCESS:
    1. For COLOR requests, check if the product contains the requested base color OR its legitimate shades:
       - "blue" request → Accept: navy, royal blue, sky blue, dark blue, light blue
       - "green" request → Accept: olive, emerald, forest green, mint green
       - "red" request → Accept: maroon, crimson, burgundy, wine red
       - "black" request → Accept: charcoal, jet black, midnight black
       - "white" request → Accept: ivory, cream, off-white, pearl white
    2. For MATERIAL requests, verify the primary material matches exactly
    3. For STYLE requests, ensure the specific style feature is explicitly mentioned
    4. For OCCASION requests, confirm the product is described for that use case
    5. If ANY criterion is not met, EXCLUDE the product completely
    6. If NO products meet ALL criteria, respond with "no exact matches found"
    7. NEVER suggest "close matches" or "similar options" unless user asks for alternatives
    
    FORBIDDEN ACTIONS:
    - DO NOT show completely different base colors (e.g. green when user asks for blue, red when user asks for white)
    - DO NOT show mixed-color items unless user specifically asks for combinations
    - DO NOT show formal wear when user asks for casual
    - DO NOT show embroidered items when user asks for plain
    - DO NOT show approximate matches without explicit user permission
    - DO NOT assume user will accept "similar" products
    
    ALLOWED ACTIONS FOR COLOR MATCHING:
    - DO show legitimate color shades (navy blue for "blue", olive green for "green", maroon for "red")
    - DO show different intensities of the same base color (light blue, dark blue for "blue")
    - DO show traditional color names that are clearly the same base color (ivory for "white", charcoal for "black")
    
    STRICT MATCHING RULES:
    - ONLY recommend products that EXACTLY match the user's requirements
    - If user asks for "blue" clothes, show products that are blue OR legitimate blue shades (navy, royal blue, sky blue)
    - If user asks for "green" clothes, show products that are green OR legitimate green shades (olive, emerald, forest green)
    - REJECT completely different base colors (green when user asks for blue, red when user asks for white)
    - If user asks for specific material (cotton, silk, velvet), ONLY show products made from that exact material
    - If user asks for specific style (embroidered, plain), ONLY show products with that exact style
    - If user asks for specific occasion (formal, casual, wedding), ONLY show products suitable for that exact occasion
    - DO NOT suggest alternatives unless the user explicitly asks for alternatives
    - If no products match exactly, say so clearly instead of showing approximate matches

    Respond with a JSON object that contains:
    1. "products": Either a single product ID or an array of up to 3 products that EXACTLY match the user's criteria
       - REQUIRED FIELD
       - ONLY include products that meet ALL specified criteria
       
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
       - FIRST validates that recommended products meet ALL user criteria
       - Provides key information ONLY about products that EXACTLY match the criteria
       - If no exact matches found, MUST state: "Sorry, I couldn't find any [exact requirement] products that match your specific criteria in our inventory"
       - NEVER mention products that don't meet exact requirements
       - If only partial matches exist, clearly state: "I found some products but they don't exactly match your [specific requirement]"
       - Suggests being more specific or browsing categories if no matches
       - Is natural, brief and conversational, as you would text on WhatsApp
       - Only use the user's name occasionally and naturally
       - Uses the same language as the user's message
       - REQUIRED FIELD
    
    5. "similar_products": (Optional) Up to 2 similar or alternative product IDs ONLY if user asks for alternatives
    
    6. "show_images": Boolean indicating if product images should be displayed (true only if exact matches found)
    
    Notes:
    - Be strict about matching criteria - better to say "no matches" than show wrong products
    - Only work with the products provided in the focused inventory
    - For traditional Pakistani clothing, focus on key attributes like embroidery, fabric, occasion, and style
    - Keep responses informative but concise for WhatsApp format
    - Prioritize accuracy over showing multiple options

    JSON response:
    """
    
    messages = prepare_messages(system_prompt, message, conversation_history)
    llm_response = safe_api_call(messages)

    # Apply GuardRails validation for product information
    llm_response = validate_llm_response(llm_response, "product_info", {"inventory": focused_inventory})
    
    # Additional validation of LLM recommendations
    if llm_response and 'products' in llm_response:
        validated_products = validate_product_recommendations(
            llm_response['products'], 
            search_terms, 
            message,
            focused_inventory
        )
        if validated_products != llm_response['products']:
            llm_response['products'] = validated_products
            # Update reply if products were filtered out
            if not validated_products:
                llm_response['reply'] = f"Sorry, I couldn't find any products that exactly match your specific requirements in our inventory. You might want to browse our categories or try different search terms."
                llm_response['show_images'] = False
    
    return llm_response


def validate_product_recommendations(product_ids, search_terms: List[str], user_message: str, inventory: str) -> List[str]:
    """
    Additional validation layer to ensure recommended products truly match user criteria
    """
    if not product_ids:
        return []
    
    # Convert single product to list for consistent processing
    if isinstance(product_ids, str):
        product_ids = [product_ids]
    
    validated_products = []
    user_message_lower = user_message.lower()
    
    # Extract user requirements more precisely
    color_requirements = []
    material_requirements = []
    style_requirements = []
    
    # Color detection
    colors = ['blue', 'green', 'red', 'black', 'white', 'navy', 'maroon', 'grey', 'gray', 'brown', 'beige', 'yellow', 'pink', 'purple', 'orange']
    for color in colors:
        if color in user_message_lower and (f'{color} ' in user_message_lower or f' {color}' in user_message_lower or user_message_lower.startswith(color)):
            color_requirements.append(color)
    
    # Material detection
    materials = ['cotton', 'silk', 'velvet', 'linen', 'wool', 'polyester', 'denim', 'leather']
    for material in materials:
        if material in user_message_lower:
            material_requirements.append(material)
    
    # Style detection
    if 'embroidered' in user_message_lower or 'embroidery' in user_message_lower:
        style_requirements.append('embroidered')
    if 'plain' in user_message_lower and 'explain' not in user_message_lower:
        style_requirements.append('plain')
    
    # Parse inventory to get product details
    try:
        import json
        inventory_data = json.loads(inventory) if isinstance(inventory, str) else inventory
        
        for product_id in product_ids:
            product_found = False
            product_matches = True
            
            # Find the product in inventory
            if isinstance(inventory_data, list):
                products = inventory_data
            else:
                products = inventory_data.get('products', [])
            
            for product in products:
                if product.get('id') == product_id or product.get('product_id') == product_id:
                    product_found = True
                    product_name = (product.get('name') or product.get('title') or '').lower()
                    product_desc = product.get('description', '').lower()
                    product_text = f"{product_name} {product_desc}"
                    
                    # Validate color requirements
                    for required_color in color_requirements:
                        if required_color == 'blue':
                            # Very strict blue validation - must be primarily blue
                            if not ('blue' in product_name and not any(other_color in product_name for other_color in ['green', 'teal', 'navy', 'purple'] if other_color != 'blue')):
                                if 'blue' not in product_name or any(x in product_text for x in ['green', 'olive', 'teal', 'hint', 'accent', 'touch']):
                                    product_matches = False
                                    break
                        else:
                            # For other colors, ensure they're primary
                            if required_color not in product_name and required_color not in product_desc[:50]:  # Check first part of description
                                product_matches = False
                                break
                    
                    # Validate material requirements
                    for required_material in material_requirements:
                        if required_material not in product_text:
                            product_matches = False
                            break
                    
                    # Validate style requirements
                    if 'embroidered' in style_requirements:
                        if not any(term in product_text for term in ['embroidered', 'embroidery', 'embroidered']):
                            product_matches = False
                    
                    if 'plain' in style_requirements:
                        if any(term in product_text for term in ['embroidered', 'embroidery', 'pattern', 'printed', 'design']):
                            product_matches = False
                    
                    break
            
            # Only include if product found and matches all criteria
            if product_found and product_matches:
                validated_products.append(product_id)
    
    except Exception as e:
        # If validation fails, be conservative and return empty list
        print(f"Validation error: {e}")
        return []
    
    return validated_products


def get_detailed_product_info(product_ids: List[str]) -> Dict[str, Any]:
    """
    Get detailed information for specific product IDs
    Used when user wants more details about products identified in initial search
    """
    detailed_products = {}
    
    for product_id in product_ids:
        product_details = get_product_details(product_id)
        if product_details['status'] == 'success' and product_details['data']:
            detailed_products[product_id] = product_details['data']
    
    return detailed_products


# Smart caching for frequently searched terms
class ProductSearchCache:
    """Simple in-memory cache for frequent product searches"""
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.access_count = {}
    
    def get(self, search_terms: tuple) -> Optional[List[Dict]]:
        """Get cached search results"""
        key = tuple(sorted(search_terms))
        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return self.cache[key]
        return None
    
    def set(self, search_terms: tuple, results: List[Dict]):
        """Cache search results"""
        key = tuple(sorted(search_terms))
        
        # Remove least used items if cache is full
        if len(self.cache) >= self.max_size:
            least_used = min(self.access_count.items(), key=lambda x: x[1])
            del self.cache[least_used[0]]
            del self.access_count[least_used[0]]
        
        self.cache[key] = results
        self.access_count[key] = 1

# Global cache instance
search_cache = ProductSearchCache()
