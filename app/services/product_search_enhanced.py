"""
Enhanced Product Search Service integrating embeddings and traditional search
Replaces the old product search with semantic search capabilities
"""

import logging
from typing import Dict, List, Any, Optional
from .embeddings import get_embedding_service, search_products_semantic
from .db_inventory import search_products, get_product_details
from .price_manager import get_price_manager

logger = logging.getLogger(__name__)

class EnhancedProductSearch:
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.price_manager = get_price_manager()

    def search(self, query: str, limit: int = 15, use_semantic: bool = True) -> Dict[str, Any]:
        """
        Enhanced search that combines semantic and keyword search

        Args:
            query: Search query
            limit: Maximum number of results
            use_semantic: Whether to use semantic search

        Returns:
            Dict with search results
        """
        try:
            # Enforce maximum limit to prevent overwhelming LLM
            actual_limit = min(limit, 20)

            if use_semantic:
                # Use hybrid search (semantic + keyword)
                result = search_products_semantic(query, actual_limit)
            else:
                # Fallback to traditional keyword search
                result = search_products(query)

            # Enhance results with price information
            if result.get('status') == 'success' and result.get('data'):
                enhanced_data = []

                for item in result['data']:
                    # Handle different result structures
                    if 'product' in item:
                        product = item['product']
                        enhanced_item = item.copy()
                        enhanced_item['product']['price_info'] = self.price_manager.format_price_display(product)
                    else:
                        product = item
                        enhanced_item = item.copy()
                        enhanced_item['price_info'] = self.price_manager.format_price_display(product)

                    enhanced_data.append(enhanced_item)

                result['data'] = enhanced_data

            return result

        except Exception as e:
            logger.error(f"❌ Enhanced search failed: {e}")
            # Fallback to traditional search
            try:
                return search_products(query)
            except:
                return {
                    'status': 'error',
                    'message': 'Search failed',
                    'error': str(e),
                    'query': query
                }

    def search_by_category(self, category_name: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search products by category with enhanced results

        Args:
            category_name: Name of the category
            limit: Maximum number of results

        Returns:
            Dict with category products
        """
        try:
            # Use semantic search to find category-related products
            query = f"category:{category_name} {category_name}"
            result = self.search(query, limit)

            if result.get('status') == 'success':
                result['search_type'] = 'category'
                result['category'] = category_name

            return result

        except Exception as e:
            logger.error(f"❌ Category search failed: {e}")
            return {
                'status': 'error',
                'message': 'Category search failed',
                'error': str(e)
            }

    def search_with_filters(self, query: str, filters: Dict[str, Any], limit: int = 10) -> Dict[str, Any]:
        """
        Search with additional filters

        Args:
            query: Search query
            filters: Additional filters (price_range, colors, sizes, etc.)
            limit: Maximum number of results

        Returns:
            Dict with filtered search results
        """
        try:
            # Enhance query with filter terms
            enhanced_query = query

            # Add filter terms to search query for better semantic matching
            if filters.get('colors'):
                enhanced_query += f" {' '.join(filters['colors'])}"

            if filters.get('sizes'):
                enhanced_query += f" size {' '.join(filters['sizes'])}"

            if filters.get('materials'):
                enhanced_query += f" {' '.join(filters['materials'])}"

            if filters.get('styles'):
                enhanced_query += f" {' '.join(filters['styles'])}"

            # Perform enhanced search
            result = self.search(enhanced_query, limit * 2)  # Get more results for filtering

            if result.get('status') == 'success' and result.get('data'):
                filtered_results = []

                for item in result['data']:
                    # Extract product data
                    if 'product' in item:
                        product = item['product']
                    else:
                        product = item

                    # Apply filters
                    if not self._matches_filters(product, filters):
                        continue

                    filtered_results.append(item)

                    if len(filtered_results) >= limit:
                        break

                result['data'] = filtered_results
                result['applied_filters'] = filters

            return result

        except Exception as e:
            logger.error(f"❌ Filtered search failed: {e}")
            return {
                'status': 'error',
                'message': 'Filtered search failed',
                'error': str(e)
            }

    def _matches_filters(self, product: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if product matches the given filters

        Args:
            product: Product data
            filters: Filter criteria

        Returns:
            bool: Whether product matches filters
        """
        try:
            # Price range filter
            price_range = filters.get('price_range')
            if price_range:
                effective_price = self.price_manager.get_effective_price(product)

                if price_range.get('min') and effective_price < price_range['min']:
                    return False

                if price_range.get('max') and effective_price > price_range['max']:
                    return False

            # Color filter
            colors = filters.get('colors')
            if colors:
                product_colors = product.get('colors', [])
                if not any(color.lower() in [pc.lower() for pc in product_colors] for color in colors):
                    return False

            # Size filter
            sizes = filters.get('sizes')
            if sizes:
                available_sizes = product.get('available_sizes', [])
                if not any(size.lower() in [ps.lower() for ps in available_sizes] for size in sizes):
                    return False

            # Material filter
            materials = filters.get('materials')
            if materials:
                product_material = product.get('material', '').lower()
                if not any(material.lower() in product_material for material in materials):
                    return False

            # Style filter
            styles = filters.get('styles')
            if styles:
                product_style = product.get('style', '').lower()
                if not any(style.lower() in product_style for style in styles):
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Filter matching error: {e}")
            return True  # Include product if filter matching fails

    def get_similar_products(self, product_id: str, limit: int = 5) -> Dict[str, Any]:
        """
        Get products similar to the given product

        Args:
            product_id: ID of the reference product
            limit: Maximum number of similar products

        Returns:
            Dict with similar products
        """
        try:
            # Get product details
            product_result = get_product_details(product_id)
            if product_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': 'Product not found'
                }

            product = product_result['data']

            # Create search query from product attributes
            query_parts = []

            product_title = product.get('title') or product.get('name')
            if product_title:
                # Extract key terms from product title
                title_parts = product_title.split()[:3]  # First 3 words
                query_parts.extend(title_parts)

            if product.get('colors'):
                query_parts.extend(product['colors'][:2])  # First 2 colors

            if product.get('material'):
                query_parts.append(product['material'])

            if product.get('style'):
                query_parts.append(product['style'])

            query = ' '.join(query_parts)

            # Search for similar products
            result = self.search(query, limit + 1)  # Get one extra to exclude the original

            if result.get('status') == 'success' and result.get('data'):
                # Remove the original product from results
                similar_products = []
                for item in result['data']:
                    if 'product' in item:
                        item_product_id = item['product'].get('id')
                    else:
                        item_product_id = item.get('id')

                    if item_product_id != product_id:
                        similar_products.append(item)

                    if len(similar_products) >= limit:
                        break

                return {
                    'status': 'success',
                    'data': similar_products,
                    'reference_product_id': product_id,
                    'count': len(similar_products)
                }

            return {
                'status': 'success',
                'data': [],
                'count': 0
            }

        except Exception as e:
            logger.error(f"❌ Similar products search failed: {e}")
            return {
                'status': 'error',
                'message': 'Failed to find similar products',
                'error': str(e)
            }

# Global instance
_enhanced_search = None

def get_enhanced_search() -> EnhancedProductSearch:
    """Get global enhanced search instance"""
    global _enhanced_search
    if _enhanced_search is None:
        _enhanced_search = EnhancedProductSearch()
    return _enhanced_search

def search_products_enhanced(query: str, limit: int = 15) -> Dict[str, Any]:
    """Enhanced product search function"""
    search_service = get_enhanced_search()
    # Enforce maximum limit to prevent overwhelming LLM
    actual_limit = min(limit, 20)
    return search_service.search(query, actual_limit)