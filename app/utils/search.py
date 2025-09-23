from flask import Flask, request, jsonify
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from groq import Groq
from supabase import create_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlaskConversationSearcher:
    """Flask-integrated conversation-based product searcher"""

    def __init__(self):
        # Configuration from environment
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.supabase_url = os.getenv('SUPABASE_URL') or os.getenv('INVENTORY_SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('INVENTORY_SUPABASE_KEY')
        self.groq_model = os.getenv('GROQ_MODEL', 'llama3-70b-8192')

        # Initialize components
        self.groq_client = None
        self.supabase_client = None
        self.embedding_service = None
        self.conversations = {}  # Store user conversations
        self.user_specifications = {}  # Store user product specifications per user_id
        self.query_cache = {}  # Cache LLM responses for identical queries
        self._initialized = False

    def initialize(self):
        """Initialize all components - call this once at app startup"""
        if self._initialized:
            return

        try:
            # Initialize Groq
            self.groq_client = Groq(api_key=self.groq_api_key)

            # Initialize Supabase
            self.supabase_client = create_client(self.supabase_url, self.supabase_key)

            # Initialize embedding service (which handles Pinecone)
            from ..services.embeddings import get_embedding_service
            self.embedding_service = get_embedding_service()

            self._initialized = True
            logger.info("✅ Flask Conversation Searcher initialized successfully")

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise

    @property
    def pinecone_index(self):
        """Get Pinecone index from embedding service"""
        return self.embedding_service.pinecone_index if self.embedding_service else None

    @property
    def pinecone_initialized(self):
        """Check if Pinecone is initialized in embedding service"""
        return self.embedding_service and self.embedding_service.pinecone_index is not None

    def _ensure_pinecone_connection(self):
        """Ensure Pinecone connection is active"""
        if not self.pinecone_initialized:
            raise Exception("Pinecone not initialized in embedding service")

    def get_user_specifications(self, user_id: str) -> Dict:
        """Get current user product specifications"""
        return self.user_specifications.get(user_id, {
            "refined_query": "",
            "filters": {},
            "context_change": False
        })

    def update_user_specifications(self, user_id: str, new_specifications: Dict):
        """Update user product specifications"""
        current_specs = self.get_user_specifications(user_id)

        # Handle context changes
        if new_specifications.get("context_change", False):
            # Complete context change - reset everything
            self.user_specifications[user_id] = new_specifications
            logger.info(f"🔄 Context changed for user {user_id}: {new_specifications}")
        else:
            # Merge specifications
            current_specs["refined_query"] = new_specifications.get("refined_query", current_specs["refined_query"])

            # Merge filters
            new_filters = new_specifications.get("filters", {})
            current_filters = current_specs.get("filters", {})

            # Handle filter removals
            remove_filters = new_filters.get("remove_filters", [])
            for filter_key in remove_filters:
                if filter_key in current_filters:
                    del current_filters[filter_key]
                    logger.info(f"🗑️ Removed filter '{filter_key}' for user {user_id}")

            # Update existing filters
            for key, value in new_filters.items():
                if key != "remove_filters" and value:  # Don't add empty values
                    current_filters[key] = value

            current_specs["filters"] = current_filters
            self.user_specifications[user_id] = current_specs
            logger.info(f"🔄 Updated specifications for user {user_id}: {current_specs}")

        return self.user_specifications[user_id]

    def get_user_conversation(self, user_id: str) -> List[Dict]:
        """Get conversation history for a user from session or database"""
        try:
            # Option 1: From Flask session (only if in Flask context)
            from flask import session
            session_key = f"conversation_{user_id}"
            if session_key in session:
                return session[session_key]
        except (ImportError, RuntimeError):
            # Not in Flask context or Flask not available, use fallback
            pass

        # Option 2: From database (implement as needed)
        # return self.load_conversation_from_db(user_id)

        return []

    def save_user_conversation(self, user_id: str, conversation: List[Dict]):
        """Save conversation history for a user"""
        try:
            # Option 1: Save to Flask session (only if in Flask context)
            from flask import session
            session_key = f"conversation_{user_id}"
            session[session_key] = conversation
        except (ImportError, RuntimeError):
            # Not in Flask context or Flask not available, skip session save
            pass

        # Option 2: Save to database (implement as needed)
        # self.save_conversation_to_db(user_id, conversation)

    def add_message_to_conversation(self, user_id: str, role: str, content: str):
        """Add a message to user's conversation history"""
        conversation = self.get_user_conversation(user_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        conversation.append(message)

        # Keep only last 20 messages to avoid session bloat
        if len(conversation) > 20:
            conversation = conversation[-20:]

        self.save_user_conversation(user_id, conversation)
        return conversation

    def format_conversation_for_llm(self, conversation: List[Dict], max_messages: int = 10) -> str:
        """Format conversation for LLM processing"""
        recent_messages = conversation[-max_messages:] if len(conversation) > max_messages else conversation

        formatted = []
        for msg in recent_messages:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def extract_user_product_specifications(self, latest_query: str, conversation_context: str) -> Dict:
        """Use Groq LLaMA3-70B to extract refined query and filters from conversation context"""
        try:
            # Create cache key from latest query
            cache_key = f"{latest_query.lower().strip()}"

            # Check cache first
            if cache_key in self.query_cache:
                logger.info(f"🚀 Using cached LLM response for: {latest_query}")
                return self.query_cache[cache_key]
            system_prompt = """You extract product search specifications from user queries. Return JSON only:

{
  "refined_query": "product type and style",
  "filters": {
    "colors": ["color1", "color2"],
    "sizes": ["size1", "size2"],
    "price_range": {"min": null, "max": 5000},
    "brands": ["brand1"],
    "materials": ["material1"],
    "occasions": ["occasion1"]
  },
  "context_change": false
}

Guidelines:
1. refined_query: product type and style (remove colors/sizes from query text)
2. filters: only explicitly mentioned attributes
3. context_change: true if user completely changes product type
4. Maintain context from previous messages unless user explicitly changes"""

            # Limit conversation context to last 3 messages to reduce tokens
            context_lines = conversation_context.split('\n')
            limited_context = '\n'.join(context_lines[-6:]) if len(context_lines) > 6 else conversation_context

            user_prompt = f"""Conversation Context:
{limited_context}

Latest User Query: {latest_query}

Extract the product specifications as JSON:"""

            response = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.groq_model,
                temperature=0.1,
                max_tokens=250,
            )

            specifications_json = response.choices[0].message.content.strip()
            logger.info(f"🧠 Extracted specifications: {specifications_json}")

            # Check if response is empty
            if not specifications_json:
                logger.warning("⚠️ Empty response from LLM")
                raise ValueError("Empty response from LLM")

            # Extract JSON from response (handle code blocks)
            import json
            import re

            # Try to find JSON in code blocks first
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', specifications_json, re.DOTALL)
            if json_match:
                specifications_json = json_match.group(1)
            elif '{' not in specifications_json:
                # If no JSON structure found, try to extract from the text
                logger.warning("⚠️ No JSON structure found in LLM response")
                raise ValueError("No JSON structure found in response")

            # Parse JSON response with better error handling
            try:
                specifications = json.loads(specifications_json)
                # Validate required fields
                if not isinstance(specifications, dict):
                    raise ValueError("Response is not a JSON object")

                # Ensure required fields exist
                specifications.setdefault("refined_query", latest_query)
                specifications.setdefault("filters", {})
                specifications.setdefault("context_change", False)

                # Cache the result for future use
                self.query_cache[cache_key] = specifications

                # Limit cache size to prevent memory bloat
                if len(self.query_cache) > 100:
                    # Remove oldest entries
                    oldest_key = next(iter(self.query_cache))
                    del self.query_cache[oldest_key]

                return specifications
            except json.JSONDecodeError as json_err:
                logger.error(f"❌ JSON parsing failed: {json_err}")
                logger.error(f"Raw JSON: {specifications_json}")
                raise ValueError(f"Invalid JSON: {json_err}")

        except Exception as e:
            logger.error(f"❌ Specification extraction failed: {e}")
            # Fallback to simple approach
            return {
                "refined_query": latest_query,
                "filters": {},
                "context_change": False
            }

    def search_products_with_specifications(self, specifications: Dict, top_k: int = 25) -> List[Dict]:
        """Search products using both embedding and metadata filters"""
        try:
            # Ensure Pinecone connection is active
            self._ensure_pinecone_connection()

            refined_query = specifications.get("refined_query", "")
            filters = specifications.get("filters", {})

            # Enhance refined query with materials and brands for semantic search
            # Since title/description are embedded, materials/brands work better in semantic search
            enhanced_query = refined_query
            if filters.get("materials") and len(filters["materials"]) > 0:
                materials_text = " ".join(filters["materials"])
                enhanced_query = f"{refined_query} {materials_text}"
            if filters.get("brands") and len(filters["brands"]) > 0:
                brands_text = " ".join(filters["brands"])
                enhanced_query = f"{enhanced_query} {brands_text}"

            # Generate embedding for enhanced query
            query_vector = self.embedding_service.create_embedding(enhanced_query)

            # Build Pinecone filter from specifications
            pinecone_filter = {}

            # Color filters - FIXED: Handle case sensitivity properly
            if filters.get("colors") and len(filters["colors"]) > 0:
                # Capitalize the first letter to match data format in Pinecone
                normalized_color = filters["colors"][0].capitalize()
                pinecone_filter["colors"] = normalized_color

            # Size filters - FIXED: For array metadata fields in Pinecone
            if filters.get("sizes") and len(filters["sizes"]) > 0:
                pinecone_filter["available_sizes"] = filters["sizes"][0]

            # Price range filters - Handle post-query due to string data type in Pinecone
            # NOTE: Pinecone stores prices as strings but requires numbers for comparison
            # We'll retrieve more results and filter them post-query
            price_filter_needed = filters.get("price_range") and (
                filters["price_range"].get("min") is not None or
                filters["price_range"].get("max") is not None
            )

            # Material and brand filters are handled in the search query itself
            # Pinecone doesn't support $regex operators in metadata filtering
            # These filters are incorporated into the refined_query for semantic search

            # Search in Pinecone with filters
            search_params = {
                "vector": query_vector,
                "top_k": top_k * 3 if price_filter_needed else top_k,  # Get more results if price filtering needed
                "include_metadata": True
            }

            if pinecone_filter:
                search_params["filter"] = pinecone_filter
                logger.info(f"🔍 Searching with enhanced query: '{enhanced_query}' and filters: {pinecone_filter}")
            else:
                logger.info(f"🔍 Searching with enhanced query: '{enhanced_query}'")

            logger.debug(f"🔍 Executing Pinecone query with params: {search_params}")
            results = self.pinecone_index.query(**search_params)
            matches = results.get('matches', [])

            # Apply post-query price filtering if needed
            if price_filter_needed:
                filtered_matches = self._apply_price_filter(matches, filters["price_range"])
                logger.info(f"🔍 Found {len(matches)} products, {len(filtered_matches)} after price filtering")
                return filtered_matches[:top_k]  # Return only requested number

            logger.info(f"🔍 Found {len(matches)} products for refined query: '{refined_query}' with filters")
            return matches

        except Exception as e:
            logger.error(f"❌ Filtered search failed: {e}")
            logger.error(f"❌ Query params were: {search_params if 'search_params' in locals() else 'N/A'}")
            # Try fallback to simple search, if that fails too, return empty list
            try:
                fallback_results = self.search_products_in_pinecone(specifications.get("refined_query", ""), top_k)
                return fallback_results if fallback_results is not None else []
            except Exception as fallback_error:
                logger.error(f"❌ Fallback search also failed: {fallback_error}")
                return []  # Return empty list instead of None

    def search_products_in_pinecone(self, query: str, top_k: int = 25) -> List[Dict]:
        """Search products in Pinecone index (legacy method)"""
        try:
            # Ensure Pinecone connection is active
            self._ensure_pinecone_connection()

            # Generate embedding
            query_vector = self.embedding_service.create_embedding(query)

            # Search in Pinecone
            query_params = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": True
            }
            logger.debug(f"🔍 Executing simple Pinecone query with params: {query_params}")
            results = self.pinecone_index.query(**query_params)

            matches = results.get('matches', [])
            logger.info(f"🔍 Found {len(matches)} products for query: '{query}'")
            return matches

        except Exception as e:
            logger.error(f"❌ Pinecone search failed: {e}")
            logger.error(f"❌ Query params were: {query_params if 'query_params' in locals() else 'N/A'}")

            # Use mock data for development when Pinecone is unavailable
            logger.info("🔄 Using mock search data for development")
            try:
                from .mock_search import get_mock_search_results
                return get_mock_search_results(query, top_k=top_k)
            except ImportError:
                logger.warning("⚠️ Mock search not available, returning empty list")
                return []  # Always return empty list instead of None

    def _apply_price_filter(self, matches: List[Dict], price_range: Dict) -> List[Dict]:
        """Apply price filtering to Pinecone results (post-query filtering)"""
        filtered_matches = []
        min_price = price_range.get("min")
        max_price = price_range.get("max")

        for match in matches:
            metadata = match.get('metadata', {})

            # Get prices from metadata (stored as strings)
            price_str = metadata.get('price', '0')
            sale_price_str = metadata.get('sale_price', '0')

            try:
                # Convert to numbers for comparison
                price = int(price_str) if price_str and price_str != '0' else float('inf')
                sale_price = int(sale_price_str) if sale_price_str and sale_price_str != '0' else float('inf')

                # Calculate effective price (lowest available)
                effective_price = min(price, sale_price)

                # Apply price range filter
                price_passes = True
                if min_price is not None and effective_price < min_price:
                    price_passes = False
                if max_price is not None and effective_price > max_price:
                    price_passes = False

                if price_passes:
                    # Add effective_price to metadata for consistency
                    metadata['effective_price'] = effective_price
                    filtered_matches.append(match)

            except (ValueError, TypeError):
                # Skip products with invalid price data
                logger.warning(f"Invalid price data for product: price={price_str}, sale_price={sale_price_str}")
                continue

        return filtered_matches

    def conversation_search(self, user_id: str, user_message: str, top_k: int = 25, external_conversation: List[Dict] = None) -> Dict:
        """Enhanced conversation-based search with specifications and filters"""
        try:
            # Step 1: Use external conversation if provided, otherwise use internal conversation
            if external_conversation:
                # Check if the user message is already at the end of the external conversation
                # If not, add it. This prevents duplication when CLI system already added the message.
                conversation = list(external_conversation)  # Make a copy
                if (not conversation or
                    conversation[-1].get('role') != 'user' or
                    conversation[-1].get('content') != user_message):
                    conversation.append({"role": "user", "content": user_message})
                # Also save to internal conversation for future use
                self.add_message_to_conversation(user_id, "user", user_message)
            else:
                # Add user message to internal conversation
                conversation = self.add_message_to_conversation(user_id, "user", user_message)

            # Step 2: Format conversation for LLM
            conversation_context = self.format_conversation_for_llm(conversation)

            # Step 3: Extract user product specifications (NEW APPROACH)
            new_specifications = self.extract_user_product_specifications(user_message, conversation_context)

            # Step 4: Update user specifications with context
            current_specifications = self.update_user_specifications(user_id, new_specifications)

            # Step 5: Search using specifications (embedding + filters)
            search_results = self.search_products_with_specifications(current_specifications, top_k)

            # Step 6: Format response
            response = {
                "success": True,
                "original_query": user_message,
                "enhanced_query": current_specifications.get("refined_query", user_message),
                "specifications": current_specifications,
                "products": self.format_product_results(search_results),
                "total_found": len(search_results),
                "conversation_length": len(conversation)
            }

            # Step 7: Add assistant response to conversation
            assistant_message = f"Found {len(search_results)} products matching your specifications."
            self.add_message_to_conversation(user_id, "assistant", assistant_message)

            return response

        except Exception as e:
            logger.error(f"❌ Enhanced conversation search failed: {e}")
            # Return fallback response with proper structure
            return {
                "success": False,
                "error": str(e),
                "original_query": user_message,
                "enhanced_query": user_message,
                "specifications": {
                    "refined_query": user_message,
                    "filters": {},
                    "context_change": False
                },
                "products": [],
                "total_found": 0,
                "conversation_length": len(conversation) if conversation else 0
            }

    def format_product_results(self, matches: List[Dict]) -> List[Dict]:
        """Format Pinecone results for API response"""
        products = []

        for match in matches:
            metadata = match.get('metadata', {})
            product = {
                "id": match.get('id'),
                "score": round(match.get('score', 0), 4),
                "title": metadata.get('title', ''),
                "price": metadata.get('price'),
                "sale_price": metadata.get('sale_price'),
                "is_on_sale": metadata.get('is_on_sale', False),
                "colors": metadata.get('colors', []),
                "available_sizes": metadata.get('available_sizes', []),
                "description": metadata.get('description', ''),
                "url": metadata.get('url', ''),
                "category_id": metadata.get('category_id')
            }
            products.append(product)

        return products

# Initialize the searcher
searcher = FlaskConversationSearcher()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

_searcher_initialized = False

@app.before_request
def initialize_searcher():
    """Initialize searcher before the first request"""
    global _searcher_initialized
    if not _searcher_initialized:
        searcher.initialize()
        _searcher_initialized = True

@app.route('/api/search/conversation', methods=['POST'])
def conversation_search_endpoint():
    """
    Main endpoint for conversation-based product search

    Request JSON:
    {
        "user_id": "user123",
        "message": "size 38",
        "top_k": 25  // optional, default 25
    }

    Response JSON:
    {
        "success": true,
        "original_query": "size 38",
        "enhanced_query": "white wedding shoes size 38",
        "products": [...],
        "total_found": 5,
        "conversation_length": 6
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        user_id = data.get('user_id')
        message = data.get('message')
        top_k = data.get('top_k', 25)

        if not user_id or not message:
            return jsonify({"error": "user_id and message are required"}), 400

        # Perform conversation search
        result = searcher.conversation_search(user_id, message, top_k)

        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Search endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversation/<user_id>', methods=['GET'])
def get_conversation(user_id):
    """Get conversation history for a user"""
    try:
        conversation = searcher.get_user_conversation(user_id)
        return jsonify({
            "user_id": user_id,
            "conversation": conversation,
            "message_count": len(conversation)
        })
    except Exception as e:
        logger.error(f"❌ Get conversation error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/conversation/<user_id>', methods=['DELETE'])
def clear_conversation(user_id):
    """Clear conversation history for a user"""
    try:
        searcher.save_user_conversation(user_id, [])
        return jsonify({
            "success": True,
            "message": f"Conversation cleared for user {user_id}"
        })
    except Exception as e:
        logger.error(f"❌ Clear conversation error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/search/simple', methods=['POST'])
def simple_search_endpoint():
    """Simple search without conversation context"""
    try:
        data = request.get_json()
        query = data.get('query')
        top_k = data.get('top_k', 25)

        if not query:
            return jsonify({"error": "query is required"}), 400

        # Direct search without conversation context
        results = searcher.search_products_in_pinecone(query, top_k)

        return jsonify({
            "success": True,
            "query": query,
            "products": searcher.format_product_results(results),
            "total_found": len(results)
        })

    except Exception as e:
        logger.error(f"❌ Simple search error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "searcher_initialized": searcher._initialized,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)