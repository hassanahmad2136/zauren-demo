"""
Product Embeddings Service for semantic search
Handles creating, storing, and searching product embeddings
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from .db_inventory import get_supabase_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

class ProductEmbeddingService:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        """
        Initialize the embedding service with a sentence transformer model

        Args:
            model_name: The name of the sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        self.pinecone_index = None
        self._load_model()
        self._initialize_pinecone()

    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"✅ Loaded embedding model: {self.model_name}")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            raise

    def _initialize_pinecone(self):
        """Initialize Pinecone client and index"""
        try:
            # Check if Pinecone is configured
            pinecone_api_key = os.getenv('PINECONE_API_KEY')
            pinecone_index_name = os.getenv('PINECONE_INDEX_NAME')

            if not pinecone_api_key or not pinecone_index_name:
                logger.warning("⚠️ Pinecone not configured - embeddings will be stored in Supabase only")
                return

            try:
                from pinecone import Pinecone, ServerlessSpec

                # Initialize Pinecone
                pc = Pinecone(api_key=pinecone_api_key)

                # Connect to existing index
                self.pinecone_index = pc.Index(pinecone_index_name)
                logger.info(f"✅ Connected to Pinecone index: {pinecone_index_name}")

            except ImportError:
                logger.warning("⚠️ Pinecone library not installed - embeddings will be stored in Supabase only")

        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Pinecone: {e} - embeddings will be stored in Supabase only")

    def create_product_text(self, product: Dict[str, Any]) -> str:
        """
        Create searchable text representation of a product

        Args:
            product: Product dictionary from database

        Returns:
            str: Formatted text for embedding
        """
        text_parts = []

        # Product name and description (handle both old and new schema)
        product_name = product.get('title') or product.get('name')
        if product_name:
            text_parts.append(f"Name: {product_name}")

        if product.get('description'):
            text_parts.append(f"Description: {product['description']}")

        # Colors and sizes
        if product.get('colors') and isinstance(product['colors'], list):
            text_parts.append(f"Colors: {', '.join(product['colors'])}")

        if product.get('sizes') and isinstance(product['sizes'], list):
            text_parts.append(f"Sizes: {', '.join(product['sizes'])}")

        # Category information
        if product.get('categories') and product['categories'].get('name'):
            text_parts.append(f"Category: {product['categories']['name']}")

        # Additional attributes for shoes/products
        if product.get('material'):
            text_parts.append(f"Material: {product['material']}")

        if product.get('style'):
            text_parts.append(f"Style: {product['style']}")

        if product.get('brand'):
            text_parts.append(f"Brand: {product['brand']}")

        # Extract additional info from product_sections if available (new schema)
        if product.get('product_sections') and isinstance(product['product_sections'], dict):
            for key, value in product['product_sections'].items():
                text_parts.append(f"{key}: {value}")

        # Price information (handle both schemas)
        regular_price = product.get('regular_price') or product.get('unit_price') or product.get('fixed_price')
        if regular_price:
            price_text = f"Regular Price: {regular_price}"
            sale_price = product.get('sale_price')
            if sale_price and sale_price != regular_price:
                price_text += f", Sale Price: {sale_price}"
            text_parts.append(price_text)

        return " | ".join(text_parts)

    def create_embedding(self, text: str) -> List[float]:
        """
        Create embedding vector for given text

        Args:
            text: Text to embed

        Returns:
            List[float]: Embedding vector
        """
        if not self.model:
            raise ValueError("Model not loaded")

        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Failed to create embedding: {e}")
            raise

    def embedding_exists(self, product_id: str) -> bool:
        """
        Check if embedding already exists for a product

        Args:
            product_id: ID of the product to check

        Returns:
            bool: True if embedding exists, False otherwise
        """
        try:
            supabase = get_supabase_client()

            response = supabase.table('product_embeddings')\
                .select('product_id')\
                .eq('product_id', product_id)\
                .execute()

            return len(response.data) > 0

        except Exception as e:
            logger.error(f"❌ Failed to check embedding existence for product {product_id}: {e}")
            return False

    def store_product_embedding(self, product_id: str, product_text: str, embedding: List[float], force_update: bool = False) -> bool:
        """
        Store product embedding in Pinecone using upsert to prevent duplicates

        Args:
            product_id: ID of the product
            product_text: Text representation of the product (not used, fetched from DB)
            embedding: Embedding vector
            force_update: If True, will update existing embeddings

        Returns:
            bool: Success status
        """
        try:
            if not force_update and self.pinecone_index:
                # Check if embedding already exists in Pinecone
                try:
                    existing = self.pinecone_index.fetch(ids=[product_id])

                    # Handle newer Pinecone API response structure
                    if hasattr(existing, 'vectors') and product_id in existing.vectors:
                        logger.info(f"⏭️  Embedding already exists for product {product_id}, skipping")
                        return True
                    elif hasattr(existing, 'get') and existing.get('vectors') and product_id in existing.get('vectors', {}):
                        logger.info(f"⏭️  Embedding already exists for product {product_id}, skipping")
                        return True
                except Exception as fetch_error:
                    logger.warning(f"⚠️ Could not check existing embedding for product {product_id}: {fetch_error}")
                    # Continue with upsert since we couldn't verify

            # Fetch complete product data from Supabase
            from .db_inventory import get_supabase_client
            supabase = get_supabase_client()
            
            product_response = supabase.table('products')\
                .select('*')\
                .eq('id', product_id)\
                .execute()
            
            if not product_response.data:
                logger.error(f"❌ Product {product_id} not found in Supabase")
                return False
            
            product_data = product_response.data[0]
            
            # Prepare metadata using the same method as your existing code
            metadata = self._prepare_metadata(product_data)

            # Store in Pinecone only
            if not self.pinecone_index:
                logger.error(f"❌ Pinecone not available for storing embedding for product {product_id}")
                return False

            # Upsert into Pinecone
            self.pinecone_index.upsert(
                vectors=[
                    {
                        'id': str(product_id),
                        'values': embedding,
                        'metadata': metadata
                    }
                ]
            )

            storage_location = "Pinecone"
            if force_update:
                logger.info(f"✅ Updated embedding for product {product_id} in {storage_location}")
            else:
                logger.info(f"✅ Stored new embedding for product {product_id} in {storage_location}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to store embedding for product {product_id}: {e}")
            return False

    def _prepare_metadata(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata for Pinecone storage (same as your existing method)"""
        metadata = {}

        # Include relevant fields, handling None values
        fields_to_include = [
            'url', 'title', 'price', 'regular_price', 'sale_price',
            'discount_percentage', 'is_on_sale', 'sku', 'description',
            'category_id', 'created_at'
        ]

        for field in fields_to_include:
            value = product.get(field)
            if value is not None:
                # Convert datetime to string if needed
                if isinstance(value, datetime):
                    metadata[field] = value.isoformat()
                else:
                    metadata[field] = str(value)  # Ensure all values are strings for Pinecone

        # Handle JSON fields using the same parsing method
        metadata['colors'] = self._parse_json_field(product.get('colors', []))
        metadata['sizes'] = self._parse_json_field(product.get('sizes', []))
        metadata['available_sizes'] = self._parse_json_field(product.get('available_sizes', []))
        metadata['out_of_stock_sizes'] = self._parse_json_field(product.get('out_of_stock_sizes', []))
        
        # Add embedding model info
        metadata['embedding_model'] = self.model_name

        return metadata

    def _parse_json_field(self, field_value: Any, default: List = None) -> List:
        """Safely parse JSON fields with fallback (same as your existing method)"""
        if default is None:
            default = []

        if not field_value:
            return default

        if isinstance(field_value, list):
            return field_value

        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON: {field_value}")
                return default

        return default

    def get_products_without_embeddings(self) -> List[str]:
        """
        Get list of product IDs that don't have embeddings yet.
        Checks Pinecone if available, falls back to Supabase.

        Returns:
            List of product IDs missing embeddings
        """
        try:
            from .db_inventory import get_all_products

            # Get all product IDs
            products_result = get_all_products()
            if products_result['status'] != 'success':
                return []

            all_product_ids = {str(product['id']) for product in products_result['data']}

            # Check Pinecone first if available
            if self.pinecone_index:
                try:
                    # Query Pinecone for existing embeddings in batches
                    existing_embeddings = set()
                    batch_size = 100
                    product_id_list = list(all_product_ids)

                    for i in range(0, len(product_id_list), batch_size):
                        batch_ids = product_id_list[i:i + batch_size]
                        response = self.pinecone_index.fetch(ids=batch_ids)

                        # Handle different Pinecone API response formats
                        if hasattr(response, 'vectors'):
                            existing_embeddings.update(response.vectors.keys())
                        elif hasattr(response, 'get') and response.get('vectors'):
                            existing_embeddings.update(response.get('vectors', {}).keys())

                    # Return products without embeddings
                    missing_embeddings = list(all_product_ids - existing_embeddings)
                    logger.info(f"📊 Pinecone check: {len(all_product_ids)} total products, {len(existing_embeddings)} have embeddings, {len(missing_embeddings)} missing")
                    return missing_embeddings

                except Exception as pinecone_error:
                    logger.warning(f"⚠️ Failed to check Pinecone, falling back to Supabase: {pinecone_error}")

            # Fallback to Supabase check
            supabase = get_supabase_client()
            embeddings_response = supabase.table('product_embeddings')\
                .select('product_id')\
                .execute()

            existing_embeddings = {str(row['product_id']) for row in embeddings_response.data}

            # Return products without embeddings
            missing_embeddings = list(all_product_ids - existing_embeddings)
            logger.info(f"📊 Supabase check: {len(all_product_ids)} total products, {len(existing_embeddings)} have embeddings, {len(missing_embeddings)} missing")
            return missing_embeddings

        except Exception as e:
            logger.error(f"❌ Failed to get products without embeddings: {e}")
            return []

    def get_embedding_status(self) -> Dict[str, Any]:
        """
        Get the current status of embeddings generation.
        Checks Pinecone if available, falls back to Supabase.

        Returns:
            Dict with embedding statistics
        """
        try:
            from .db_inventory import get_all_products

            # Get total products count
            products_result = get_all_products()
            if products_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': 'Failed to fetch products'
                }

            total_products = len(products_result['data'])
            all_product_ids = {str(product['id']) for product in products_result['data']}

            # Check Pinecone first if available
            if self.pinecone_index:
                try:
                    # Query Pinecone for existing embeddings in batches
                    existing_embeddings = set()
                    batch_size = 100
                    product_id_list = list(all_product_ids)

                    for i in range(0, len(product_id_list), batch_size):
                        batch_ids = product_id_list[i:i + batch_size]
                        response = self.pinecone_index.fetch(ids=batch_ids)

                        # Handle different Pinecone API response formats
                        if hasattr(response, 'vectors'):
                            existing_embeddings.update(response.vectors.keys())
                        elif hasattr(response, 'get') and response.get('vectors'):
                            existing_embeddings.update(response.get('vectors', {}).keys())

                    embeddings_count = len(existing_embeddings)

                    return {
                        'status': 'success',
                        'total_products': total_products,
                        'products_with_embeddings': embeddings_count,
                        'products_without_embeddings': total_products - embeddings_count,
                        'completion_percentage': round((embeddings_count / total_products) * 100, 2) if total_products > 0 else 100,
                        'is_complete': embeddings_count >= total_products,
                        'source': 'pinecone'
                    }

                except Exception as pinecone_error:
                    logger.warning(f"⚠️ Failed to check Pinecone status, falling back to Supabase: {pinecone_error}")

            # Fallback to Supabase check
            supabase = get_supabase_client()
            embeddings_response = supabase.table('product_embeddings')\
                .select('product_id', count='exact')\
                .execute()

            embeddings_count = embeddings_response.count

            return {
                'status': 'success',
                'total_products': total_products,
                'products_with_embeddings': embeddings_count,
                'products_without_embeddings': total_products - embeddings_count,
                'completion_percentage': round((embeddings_count / total_products) * 100, 2) if total_products > 0 else 100,
                'is_complete': embeddings_count >= total_products,
                'source': 'supabase'
            }

        except Exception as e:
            logger.error(f"❌ Failed to get embedding status: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get embedding status: {str(e)}'
            }

    def generate_embeddings_for_all_products(self, force_regenerate: bool = False, batch_size: int = 50) -> Dict[str, Any]:
        """
        Generate and store embeddings for all products in the database (only once)

        Args:
            force_regenerate: If True, regenerate embeddings even if they exist
            batch_size: Number of products to process in each batch

        Returns:
            Dict with success/failure counts
        """
        try:
            # Check current status first
            status = self.get_embedding_status()
            if status['status'] != 'success':
                return status

            if not force_regenerate and status['is_complete']:
                logger.info(f"✅ All embeddings already exist ({status['products_with_embeddings']}/{status['total_products']})")
                return {
                    'status': 'success',
                    'message': 'All embeddings already exist',
                    'total_products': status['total_products'],
                    'success_count': status['products_with_embeddings'],
                    'error_count': 0,
                    'skipped_count': status['products_with_embeddings'],
                    'already_complete': True
                }

            from .db_inventory import get_all_products

            # Get products that need embeddings
            if force_regenerate:
                products_result = get_all_products(include_categories=True)
                if products_result['status'] != 'success':
                    return {
                        'status': 'error',
                        'message': 'Failed to fetch products',
                        'error': products_result.get('error')
                    }
                products_to_process = products_result['data']
            else:
                # Get only products without embeddings
                missing_product_ids = self.get_products_without_embeddings()
                if not missing_product_ids:
                    logger.info("✅ All products already have embeddings")
                    return {
                        'status': 'success',
                        'message': 'All products already have embeddings',
                        'total_products': status['total_products'],
                        'success_count': 0,
                        'error_count': 0,
                        'skipped_count': status['products_with_embeddings'],
                        'already_complete': True
                    }

                # Fetch only missing products
                supabase = get_supabase_client()
                products_response = supabase.table('products')\
                    .select('*, categories(id, name)')\
                    .in_('id', missing_product_ids)\
                    .execute()

                if not products_response.data:
                    return {
                        'status': 'error',
                        'message': 'Failed to fetch missing products'
                    }

                products_to_process = products_response.data

            success_count = 0
            error_count = 0
            skipped_count = 0
            total_products = len(products_to_process)

            logger.info(f"🔄 Processing {total_products} products for embeddings in batches of {batch_size} (force_regenerate={force_regenerate})...")

            # Process in batches to improve performance
            for i in range(0, total_products, batch_size):
                batch = products_to_process[i:i + batch_size]
                batch_success = 0
                batch_errors = 0

                logger.info(f"🔄 Processing batch {i//batch_size + 1}/{(total_products + batch_size - 1)//batch_size} ({len(batch)} products)")

                for product in batch:
                    try:
                        # Create text representation
                        product_text = self.create_product_text(product)

                        # Create embedding
                        embedding = self.create_embedding(product_text)

                        # Store embedding using the improved method
                        if self.store_product_embedding(product['id'], product_text, embedding, force_update=force_regenerate):
                            success_count += 1
                            batch_success += 1
                        else:
                            error_count += 1
                            batch_errors += 1

                    except Exception as e:
                        logger.error(f"❌ Error processing product {product.get('id', 'unknown')}: {e}")
                        error_count += 1
                        batch_errors += 1

                logger.info(f"✅ Batch {i//batch_size + 1} complete: {batch_success} success, {batch_errors} errors")

            result = {
                'status': 'success',
                'total_products': total_products,
                'success_count': success_count,
                'error_count': error_count,
                'skipped_count': skipped_count,
                'message': f"Processed {total_products} products: {success_count} new, {skipped_count} skipped, {error_count} errors"
            }

            logger.info(f"✅ Embedding generation complete: {result['message']}")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to generate embeddings: {e}")
            return {
                'status': 'error',
                'message': 'Failed to generate embeddings',
                'error': str(e)
            }

    def semantic_search(self, query: str, limit: int = 15, similarity_threshold: float = 0.3) -> Dict[str, Any]:
        """
        Perform semantic search for products using optimized database query

        Args:
            query: Search query
            limit: Maximum number of results (capped at 20 to prevent overwhelming LLM)
            similarity_threshold: Minimum similarity score (0.3 for broader results)

        Returns:
            Dict with search results
        """
        try:
            # Enforce maximum limit to prevent overwhelming LLM
            actual_limit = min(limit, 20)

            # Create embedding for query
            query_embedding = self.create_embedding(query)

            # Search in database using cosine similarity with optimized query
            supabase = get_supabase_client()

            # Use the RPC function defined in the database schema
            try:
                # Ensure the embedding is properly formatted as a list
                if isinstance(query_embedding, np.ndarray):
                    query_embedding = query_embedding.tolist()

                response = supabase.rpc('search_products_by_embedding', {
                    'query_embedding': query_embedding,
                    'match_threshold': similarity_threshold,
                    'match_count': actual_limit
                }).execute()

                if response.data:
                    # Get full product details for matching products in a single query
                    product_ids = [item['product_id'] for item in response.data]

                    if product_ids:
                        products_response = supabase.table('products')\
                            .select('*, categories(id, name, description)')\
                            .in_('id', product_ids)\
                            .execute()

                        # Create a mapping for quick lookup
                        similarity_map = {item['product_id']: item['similarity'] for item in response.data}
                        product_map = {product['id']: product for product in products_response.data}

                        # Build results maintaining the similarity order
                        results = []
                        for item in response.data:  # This is already sorted by similarity
                            product_id = item['product_id']
                            if product_id in product_map:
                                results.append({
                                    'product': product_map[product_id],
                                    'similarity': item['similarity']
                                })

                        logger.info(f"✅ Found {len(results)} products for query '{query}' (similarity > {similarity_threshold})")

                        return {
                            'status': 'success',
                            'data': results,
                            'query': query,
                            'count': len(results),
                            'similarity_threshold': similarity_threshold
                        }

            except Exception as rpc_error:
                logger.warning(f"⚠️ RPC search failed, using manual cosine similarity: {rpc_error}")

                # Import numpy at the beginning of fallback to avoid scoping issues
                import numpy as np
                from numpy.linalg import norm

                # Fallback: Manual cosine similarity search using raw SQL
                try:
                    # Convert embedding to list format if it's numpy array
                    if hasattr(query_embedding, 'tolist'):
                        embedding_list = query_embedding.tolist()
                    else:
                        embedding_list = query_embedding

                    # Manual similarity search using PostgREST
                    # Get all embeddings and calculate similarity on the client side
                    embeddings_response = supabase.table('product_embeddings')\
                        .select('product_id, embedding')\
                        .execute()

                    if not embeddings_response.data:
                        return {
                            'status': 'success',
                            'data': [],
                            'query': query,
                            'count': 0,
                            'similarity_threshold': similarity_threshold,
                            'message': 'No embeddings found in database'
                        }

                    # Calculate cosine similarities manually
                    similarities = []
                    query_vec = np.array(embedding_list)

                    for row in embeddings_response.data:
                        if row['embedding'] and len(row['embedding']) == len(embedding_list):
                            product_vec = np.array(row['embedding'])
                            # Cosine similarity calculation
                            similarity = np.dot(query_vec, product_vec) / (norm(query_vec) * norm(product_vec))

                            if similarity > similarity_threshold:
                                similarities.append({
                                    'product_id': row['product_id'],
                                    'similarity': float(similarity)
                                })

                    # Sort by similarity (descending) and limit results
                    similarities.sort(key=lambda x: x['similarity'], reverse=True)
                    similarities = similarities[:actual_limit]

                    if similarities:
                        # Get product details
                        product_ids = [item['product_id'] for item in similarities]
                        products_response = supabase.table('products')\
                            .select('*, categories(id, name, description)')\
                            .in_('id', product_ids)\
                            .execute()

                        # Create similarity mapping
                        similarity_map = {item['product_id']: item['similarity'] for item in similarities}
                        product_map = {product['id']: product for product in products_response.data}

                        # Build results maintaining the similarity order
                        results = []
                        for item in similarities:
                            product_id = item['product_id']
                            if product_id in product_map:
                                results.append({
                                    'product': product_map[product_id],
                                    'similarity': item['similarity']
                                })

                        logger.info(f"✅ Manual search found {len(results)} products for query '{query}'")

                        return {
                            'status': 'success',
                            'data': results,
                            'query': query,
                            'count': len(results),
                            'similarity_threshold': similarity_threshold,
                            'search_method': 'manual_fallback'
                        }

                except Exception as fallback_error:
                    logger.error(f"❌ Fallback search also failed: {fallback_error}")
                    return {
                        'status': 'error',
                        'message': 'All search methods failed',
                        'error': str(fallback_error),
                        'query': query
                    }

            # No results found
            logger.info(f"🔍 No products found for query '{query}' with similarity > {similarity_threshold}")
            return {
                'status': 'success',
                'data': [],
                'query': query,
                'count': 0,
                'similarity_threshold': similarity_threshold
            }

        except Exception as e:
            logger.error(f"❌ Semantic search failed for query '{query}': {e}")
            return {
                'status': 'error',
                'message': 'Semantic search failed',
                'error': str(e),
                'query': query
            }

    def hybrid_search(self, query: str, limit: int = 15) -> Dict[str, Any]:
        """
        Combine semantic search with traditional keyword search

        Args:
            query: Search query
            limit: Maximum number of results (capped at 20)

        Returns:
            Dict with combined search results
        """
        try:
            # Enforce maximum limit
            actual_limit = min(limit, 20)

            # Perform semantic search
            semantic_results = self.semantic_search(query, actual_limit)

            # Perform traditional keyword search
            from .db_inventory import search_products
            keyword_results = search_products(query)

            if semantic_results['status'] == 'success' and keyword_results['status'] == 'success':
                # Combine and deduplicate results
                combined_products = {}

                # Add semantic results with their scores
                for item in semantic_results['data']:
                    product_id = item['product']['id']
                    combined_products[product_id] = {
                        'product': item['product'],
                        'semantic_score': item['similarity'],
                        'keyword_match': False
                    }

                # Add keyword results
                for product in keyword_results['data']:
                    product_id = product['id']
                    if product_id in combined_products:
                        combined_products[product_id]['keyword_match'] = True
                    else:
                        combined_products[product_id] = {
                            'product': product,
                            'semantic_score': 0.0,
                            'keyword_match': True
                        }

                # Calculate combined score
                results = []
                for product_id, data in combined_products.items():
                    combined_score = data['semantic_score']
                    if data['keyword_match']:
                        combined_score += 0.2  # Boost for keyword match

                    results.append({
                        'product': data['product'],
                        'semantic_score': data['semantic_score'],
                        'keyword_match': data['keyword_match'],
                        'combined_score': combined_score
                    })

                # Sort by combined score
                results.sort(key=lambda x: x['combined_score'], reverse=True)
                results = results[:actual_limit]

                return {
                    'status': 'success',
                    'data': results,
                    'query': query,
                    'count': len(results)
                }

            # Fallback to whichever search worked
            if semantic_results['status'] == 'success':
                return semantic_results

            return keyword_results

        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            return {
                'status': 'error',
                'message': 'Hybrid search failed',
                'error': str(e),
                'query': query
            }

# Global instance with thread-safe singleton
_embedding_service = None
_embedding_service_lock = None

def get_embedding_service() -> ProductEmbeddingService:
    """Get global embedding service instance (thread-safe singleton)"""
    global _embedding_service, _embedding_service_lock

    if _embedding_service is None:
        # Import threading only when needed
        import threading

        # Initialize lock if not already done
        if _embedding_service_lock is None:
            _embedding_service_lock = threading.Lock()

        # Double-checked locking pattern
        with _embedding_service_lock:
            if _embedding_service is None:
                logger.info("🔄 Creating singleton ProductEmbeddingService instance")
                _embedding_service = ProductEmbeddingService()
                logger.info("✅ ProductEmbeddingService singleton created")

    return _embedding_service

def _reset_embedding_service():
    """Reset the singleton instance (for testing purposes only)"""
    global _embedding_service
    _embedding_service = None
    logger.warning("⚠️ ProductEmbeddingService singleton has been reset")

def initialize_embeddings() -> Dict[str, Any]:
    """Initialize embeddings for all products"""
    service = get_embedding_service()
    return service.generate_embeddings_for_all_products()

def search_products_semantic(query: str, limit: int = 15) -> Dict[str, Any]:
    """Search products using semantic similarity"""
    service = get_embedding_service()
    # Enforce maximum limit to prevent overwhelming LLM
    actual_limit = min(limit, 20)
    return service.hybrid_search(query, actual_limit)