"""
Multi-Layer Retrieval System for Product Search
Implements context-aware, category-first, memory-enabled product discovery
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from .llm_core import safe_api_call, prepare_messages
from .db_inventory import get_all_categories, get_all_products, advanced_product_search
from .embeddings import get_embedding_service
from .semantic_product_filter import SemanticProductFilter

logger = logging.getLogger(__name__)

class UserProfile:
    """Manages user preferences and conversation memory"""
    
    def __init__(self):
        self.profiles = {}  # user_id -> profile data
    
    def extract_preferences(self, user_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Extract user preferences from conversation history"""
        profile = self.profiles.get(user_id, {
            'budget_range': None,
            'preferred_colors': [],
            'preferred_materials': [],
            'preferred_styles': [],
            'gender_preferences': [],
            'size_preferences': [],
            'occasion_preferences': [],
            'brand_preferences': [],
            'last_updated': datetime.now(),
            'query_count': 0
        })
        
        # Analyze recent conversation for preferences
        recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        
        for message in recent_messages:
            content = message.get('content', '').lower()
            
            # Extract budget mentions
            if any(word in content for word in ['budget', 'price', 'cost', 'rs', 'rupees']):
                budget_match = self._extract_budget_from_text(content)
                if budget_match:
                    profile['budget_range'] = budget_match
            
            # Extract color preferences
            colors = ['black', 'white', 'brown', 'blue', 'red', 'green', 'navy', 'grey', 'tan', 'beige']
            for color in colors:
                if color in content and color not in profile['preferred_colors']:
                    profile['preferred_colors'].append(color)
            
            # Extract material preferences
            materials = ['leather', 'cotton', 'silk', 'velvet', 'suede', 'canvas', 'synthetic']
            for material in materials:
                if material in content and material not in profile['preferred_materials']:
                    profile['preferred_materials'].append(material)
            
            # Extract style preferences
            styles = ['formal', 'casual', 'sporty', 'traditional', 'modern', 'elegant']
            for style in styles:
                if style in content and style not in profile['preferred_styles']:
                    profile['preferred_styles'].append(style)
        
        profile['last_updated'] = datetime.now()
        profile['query_count'] += 1
        self.profiles[user_id] = profile
        
        return profile
    
    def _extract_budget_from_text(self, text: str) -> Optional[Dict[str, int]]:
        """Extract budget range from text"""
        import re
        
        # Look for patterns like "under 5000", "below 3000", "5000-8000", "around 6000"
        patterns = [
            r'under (\d+)',
            r'below (\d+)', 
            r'less than (\d+)',
            r'(\d+)\s*-\s*(\d+)',
            r'around (\d+)',
            r'about (\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 1:
                    amount = int(match.group(1))
                    return {'max': amount}
                elif len(match.groups()) == 2:
                    min_amount = int(match.group(1))
                    max_amount = int(match.group(2))
                    return {'min': min_amount, 'max': max_amount}
        
        return None

class CategoryDetector:
    """Detects product categories and determines query specificity"""
    
    def __init__(self):
        self.category_keywords = {
            'footwear': ['shoes', 'chappal', 'sandal', 'boot', 'slipper', 'sneaker', 'formal shoes', 'casual shoes'],
            'clothing': ['shirt', 'kurta', 'shalwar', 'kameez', 'waistcoat', 'sherwani', 'dress'],
            'accessories': ['watch', 'belt', 'bag', 'wallet', 'sunglasses']
        }
        
        self.subcategory_keywords = {
            'formal_footwear': ['formal shoes', 'dress shoes', 'oxford', 'loafer'],
            'casual_footwear': ['casual shoes', 'sneakers', 'canvas shoes'],
            'traditional_footwear': ['chappal', 'khussas', 'mojaris'],
            'sandals': ['sandals', 'flip flop', 'slides']
        }
    
    def analyze_query(self, message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Analyze query to determine category and specificity"""
        message_lower = message.lower()
        
        # Determine query type
        query_analysis = {
            'is_general': self._is_general_query(message_lower),
            'is_specific': self._is_specific_query(message_lower),
            'detected_categories': [],
            'detected_subcategories': [],
            'specificity_score': 0,
            'context_from_history': self._extract_context_from_history(conversation_history)
        }
        
        # Detect categories
        for category, keywords in self.category_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                query_analysis['detected_categories'].append(category)
        
        # Detect subcategories
        for subcategory, keywords in self.subcategory_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                query_analysis['detected_subcategories'].append(subcategory)
        
        # Calculate specificity score
        query_analysis['specificity_score'] = self._calculate_specificity(message_lower)
        
        return query_analysis
    
    def _is_general_query(self, message: str) -> bool:
        """Check if query is general/broad"""
        general_patterns = [
            'show me', 'i want', 'looking for', 'need some', 'browse', 'see your',
            'what do you have', 'any', 'something', 'options'
        ]
        return any(pattern in message for pattern in general_patterns)
    
    def _is_specific_query(self, message: str) -> bool:
        """Check if query is specific"""
        specific_indicators = [
            'size', 'color', 'price', 'brand', 'model', 'rs ', 'rupees',
            'black', 'white', 'brown', 'blue', 'red', 'green'
        ]
        return any(indicator in message for indicator in specific_indicators)
    
    def _calculate_specificity(self, message: str) -> int:
        """Calculate specificity score from 1-10"""
        score = 0
        
        # Count specific attributes mentioned
        attributes = ['color', 'size', 'material', 'brand', 'price', 'style', 'occasion']
        for attr in attributes:
            if attr in message:
                score += 1
        
        # Bonus for specific values
        specific_values = ['black', 'white', 'brown', 'formal', 'casual', 'leather', 'cotton']
        for value in specific_values:
            if value in message:
                score += 1
        
        return min(score, 10)
    
    def _extract_context_from_history(self, conversation_history: List[Dict]) -> str:
        """Extract relevant context from conversation history"""
        if not conversation_history:
            return ""
        
        # Look for preferences in recent conversation
        recent_context = []
        for message in conversation_history[-5:]:
            content = message.get('content', '')
            if any(word in content.lower() for word in ['prefer', 'like', 'want', 'need', 'looking']):
                recent_context.append(content)
        
        return " ".join(recent_context)

class MultiLayerRetrieval:
    """Main multi-layer retrieval system"""
    
    def __init__(self):
        self.user_profile = UserProfile()
        self.category_detector = CategoryDetector()
        self.semantic_filter = SemanticProductFilter()
        self.embedding_service = get_embedding_service()
    
    def search_products(self, 
                       user_id: str,
                       message: str, 
                       conversation_history: List[Dict],
                       user_name: str = None) -> Dict[str, Any]:
        """
        Main search function implementing the multi-layer retrieval pipeline
        """
        
        # Step 1: Extract user profile and preferences
        user_profile = self.user_profile.extract_preferences(user_id, conversation_history)
        
        # Step 2: Analyze query for category detection and specificity
        query_analysis = self.category_detector.analyze_query(message, conversation_history)
        
        # Step 3: Context-aware query reformulation
        refined_query = self._reformulate_query(message, conversation_history, user_profile, query_analysis)
        
        # Step 4: Determine retrieval strategy based on query type
        if query_analysis['is_general'] and query_analysis['specificity_score'] < 3:
            # General query - return category summaries
            return self._handle_general_query(refined_query, user_profile, query_analysis)
        else:
            # Specific query - return products
            return self._handle_specific_query(refined_query, user_profile, query_analysis)
    
    def _reformulate_query(self, 
                          original_message: str,
                          conversation_history: List[Dict],
                          user_profile: Dict[str, Any],
                          query_analysis: Dict[str, Any]) -> str:
        """Reformulate query using conversation context and user preferences"""
        
        # ALWAYS preserve the original user query as the base
        # Only add context for extremely vague queries, never for specific product requests
        
        # Check if query is specific enough - if it mentions a product type + attribute, don't add preferences
        message_lower = original_message.lower()
        
        # Product type keywords
        product_types = ['shoes', 'heels', 'sandals', 'boots', 'flats', 'sneakers', 'pumps', 'loafers', 
                        'kurta', 'shirt', 'dress', 'kameez', 'sherwani', 'waistcoat']
        
        # Color keywords
        color_words = ['black', 'white', 'brown', 'blue', 'red', 'green', 'yellow', 'gray', 'beige', 
                      'pink', 'orange', 'purple', 'gold', 'golden', 'silver', 'maroon', 'navy']
        
        # Style keywords  
        style_words = ['formal', 'casual', 'party', 'wedding', 'office', 'sports', 'elegant', 'traditional']
        
        # Size/price keywords
        specific_keywords = ['size', 'rs', 'rupees', 'price', 'budget', 'cost', 'under', 'below', 'around']
        
        # If query mentions product type + any specific attribute, keep it as-is
        has_product_type = any(product in message_lower for product in product_types)
        has_specific_attr = (any(color in message_lower for color in color_words) or
                           any(style in message_lower for style in style_words) or  
                           any(keyword in message_lower for keyword in specific_keywords))
        
        # For specific queries like "yellow heels" or "formal shoes", return original query unchanged
        if has_product_type and has_specific_attr:
            return original_message
            
        # For very vague queries like "show me something", only add minimal context
        if len(original_message.split()) <= 3 and not has_product_type:
            refined_parts = [original_message]
            
            # Only add budget if query has NO specifics at all
            if not any(word in message_lower for word in color_words + style_words + specific_keywords):
                if user_profile.get('budget_range') and 'max' in user_profile['budget_range']:
                    refined_parts.append(f"under Rs {user_profile['budget_range']['max']}")
            
            if len(refined_parts) > 1:
                return ' '.join(refined_parts)
        
        # For all other cases, return original query unchanged
        return original_message
    
    def _handle_general_query(self, 
                             query: str,
                             user_profile: Dict[str, Any],
                             query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general queries by returning category summaries"""
        
        try:
            # Get all categories
            categories_result = get_all_categories()
            if categories_result['status'] != 'success':
                return self._error_response("Failed to fetch categories")
            
            categories = categories_result['data']
            
            # For each category, get a sample of products and create summary
            category_summaries = []
            
            for category in categories:
                # Get sample products from this category (5-10 products)
                sample_products = self._get_sample_products_by_category(
                    category['id'], 
                    limit=8,
                    user_preferences=user_profile
                )
                
                if sample_products:
                    # Create category summary
                    summary = self._create_category_summary(category, sample_products, user_profile)
                    category_summaries.append(summary)
            
            return {
                'type': 'category_overview',
                'query_type': 'general',
                'refined_query': query,
                'user_profile': user_profile,
                'categories': category_summaries,
                'next_action': 'drill_down',
                'total_categories': len(category_summaries)
            }
            
        except Exception as e:
            logger.error(f"Error in general query handling: {e}")
            return self._error_response("Failed to process general query")
    
    def _handle_specific_query(self,
                              query: str,
                              user_profile: Dict[str, Any], 
                              query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle specific queries by returning relevant products"""
        
        try:
            # Determine retrieval size based on specificity
            if query_analysis['specificity_score'] >= 7:
                limit = 15  # Very specific - fewer results
            elif query_analysis['specificity_score'] >= 4:
                limit = 25  # Moderately specific
            else:
                limit = 50  # Less specific - more results for filtering
            
            # Perform hybrid search
            products = self._hybrid_search(query, user_profile, limit)
            
            if not products:
                return {
                    'type': 'no_results',
                    'query_type': 'specific',
                    'refined_query': query,
                    'user_profile': user_profile,
                    'suggestion': 'Try browsing categories or use different keywords'
                }
            
            # If we have too many results, cluster them
            if len(products) > 20:
                clustered_results = self._cluster_products(products, max_clusters=5)
                return {
                    'type': 'clustered_results',
                    'query_type': 'specific',
                    'refined_query': query,
                    'user_profile': user_profile,
                    'clusters': clustered_results,
                    'total_products': len(products),
                    'next_action': 'refine_or_drill_down'
                }
            else:
                # Return direct product results
                return {
                    'type': 'direct_results',
                    'query_type': 'specific',
                    'refined_query': query,
                    'user_profile': user_profile,
                    'products': products[:15],  # Limit for LLM
                    'total_found': len(products),
                    'next_action': 'select_product'
                }
                
        except Exception as e:
            logger.error(f"Error in specific query handling: {e}")
            return self._error_response("Failed to process specific query")
    
    def _hybrid_search(self, 
                      query: str,
                      user_profile: Dict[str, Any],
                      limit: int = 25) -> List[Dict]:
        """Perform hybrid search combining semantic and structured filtering"""
        
        try:
            # Step 1: Semantic search for relevance
            semantic_results = self._semantic_search(query, limit * 2)  # Get more for filtering
            
            # Step 2: Apply user preferences as filters
            filtered_results = self._apply_preference_filters(semantic_results, user_profile)
            
            # Step 3: Apply structured filters based on query
            final_results = self._apply_query_filters(filtered_results, query)
            
            return final_results[:limit]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    def _semantic_search(self, query: str, limit: int) -> List[Dict]:
        """Perform semantic search using embeddings"""
        try:
            # Use the existing semantic filter with fallback enabled for multilayer search
            relevant_products_json = self.semantic_filter.get_relevant_products_for_llm(
                query, 
                limit=limit, 
                fallback_to_all=True  # Enable fallback for better results
            )
            
            # Parse the JSON response and extract products
            if relevant_products_json:
                relevant_data = json.loads(relevant_products_json)
                
                # Extract products from nested category structure
                products = []
                if 'categories' in relevant_data:
                    for category in relevant_data['categories']:
                        if 'products' in category:
                            products.extend(category['products'])
                
                if products:
                    logger.info(f"✅ Semantic search found {len(products)} products")
                    return products
            
            logger.warning(f"⚠️ No products found for query: {query}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error in semantic search: {e}")
            return []
    
    def _apply_preference_filters(self, 
                                 products: List[Dict],
                                 user_profile: Dict[str, Any]) -> List[Dict]:
        """Apply user preference filters to product list"""
        
        if not user_profile:
            return products
        
        filtered = []
        
        for product in products:
            # Check budget constraints
            if user_profile.get('budget_range'):
                budget = user_profile['budget_range']
                product_price = self._extract_price(product)
                
                if product_price:
                    if 'max' in budget and product_price > budget['max']:
                        continue
                    if 'min' in budget and product_price < budget['min']:
                        continue
            
            # Check color preferences
            if user_profile.get('preferred_colors'):
                product_colors = product.get('colors', [])
                if isinstance(product_colors, list):
                    product_colors_lower = [color.lower() for color in product_colors]
                    if not any(pref_color in product_colors_lower for pref_color in user_profile['preferred_colors']):
                        continue
            
            # Check material preferences  
            if user_profile.get('preferred_materials'):
                product_material = product.get('material', '').lower()
                if not any(pref_material in product_material for pref_material in user_profile['preferred_materials']):
                    continue
            
            filtered.append(product)
        
        return filtered
    
    def _apply_query_filters(self, products: List[Dict], query: str) -> List[Dict]:
        """Apply filters based on the query content"""
        
        query_lower = query.lower()
        
        # Extract filters from query
        filters = {
            'colors': [],
            'materials': [],
            'styles': [],
            'price_range': None
        }
        
        # Color filters
        colors = ['black', 'white', 'brown', 'blue', 'red', 'green', 'navy', 'grey', 'tan', 'beige']
        for color in colors:
            if color in query_lower:
                filters['colors'].append(color)
        
        # Material filters
        materials = ['leather', 'cotton', 'silk', 'velvet', 'suede', 'canvas', 'synthetic']
        for material in materials:
            if material in query_lower:
                filters['materials'].append(material)
        
        # Style filters
        styles = ['formal', 'casual', 'sporty', 'traditional', 'modern', 'elegant']
        for style in styles:
            if style in query_lower:
                filters['styles'].append(style)
        
        # Apply filters
        filtered = []
        for product in products:
            # Color filter
            if filters['colors']:
                product_colors = product.get('colors', [])
                if isinstance(product_colors, list):
                    product_colors_lower = [color.lower() for color in product_colors]
                    if not any(color in product_colors_lower for color in filters['colors']):
                        continue
            
            # Material filter
            if filters['materials']:
                product_material = product.get('material', '').lower()
                if not any(material in product_material for material in filters['materials']):
                    continue
            
            # Style filter (check title, description, style fields)
            if filters['styles']:
                searchable_text = f"{product.get('title', '')} {product.get('description', '')} {product.get('style', '')}".lower()
                if not any(style in searchable_text for style in filters['styles']):
                    continue
            
            filtered.append(product)
        
        return filtered
    
    def _get_sample_products_by_category(self,
                                        category_id: str,
                                        limit: int = 8,
                                        user_preferences: Dict[str, Any] = None) -> List[Dict]:
        """Get sample products from a category"""
        try:
            # Use advanced search to get products by category
            filters = {
                'categories': [category_id],
                'limit': limit
            }
            
            # Add user preferences to filters if available
            if user_preferences:
                if user_preferences.get('budget_range'):
                    filters['price_range'] = user_preferences['budget_range']
                if user_preferences.get('preferred_colors'):
                    filters['colors'] = user_preferences['preferred_colors']
                if user_preferences.get('preferred_materials'):
                    filters['materials'] = user_preferences['preferred_materials']
            
            result = advanced_product_search(filters)
            
            if result['status'] == 'success' and result['data']:
                return result['data']
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting sample products for category {category_id}: {e}")
            return []
    
    def _create_category_summary(self,
                                category: Dict[str, Any],
                                sample_products: List[Dict],
                                user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary for a category based on sample products"""
        
        # Analyze sample products to create summary
        price_range = self._analyze_price_range(sample_products)
        available_colors = self._extract_unique_colors(sample_products)
        available_materials = self._extract_unique_materials(sample_products)
        
        summary = {
            'category_id': category['id'],
            'category_name': category['name'],
            'description': category.get('description', ''),
            'product_count': len(sample_products),
            'price_range': price_range,
            'available_colors': available_colors[:8],  # Limit colors shown
            'available_materials': available_materials[:5],  # Limit materials shown
            'sample_products': sample_products[:3],  # Show top 3 as examples
            'matches_user_preferences': self._check_category_preference_match(
                sample_products, user_profile
            )
        }
        
        return summary
    
    def _cluster_products(self, products: List[Dict], max_clusters: int = 5) -> List[Dict]:
        """Cluster products by similarity for better organization"""
        
        # Simple clustering based on categories, price ranges, and attributes
        clusters = {}
        
        for product in products:
            # Create clustering key based on category and price range
            category_name = product.get('categories', {}).get('name', 'Other')
            price = self._extract_price(product)
            
            # Price range clustering
            if price:
                if price < 2000:
                    price_range = "Budget (Under Rs 2,000)"
                elif price < 5000:
                    price_range = "Mid-range (Rs 2,000-5,000)"
                else:
                    price_range = "Premium (Above Rs 5,000)"
            else:
                price_range = "Price not specified"
            
            cluster_key = f"{category_name} - {price_range}"
            
            if cluster_key not in clusters:
                clusters[cluster_key] = {
                    'cluster_name': cluster_key,
                    'category': category_name,
                    'price_range': price_range,
                    'products': [],
                    'representative_product': None
                }
            
            clusters[cluster_key]['products'].append(product)
        
        # Set representative products and limit cluster size
        cluster_list = []
        for cluster_data in clusters.values():
            # Sort products by relevance (you could implement a scoring system)
            cluster_data['products'] = cluster_data['products'][:8]  # Limit products per cluster
            cluster_data['representative_product'] = cluster_data['products'][0]  # First as representative
            cluster_data['product_count'] = len(cluster_data['products'])
            cluster_list.append(cluster_data)
        
        # Return top clusters
        return sorted(cluster_list, key=lambda x: x['product_count'], reverse=True)[:max_clusters]
    
    def _extract_price(self, product: Dict[str, Any]) -> Optional[float]:
        """Extract price from product data"""
        price_fields = ['sale_price', 'regular_price', 'price', 'unit_price']
        
        for field in price_fields:
            price_value = product.get(field)
            if price_value:
                try:
                    # Handle string prices like "Rs 2500" or "2500"
                    if isinstance(price_value, str):
                        price_value = price_value.replace('Rs', '').replace('rs', '').replace(',', '').strip()
                    return float(price_value)
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _analyze_price_range(self, products: List[Dict]) -> Dict[str, Any]:
        """Analyze price range of products"""
        prices = []
        for product in products:
            price = self._extract_price(product)
            if price:
                prices.append(price)
        
        if prices:
            return {
                'min': min(prices),
                'max': max(prices),
                'avg': sum(prices) / len(prices)
            }
        
        return {'min': None, 'max': None, 'avg': None}
    
    def _extract_unique_colors(self, products: List[Dict]) -> List[str]:
        """Extract unique colors from products"""
        colors = set()
        for product in products:
            product_colors = product.get('colors', [])
            if isinstance(product_colors, list):
                colors.update(color.lower() for color in product_colors)
        
        return list(colors)
    
    def _extract_unique_materials(self, products: List[Dict]) -> List[str]:
        """Extract unique materials from products"""
        materials = set()
        for product in products:
            material = product.get('material', '')
            if material:
                materials.add(material.lower())
        
        return list(materials)
    
    def _check_category_preference_match(self, 
                                        products: List[Dict],
                                        user_profile: Dict[str, Any]) -> bool:
        """Check if category matches user preferences"""
        if not user_profile:
            return False
        
        # Check if any products in category match user preferences
        for product in products:
            if self._product_matches_preferences(product, user_profile):
                return True
        
        return False
    
    def _product_matches_preferences(self, 
                                   product: Dict[str, Any],
                                   user_profile: Dict[str, Any]) -> bool:
        """Check if a product matches user preferences"""
        
        # Check budget
        if user_profile.get('budget_range'):
            budget = user_profile['budget_range']
            price = self._extract_price(product)
            if price:
                if 'max' in budget and price > budget['max']:
                    return False
                if 'min' in budget and price < budget['min']:
                    return False
        
        # Check colors
        if user_profile.get('preferred_colors'):
            product_colors = product.get('colors', [])
            if isinstance(product_colors, list):
                product_colors_lower = [color.lower() for color in product_colors]
                if not any(pref_color in product_colors_lower for pref_color in user_profile['preferred_colors']):
                    return False
        
        return True
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            'type': 'error',
            'message': message,
            'next_action': 'fallback_search'
        }

# Global instance for easy access
_retrieval_system = None

def get_retrieval_system() -> MultiLayerRetrieval:
    """Get global retrieval system instance"""
    global _retrieval_system
    if _retrieval_system is None:
        _retrieval_system = MultiLayerRetrieval()
    return _retrieval_system

def search_products_multilayer(user_id: str,
                              message: str,
                              conversation_history: List[Dict],
                              user_name: str = None) -> Dict[str, Any]:
    """
    Main function for multi-layer product search
    
    Usage:
        result = search_products_multilayer(
            user_id="user123",
            message="I want black formal shoes",
            conversation_history=conversation_history,
            user_name="John"
        )
    """
    retrieval_system = get_retrieval_system()
    return retrieval_system.search_products(user_id, message, conversation_history, user_name)
