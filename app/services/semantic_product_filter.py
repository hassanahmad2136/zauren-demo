"""
Semantic Product Filter Service

This service provides semantic search capabilities specifically for LLM functions,
returning only the most relevant 10-20 products instead of the full inventory.
Uses both Pinecone and local embeddings for optimal performance.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from .embeddings import get_embedding_service
from .db_inventory import get_all_categories, create_nested_inventory_json
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)

class SemanticProductFilter:
    def __init__(self, auto_init_embeddings: bool = True):
        """Initialize the semantic product filter"""
        self.embedding_service = get_embedding_service()

        # Automatically ensure embeddings are generated once
        if auto_init_embeddings:
            self._ensure_embeddings_exist()

    @property
    def pinecone_index(self):
        """Get Pinecone index from embedding service"""
        return self.embedding_service.pinecone_index

    @property
    def pinecone_initialized(self):
        """Check if Pinecone is initialized in embedding service"""
        return self.embedding_service.pinecone_index is not None

    def _ensure_embeddings_exist(self):
        """Ensure embeddings are generated for all products (run only once)"""
        try:
            # Check embedding status first
            status = self.embedding_service.get_embedding_status()

            if status['status'] == 'success':
                if status['is_complete']:
                    logger.info(f"✅ Embeddings already complete: {status['products_with_embeddings']}/{status['total_products']} products")
                else:
                    logger.info(f"🔄 Generating missing embeddings: {status['products_without_embeddings']}/{status['total_products']} remaining")

                    # Generate only missing embeddings (not forcing regeneration)
                    result = self.embedding_service.generate_embeddings_for_all_products(force_regenerate=False)

                    if result['status'] == 'success':
                        if result.get('already_complete'):
                            logger.info("✅ All embeddings were already complete")
                        else:
                            logger.info(f"✅ Embedding generation result: {result['message']}")
                    else:
                        logger.warning(f"⚠️ Embedding generation had issues: {result.get('message', 'Unknown error')}")
            else:
                logger.warning(f"⚠️ Could not check embedding status: {status.get('message', 'Unknown error')}")

        except Exception as e:
            logger.warning(f"⚠️ Error during embedding initialization: {e}")

    def get_embedding_status(self) -> Dict[str, Any]:
        """Get current embedding status"""
        return self.embedding_service.get_embedding_status()

    def generate_missing_embeddings(self) -> Dict[str, Any]:
        """Generate embeddings only for products that don't have them"""
        return self.embedding_service.generate_embeddings_for_all_products(force_regenerate=False)

    def regenerate_all_embeddings(self) -> Dict[str, Any]:
        """Force regeneration of all embeddings"""
        return self.embedding_service.generate_embeddings_for_all_products(force_regenerate=True)

    def get_relevant_products_for_llm(self, user_query: str, limit: int = 15, fallback_to_all: bool = True) -> str:
        """
        Get semantically relevant products for LLM processing

        Args:
            user_query: User's message/query
            limit: Maximum number of products to return (10-30 range)
            fallback_to_all: If no relevant products found, return random sample

        Returns:
            JSON string with relevant products in nested format for LLM
        """
        try:
            # Enforce reasonable limits for LLM processing
            actual_limit = max(10, min(limit, 30))

            # Try Pinecone first if available
            if self.pinecone_initialized:
                relevant_products = self._search_with_pinecone(user_query, actual_limit)
            else:
                # Fallback to local embeddings
                relevant_products = self._search_with_local_embeddings(user_query, actual_limit)

            # If no relevant products found and fallback is enabled
            if not relevant_products and fallback_to_all:
                logger.info(f"🔄 No relevant products found for '{user_query}', using fallback selection")
                relevant_products = self._get_fallback_products(actual_limit)

            # Create nested inventory JSON with only relevant products
            if relevant_products:
                categories_result = get_all_categories()
                if categories_result['status'] == 'success':
                    filtered_inventory_json = create_nested_inventory_json(
                        categories_result['data'],
                        relevant_products
                    )

                    logger.info(f"✅ Returning {len(relevant_products)} relevant products for LLM processing")
                    return filtered_inventory_json

            # Ultimate fallback - return empty inventory
            logger.warning("⚠️ No products available for LLM processing")
            return json.dumps({"categories": []})

        except Exception as e:
            logger.error(f"❌ Error in get_relevant_products_for_llm: {e}")

            # Emergency fallback - get a small sample
            if fallback_to_all:
                return self._get_emergency_fallback()

            return json.dumps({"categories": []})

    def _format_query_as_product_json(self, user_query: str) -> str:
        """
        Format user query as a product-like JSON string for better embedding matching
        
        Args:
            user_query: Raw user query like "yellow heels" or "formal shoes"
            
        Returns:
            JSON-formatted string similar to product embeddings
        """
        import re
        
        # Extract potential product attributes from query
        query_lower = user_query.lower()
        
        # Color detection
        colors = ['black', 'white', 'brown', 'blue', 'red', 'green', 'yellow', 'gray', 'grey', 
                 'beige', 'pink', 'orange', 'purple', 'gold', 'golden', 'silver', 'maroon', 
                 'navy', 'cream', 'tan', 'fawn', 'mustard', 'chikoo', 'coffee']
        detected_colors = [color for color in colors if color in query_lower]
        
        # Product type detection
        product_types = ['shoes', 'heels', 'sandals', 'boots', 'flats', 'sneakers', 'pumps', 
                        'loafers', 'khussas', 'slippers', 'mules', 'chappal', 'footwear']
        detected_types = [ptype for ptype in product_types if ptype in query_lower]
        
        # Style detection
        styles = ['formal', 'casual', 'party', 'wedding', 'office', 'sports', 'elegant', 
                 'traditional', 'modern', 'vintage', 'classic']
        detected_styles = [style for style in styles if style in query_lower]
        
        # Material detection
        materials = ['leather', 'synthetic', 'velvet', 'fabric', 'suede', 'canvas', 'mesh']
        detected_materials = [material for material in materials if material in query_lower]
        
        # Create product-like structure
        product_query = {
            "title": user_query,
            "description": f"Looking for {user_query}",
            "colors": detected_colors,
            "materials": detected_materials,
            "styles": detected_styles,
            "product_types": detected_types,
            "sizes": [],  # Usually not specified in queries
            "category": detected_types[0] if detected_types else "footwear",
            "features": detected_styles + detected_materials,
            "search_terms": user_query
        }
        
        return json.dumps(product_query, separators=(',', ':'))

    def _search_with_pinecone(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search using Pinecone vector database"""
        try:
            if "Add to cart product_id: " in query:
                product_id = query.split("Add to cart product_id: ")[1].split()[0]

                # query this product from supabase
                from .db_inventory import get_supabase_client
                supabase = get_supabase_client()

                product_response = supabase.table('products')\
                    .select('*, categories(id, name)')\
                    .eq('id', product_id)\
                    .execute()

                if product_response.data:
                    # Inject score = 1.0 into each returned product
                    for p in product_response.data:
                        p["score"] = 1.0
                    logger.debug(f"Returning product for cart: {product_response.data}")
                    return product_response.data

                return []

        # ------- Regular Pinecone search -------
            formatted_query = self._format_query_as_product_json(query)
            logger.info(f"🔍 Formatted query for Pinecone: {formatted_query}")

            query_embedding = self.embedding_service.create_embedding(formatted_query)

            search_results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True,
                include_values=False
            )

            if search_results['matches']:
                product_ids = [match['id'] for match in search_results['matches']]
                scores = {match['id']: match['score'] for match in search_results['matches']}

                from .db_inventory import get_supabase_client
                supabase = get_supabase_client()

                products_response = supabase.table('products')\
                    .select('*, categories(id, name)')\
                    .in_('id', product_ids)\
                    .execute()

                if products_response.data:
                    sorted_products = sorted(
                        products_response.data, 
                        key=lambda p: scores.get(p['id'], 0), 
                        reverse=True
                    )
                    # Attach score from Pinecone
                    for p in sorted_products:
                        p["score"] = scores.get(p["id"], 0)

                    top_scores = [f"{p['score']:.3f}" for p in sorted_products[:3]]
                    logger.info(f"✅ Found {len(sorted_products)} products via Pinecone (scores: {top_scores})")
                    return sorted_products

            return []

        except Exception as e:
            logger.error(f"❌ Pinecone search failed: {e}")
            return []
    def _search_with_local_embeddings(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search using local embeddings system"""
        try:
            # Format query as product-like JSON for better matching
            formatted_query = self._format_query_as_product_json(query)
            logger.info(f"🔍 Formatted query for local search: {formatted_query}")
            
            # Use existing semantic search with lower threshold for broader results
            search_result = self.embedding_service.semantic_search(
                query=formatted_query,
                limit=limit,
                similarity_threshold=0.15  # Much lower threshold for broader results
            )

            if search_result['status'] == 'success' and search_result['data']:
                products = [item['product'] for item in search_result['data']]
                logger.info(f"✅ Found {len(products)} products via local embeddings")
                return products

            # If no results with low threshold, try even lower
            search_result = self.embedding_service.semantic_search(
                query=formatted_query,
                limit=limit,
                similarity_threshold=0.05  # Very low threshold as fallback
            )

            if search_result['status'] == 'success' and search_result['data']:
                products = [item['product'] for item in search_result['data']]
                logger.info(f"✅ Found {len(products)} products via fallback threshold")
                return products

            return []

        except Exception as e:
            logger.error(f"❌ Local embeddings search failed: {e}")
            return []

    def _get_fallback_products(self, limit: int) -> List[Dict[str, Any]]:
        """Get a diverse sample of products when semantic search fails"""
        try:
            from .db_inventory import get_all_products

            products_result = get_all_products(include_categories=True)

            if products_result['status'] == 'success' and products_result['data']:
                all_products = products_result['data']

                # Get a diverse sample - take products from different categories
                categories_seen = set()
                diverse_products = []

                # First pass - one product per category
                for product in all_products:
                    if len(diverse_products) >= limit:
                        break

                    category_name = product.get('categories', {}).get('name', 'unknown')
                    if category_name not in categories_seen:
                        diverse_products.append(product)
                        categories_seen.add(category_name)

                # Second pass - fill remaining slots
                for product in all_products:
                    if len(diverse_products) >= limit:
                        break

                    if product not in diverse_products:
                        diverse_products.append(product)

                logger.info(f"✅ Using {len(diverse_products)} diverse products as fallback")
                return diverse_products[:limit]

            return []

        except Exception as e:
            logger.error(f"❌ Fallback product selection failed: {e}")
            return []

    def _get_emergency_fallback(self) -> str:
        """Emergency fallback with minimal product set"""
        try:
            fallback_products = self._get_fallback_products(10)

            if fallback_products:
                categories_result = get_all_categories()
                if categories_result['status'] == 'success':
                    return create_nested_inventory_json(
                        categories_result['data'],
                        fallback_products
                    )

        except Exception as e:
            logger.error(f"❌ Emergency fallback failed: {e}")

        # Absolute final fallback
        return json.dumps({
            "categories": [{
                "id": "emergency",
                "name": "Products",
                "description": "Available products",
                "products": [{
                    "id": "unavailable",
                    "title": "Products temporarily unavailable",
                    "description": "Please try again later",
                    "regular_price": 0,
                    "colors": [],
                    "sizes": []
                }]
            }]
        })

    def sync_products_to_pinecone(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Sync all products to Pinecone vector database

        Args:
            batch_size: Number of products to process in each batch

        Returns:
            Dict with sync results
        """
        if not self.pinecone_initialized:
            return {
                'status': 'error',
                'message': 'Pinecone not initialized'
            }

        try:
            from .db_inventory import get_all_products

            # Get all products
            products_result = get_all_products(include_categories=True)

            if products_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': 'Failed to fetch products from database'
                }

            products = products_result['data']
            success_count = 0
            error_count = 0

            logger.info(f"🔄 Syncing {len(products)} products to Pinecone...")

            # Process in batches
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                vectors_to_upsert = []

                for product in batch:
                    try:
                        # Create product text and embedding
                        product_text = self.embedding_service.create_product_text(product)
                        embedding = self.embedding_service.create_embedding(product_text)

                        # Prepare vector for Pinecone
                        vector_data = {
                            'id': product['id'],
                            'values': embedding,
                            'metadata': {
                                'title': product.get('title', ''),
                                'category': product.get('categories', {}).get('name', ''),
                                'colors': product.get('colors', []),
                                'sizes': product.get('sizes', []),
                                'regular_price': product.get('regular_price', 0),
                                'product_text': product_text[:1000]  # Truncate for metadata
                            }
                        }

                        vectors_to_upsert.append(vector_data)

                    except Exception as e:
                        logger.error(f"❌ Error processing product {product.get('id')}: {e}")
                        error_count += 1

                # Upsert batch to Pinecone
                if vectors_to_upsert:
                    try:
                        self.pinecone_index.upsert(vectors=vectors_to_upsert)
                        success_count += len(vectors_to_upsert)
                        logger.info(f"✅ Synced batch {i//batch_size + 1}, {len(vectors_to_upsert)} products")

                    except Exception as e:
                        logger.error(f"❌ Failed to upsert batch to Pinecone: {e}")
                        error_count += len(vectors_to_upsert)

            result = {
                'status': 'success',
                'total_products': len(products),
                'success_count': success_count,
                'error_count': error_count,
                'message': f"Synced {success_count} products to Pinecone, {error_count} errors"
            }

            logger.info(f"✅ Pinecone sync complete: {result['message']}")
            return result

        except Exception as e:
            logger.error(f"❌ Pinecone sync failed: {e}")
            return {
                'status': 'error',
                'message': f'Pinecone sync failed: {str(e)}'
            }


# Global instance
semantic_filter = SemanticProductFilter()

def get_semantic_inventory_for_llm(user_query: str, limit: int = 15) -> str:
    """
    Convenience function to get semantic inventory for LLM functions

    Args:
        user_query: User's message/query
        limit: Maximum number of products (10-30)

    Returns:
        JSON string with relevant products
    """
    return semantic_filter.get_relevant_products_for_llm(user_query, limit)