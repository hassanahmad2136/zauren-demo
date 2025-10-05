# core/services/product_search.py
"""
Multi-Tenant RAG Product Search Engine
Vector search → Metadata filtering → LLM enhancement for product recommendations
"""

import logging
from typing import Dict, Any, List

from core.services.tenant_config import TenantConfigManager
from core.services.client_factory import TenantClientFactory
from core.llm.groq_client import groq_client

logger = logging.getLogger(__name__)

class MultiTenantProductSearch:
    """RAG-based product search: Vector → Filter → LLM Enhancement"""
    
    def __init__(self, config_manager: TenantConfigManager, client_factory: TenantClientFactory):
        self.config_manager = config_manager
        self.client_factory = client_factory
        
    async def search_products(self, tenant_id: str, search_entity: Dict[str, Any]) -> Dict[str, Any]:
        """RAG product search with LLM enhancement"""
        
        try:
            # 1. Get tenant configuration
            config = await self.config_manager.get_tenant_config(tenant_id)
            if not config:
                raise ValueError(f"Configuration not found for tenant: {tenant_id}")
                
            # 2. Get tenant clients
            pinecone_index, supabase_client, embedding_model = await self.client_factory.get_tenant_clients(config)
            
            # 3. Vector search in Pinecone
            raw_products = await self._vector_search(
                pinecone_index, embedding_model, search_entity, config
            )
            
            if not raw_products:
                return await self._generate_no_results_response(search_entity, config)
            
            # 4. Apply metadata filters on Pinecone results
            filtered_products = await self._apply_metadata_filters(
                raw_products, search_entity, config
            )
            
            # 5. Get full product details from Supabase
            enriched_products = await self._enrich_with_supabase_data(
                supabase_client, filtered_products, config
            )
            
            # 6. RAG Enhancement: Pass products to LLM for intelligent recommendations
            rag_response = await self._llm_enhance_results(
                enriched_products, search_entity, config
            )
            
            return rag_response
            
        except Exception as e:
            logger.error(f"RAG search failed for tenant {tenant_id}: {e}")
            return {
                "products": [],
                "total": 0,
                "tenant_id": tenant_id,
                "rag_response": f"I apologize, but I encountered an error while searching for products: {str(e)}",
                "error": str(e)
            }
    
    async def _vector_search(self, pinecone_index, embedding_model, search_entity: Dict[str, Any], config) -> List[Dict]:
        """Step 1: Vector similarity search in Pinecone"""
        
        query = search_entity.get("query", "")
        if not query:
            return []
            
        # Create embedding for search query
        prefixed_query = f"{config.embedding.query_prefix}{query}"
        query_embedding = embedding_model.encode([prefixed_query])[0].tolist()
        
        # Vector search with high top_k (we'll filter later)
        vector_results = pinecone_index.query(
            vector=query_embedding,
            top_k=min(100, config.search.max_results * 5),  # Get more results for filtering
            include_metadata=True,
            namespace=config.pinecone.namespace if config.pinecone.namespace else None
        )
        
        logger.info(f"Vector search returned {len(vector_results.matches)} results")
        
        # Convert to product dictionaries
        products = []
        for match in vector_results.matches:
            product = {
                "id": match.id,
                "similarity_score": match.score,
                **match.metadata  # Includes category, brand, price, etc.
            }
            products.append(product)
            
        return products
    
    async def _apply_metadata_filters(self, products: List[Dict], search_entity: Dict[str, Any], config) -> List[Dict]:
        """Step 2: Apply search entity filters to vector results"""
        
        filtered = []
        
        for product in products:
            # Apply similarity threshold
            if product["similarity_score"] < config.search.similarity_threshold:
                continue
                
            # Apply search entity filters
            if not self._product_matches_filters(product, search_entity, config):
                continue
                
            filtered.append(product)
        
        # Sort by similarity score and limit results
        filtered.sort(key=lambda x: x["similarity_score"], reverse=True)
        filtered = filtered[:config.search.max_results]
        
        logger.info(f"Applied filters, {len(filtered)} products remain")
        return filtered
    
    def _product_matches_filters(self, product: Dict, search_entity: Dict[str, Any], config) -> bool:
        """Check if product matches search entity filters with fuzzy matching"""
        
        # Brand filter with fuzzy matching
        if search_entity.get("brand"):
            if not self._fuzzy_match_brand(product.get("brand", ""), search_entity["brand"]):
                return False
        
        # Category filter with fuzzy matching
        if search_entity.get("category"):
            if not self._fuzzy_match_category(product.get("category", ""), search_entity["category"]):
                return False
                
        # Color filter with semantic similarity
        if search_entity.get("color"):
            if not self._fuzzy_match_color(product.get("colors", []), search_entity["color"]):
                return False
        
        # Size filter (exact match for now, could be fuzzy for clothing)
        if search_entity.get("size"):
            if not self._fuzzy_match_size(product.get("sizes", []), search_entity["size"]):
                return False
        
        # Style/Material filters with fuzzy matching
        if search_entity.get("style"):
            if not self._fuzzy_match_style(product.get("style", ""), search_entity["style"]):
                return False
                
        if search_entity.get("material"):
            if not self._fuzzy_match_material(product.get("material", ""), search_entity["material"]):
                return False
        
        # Price range filters (exact)
        product_price = product.get("price", 0)
        if search_entity.get("min_price") and product_price < search_entity["min_price"]:
            return False
        if search_entity.get("max_price") and product_price > search_entity["max_price"]:
            return False
            
        return True
    
    def _fuzzy_match_color(self, product_colors, search_color: str) -> bool:
        """Fuzzy color matching using FuzzyWuzzy for better accuracy"""
        if not product_colors:
            return False
            
        # Normalize inputs
        if isinstance(product_colors, str):
            product_colors = [product_colors]
        search_color = search_color.lower().strip()
        
        try:
            from fuzzywuzzy import fuzz
            
            # Extended color vocabulary for better matching
            color_variations = [
                "red", "crimson", "scarlet", "burgundy", "maroon", "cherry", "wine", "rust", "brick", "rose",
                "blue", "navy", "royal", "sky", "azure", "teal", "turquoise", "cyan", "cobalt", "sapphire",
                "green", "lime", "forest", "emerald", "mint", "olive", "sage", "jade", "pine", "chartreuse",
                "yellow", "gold", "golden", "amber", "honey", "cream", "lemon", "banana", "butter",
                "orange", "tangerine", "peach", "coral", "apricot", "rust", "burnt", "sunset",
                "purple", "violet", "lavender", "plum", "magenta", "lilac", "indigo", "amethyst",
                "pink", "rose", "blush", "fuchsia", "salmon", "coral", "hot pink", "pastel",
                "brown", "tan", "beige", "khaki", "chocolate", "coffee", "camel", "nude", "taupe",
                "black", "charcoal", "ebony", "jet", "onyx", "coal", "midnight", "obsidian",
                "white", "ivory", "cream", "off-white", "pearl", "snow", "alabaster", "vanilla",
                "gray", "grey", "silver", "ash", "slate", "pewter", "charcoal", "steel"
            ]
            
            # Direct match first (fastest)
            for product_color in product_colors:
                if search_color in product_color.lower() or product_color.lower() in search_color:
                    return True
            
            # FuzzyWuzzy matching with color variations
            for product_color in product_colors:
                product_color_clean = product_color.lower().strip()
                
                # Direct fuzzy match between search and product color
                if fuzz.ratio(search_color, product_color_clean) >= 85:
                    return True
                
                # Partial ratio for substring matching
                if fuzz.partial_ratio(search_color, product_color_clean) >= 90:
                    return True
                
                # Check against color variations
                for color_var in color_variations:
                    # If search color is similar to a standard color
                    if fuzz.ratio(search_color, color_var) >= 85:
                        # Check if product has that color family
                        if fuzz.partial_ratio(color_var, product_color_clean) >= 80:
                            return True
            
            return False
            
        except ImportError:
            # Fallback if FuzzyWuzzy not available
            return self._fallback_color_match(product_colors, search_color)
    
    def _fuzzy_match_brand(self, product_brand: str, search_brand: str) -> bool:
        """Fuzzy brand matching using FuzzyWuzzy"""
        if not product_brand:
            return False
            
        try:
            from fuzzywuzzy import fuzz
            
            product_brand = product_brand.lower().strip()
            search_brand = search_brand.lower().strip()
            
            # Direct fuzzy match
            if fuzz.ratio(search_brand, product_brand) >= 85:
                return True
            
            # Partial match for brand variations (e.g., "Nike" in "Nike Air")
            if fuzz.partial_ratio(search_brand, product_brand) >= 90:
                return True
            
            # Token sort ratio for reordered words
            if fuzz.token_sort_ratio(search_brand, product_brand) >= 85:
                return True
            
            return False
            
        except ImportError:
            return self._fallback_brand_match(product_brand, search_brand)
    
    def _fuzzy_match_category(self, product_category: str, search_category: str) -> bool:
        """Fuzzy category matching using FuzzyWuzzy"""
        if not product_category:
            return False
            
        try:
            from fuzzywuzzy import fuzz
            
            product_category = product_category.lower().strip()
            search_category = search_category.lower().strip()
            
            # Direct fuzzy match
            if fuzz.ratio(search_category, product_category) >= 80:
                return True
            
            # Partial match
            if fuzz.partial_ratio(search_category, product_category) >= 85:
                return True
            
            # Category synonyms with fuzzy matching
            category_synonyms = {
                "shoes": ["footwear", "sneakers", "boots", "sandals", "heels", "flats"],
                "clothing": ["apparel", "wear", "garments", "fashion", "clothes"],
                "shirts": ["tops", "blouses", "t-shirts", "tees", "polo"],
                "pants": ["trousers", "jeans", "bottoms", "slacks", "chinos"],
                "electronics": ["gadgets", "devices", "tech", "technology"],
                "phones": ["smartphones", "mobile", "cellphone"]
            }
            
            # Check synonyms with fuzzy matching
            for category, synonyms in category_synonyms.items():
                if fuzz.partial_ratio(search_category, category) >= 80:
                    for synonym in synonyms:
                        if fuzz.partial_ratio(synonym, product_category) >= 80:
                            return True
                            
                if fuzz.partial_ratio(product_category, category) >= 80:
                    for synonym in synonyms:
                        if fuzz.partial_ratio(search_category, synonym) >= 80:
                            return True
            
            return False
            
        except ImportError:
            return self._fallback_category_match(product_category, search_category)
    
    def _fuzzy_match_size(self, product_sizes, search_size: str) -> bool:
        """Fuzzy size matching with equivalents"""
        if not product_sizes:
            return False
            
        if isinstance(product_sizes, str):
            product_sizes = [product_sizes]
        
        search_size = str(search_size).lower().strip()
        
        try:
            from fuzzywuzzy import fuzz
            
            # Direct and fuzzy matching
            for size in product_sizes:
                size_str = str(size).lower().strip()
                
                # Exact match
                if size_str == search_size:
                    return True
                
                # Fuzzy match for size variations
                if fuzz.ratio(search_size, size_str) >= 90:
                    return True
            
            # Size equivalents with fuzzy matching
            size_equivalents = {
                "extra small": ["xs", "0", "2"],
                "small": ["s", "4", "6"],
                "medium": ["m", "8", "10"], 
                "large": ["l", "12", "14"],
                "extra large": ["xl", "16", "18"],
                "double xl": ["xxl", "2xl", "20", "22"]
            }
            
            for size_name, equivalents in size_equivalents.items():
                # Check if search matches size name
                if fuzz.partial_ratio(search_size, size_name) >= 85:
                    for product_size in product_sizes:
                        if str(product_size).lower() in equivalents:
                            return True
                
                # Check if search matches equivalent
                if search_size in equivalents:
                    for product_size in product_sizes:
                        product_size_str = str(product_size).lower()
                        if product_size_str in equivalents or fuzz.ratio(product_size_str, size_name) >= 85:
                            return True
            
            return False
            
        except ImportError:
            return self._fallback_size_match(product_sizes, search_size)
    
    def _fuzzy_match_style(self, product_style: str, search_style: str) -> bool:
        """Fuzzy style matching using FuzzyWuzzy"""
        if not product_style:
            return False
            
        try:
            from fuzzywuzzy import fuzz
            
            product_style = product_style.lower().strip()
            search_style = search_style.lower().strip()
            
            # Direct fuzzy match
            if fuzz.ratio(search_style, product_style) >= 80:
                return True
            
            # Partial match
            if fuzz.partial_ratio(search_style, product_style) >= 85:
                return True
            
            return False
            
        except ImportError:
            return self._fallback_style_match(product_style, search_style)
    
    def _fuzzy_match_material(self, product_material: str, search_material: str) -> bool:
        """Fuzzy material matching using FuzzyWuzzy"""
        if not product_material:
            return False
            
        try:
            from fuzzywuzzy import fuzz
            
            product_material = product_material.lower().strip()
            search_material = search_material.lower().strip()
            
            # Direct fuzzy match
            if fuzz.ratio(search_material, product_material) >= 80:
                return True
            
            # Partial match for material blends
            if fuzz.partial_ratio(search_material, product_material) >= 85:
                return True
            
            return False
            
        except ImportError:
            return self._fallback_material_match(product_material, search_material)
    
    # Fallback methods for when FuzzyWuzzy is not available
    def _fallback_color_match(self, product_colors, search_color: str) -> bool:
        """Fallback color matching without FuzzyWuzzy"""
        for product_color in product_colors:
            if search_color in product_color.lower() or product_color.lower() in search_color:
                return True
        return False
    
    def _fallback_brand_match(self, product_brand: str, search_brand: str) -> bool:
        """Fallback brand matching without FuzzyWuzzy"""
        return search_brand.lower() in product_brand.lower()
    
    def _fallback_category_match(self, product_category: str, search_category: str) -> bool:
        """Fallback category matching without FuzzyWuzzy"""
        return search_category.lower() in product_category.lower()
    
    def _fallback_size_match(self, product_sizes, search_size: str) -> bool:
        """Fallback size matching without FuzzyWuzzy"""
        search_size = str(search_size).lower()
        return any(str(size).lower() == search_size for size in product_sizes)
    
    def _fallback_style_match(self, product_style: str, search_style: str) -> bool:
        """Fallback style matching without FuzzyWuzzy"""
        return search_style.lower() in product_style.lower()
    
    def _fallback_material_match(self, product_material: str, search_material: str) -> bool:
        """Fallback material matching without FuzzyWuzzy"""
        return search_material.lower() in product_material.lower()
    
    async def _enrich_with_supabase_data(self, supabase_client, products: List[Dict], config) -> List[Dict]:
        """Step 3: Get full product details from Supabase"""
        
        if not products:
            return []
        
        try:
            product_ids = [p["id"] for p in products]
            
            # Query Supabase for full product details
            query = supabase_client.table(config.supabase.products_table).select("*")
            query = query.in_("id", product_ids)
            result = query.execute()
            
            # Merge vector search results with Supabase data
            supabase_data = {item["id"]: item for item in result.data}
            
            enriched = []
            for product in products:
                full_data = supabase_data.get(product["id"], {})
                enriched_product = {
                    **full_data,
                    "similarity_score": product["similarity_score"]
                }
                enriched.append(enriched_product)
            
            logger.info(f"Enriched {len(enriched)} products with Supabase data")
            return enriched
            
        except Exception as e:
            logger.error(f"Supabase enrichment failed: {e}")
            return products  # Return vector results if Supabase fails
    
    async def _llm_enhance_results(self, products: List[Dict], search_entity: Dict[str, Any], config) -> Dict[str, Any]:
        """Step 4: RAG Enhancement - LLM processes search results"""
        
        if not products:
            return await self._generate_no_results_response(search_entity, config)
        
        # Prepare context for LLM
        search_context = {
            "user_query": search_entity.get("query", ""),
            "filters_applied": {k: v for k, v in search_entity.items() if v is not None and k != "query"},
            "products_found": len(products),
            "tenant": config.tenant_name
        }
        
        # Format products for LLM
        products_text = ""
        for i, product in enumerate(products, 1):
            products_text += f"""
Product {i}:
- Name: {product.get('name', 'N/A')}
- Price: ${product.get('price', 0):.2f}
- Brand: {product.get('brand', 'N/A')}
- Category: {product.get('category', 'N/A')}
- Description: {product.get('description', 'N/A')[:150]}...
- Similarity Score: {product.get('similarity_score', 0):.2f}
"""
        
        # RAG Prompt for LLM
        rag_prompt = f"""You are an expert retail assistant for {config.tenant_name}. A customer searched for: "{search_context['user_query']}"

Applied filters: {search_context['filters_applied']}

Here are the {len(products)} most relevant products found:
{products_text}

Your task:
1. Analyze the search results and customer intent
2. Provide personalized product recommendations
3. Explain WHY these products match their needs
4. Suggest complementary items or alternatives
5. Include relevant details (price, features, availability)
6. Use a helpful, conversational tone

Generate a comprehensive product recommendation response:"""

        try:
            # Get LLM enhancement
            rag_response = await groq_client.chat_completion(
                messages=[
                    {"role": "system", "content": f"You are a knowledgeable shopping assistant for {config.tenant_name}. Help customers find the perfect products."},
                    {"role": "user", "content": rag_prompt}
                ],
                temperature=0.7,
                max_tokens=800,
                target_language="en"
            )
            
            logger.info(f"Generated RAG response for {len(products)} products")
            
            return {
                "products": products,
                "total": len(products),
                "tenant_id": config.tenant_id,
                "rag_response": rag_response,
                "search_metadata": {
                    "query": search_context["user_query"],
                    "filters_applied": search_context["filters_applied"],
                    "embedding_model": config.embedding.model_name,
                    "similarity_threshold": config.search.similarity_threshold,
                    "llm_enhanced": True
                }
            }
            
        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")
            
            # Fallback: Return structured results without LLM enhancement
            fallback_response = f"Found {len(products)} products matching your search"
            if search_entity.get("query"):
                fallback_response += f" for '{search_entity['query']}'"
            
            return {
                "products": products,
                "total": len(products),
                "tenant_id": config.tenant_id,
                "rag_response": fallback_response,
                "search_metadata": search_context,
                "llm_enhanced": False
            }
    
    async def _generate_no_results_response(self, search_entity: Dict[str, Any], config) -> Dict[str, Any]:
        """Generate helpful response when no products found"""
        
        no_results_prompt = f"""A customer at {config.tenant_name} searched for: "{search_entity.get('query', '')}"
        
Applied filters: {search_entity}

No products matched their search criteria. Generate a helpful response that:
1. Acknowledges their search
2. Suggests alternative searches or broader criteria
3. Offers to help them find similar items
4. Maintains a positive, helpful tone

Response:"""

        try:
            response = await groq_client.chat_completion(
                messages=[
                    {"role": "system", "content": f"You are a helpful shopping assistant for {config.tenant_name}."},
                    {"role": "user", "content": no_results_prompt}
                ],
                temperature=0.7,
                max_tokens=300,
                target_language="en"
            )
            
            return {
                "products": [],
                "total": 0,
                "tenant_id": config.tenant_id,
                "rag_response": response,
                "search_metadata": {"no_results": True, "original_query": search_entity}
            }
            
        except Exception as e:
            return {
                "products": [],
                "total": 0, 
                "tenant_id": config.tenant_id,
                "rag_response": "I couldn't find any products matching your search. Please try different keywords or filters.",
                "error": str(e)
            }