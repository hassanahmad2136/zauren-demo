"""
Price Management Service for ECS Shoe Store
Handles regular pricing, sale pricing, and price calculations
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from .db_inventory import get_supabase_client, get_product_details

logger = logging.getLogger(__name__)

class PriceManager:
    def __init__(self):
        self.supabase = get_supabase_client()

    def get_effective_price(self, product: Dict[str, Any]) -> float:
        """
        Get the effective price for a product (sale price if available, otherwise regular price)

        Args:
            product: Product dictionary from database

        Returns:
            float: Effective price
        """
        try:
            sale_price = product.get('sale_price')
            regular_price = product.get('regular_price', 0)

            # If sale price exists and is not None, use it
            if sale_price is not None and sale_price > 0:
                return float(sale_price)

            return float(regular_price)

        except (ValueError, TypeError):
            logger.warning(f"Invalid price data for product {product.get('id', 'unknown')}")
            return 0.0

    def calculate_discount_percentage(self, product: Dict[str, Any]) -> Optional[float]:
        """
        Calculate discount percentage if product is on sale

        Args:
            product: Product dictionary from database

        Returns:
            Optional[float]: Discount percentage (0-100) or None if not on sale
        """
        try:
            sale_price = product.get('sale_price')
            regular_price = product.get('regular_price')

            if not sale_price or not regular_price:
                return None

            if sale_price >= regular_price:
                return None

            discount_percentage = ((regular_price - sale_price) / regular_price) * 100
            return round(discount_percentage, 1)

        except (ValueError, TypeError, ZeroDivisionError):
            return None

    def format_price_display(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format price display information for a product

        Args:
            product: Product dictionary from database

        Returns:
            Dict with formatted price information
        """
        try:
            regular_price = product.get('regular_price', 0)
            sale_price = product.get('sale_price')

            effective_price = self.get_effective_price(product)
            discount_percentage = self.calculate_discount_percentage(product)

            result = {
                'effective_price': effective_price,
                'regular_price': regular_price,
                'is_on_sale': sale_price is not None and sale_price < regular_price,
                'currency': 'PKR'  # Pakistani Rupee
            }

            if result['is_on_sale']:
                result.update({
                    'sale_price': sale_price,
                    'discount_percentage': discount_percentage,
                    'savings': regular_price - sale_price
                })

            return result

        except Exception as e:
            logger.error(f"Error formatting price display: {e}")
            return {
                'effective_price': 0,
                'regular_price': 0,
                'is_on_sale': False,
                'currency': 'PKR'
            }

    def get_price_display_text(self, product: Dict[str, Any], include_discount: bool = True) -> str:
        """
        Get formatted price display text

        Args:
            product: Product dictionary from database
            include_discount: Whether to include discount information

        Returns:
            str: Formatted price text
        """
        try:
            price_info = self.format_price_display(product)

            if price_info['is_on_sale'] and include_discount:
                return f"PKR {price_info['sale_price']:,} (was PKR {price_info['regular_price']:,} - {price_info['discount_percentage']}% off)"
            else:
                return f"PKR {price_info['effective_price']:,}"

        except Exception as e:
            logger.error(f"Error generating price display text: {e}")
            return "Price unavailable"

    def calculate_cart_total(self, cart_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate total price for cart items

        Args:
            cart_items: List of cart items with product info

        Returns:
            Dict with cart total information
        """
        try:
            subtotal = 0
            total_savings = 0
            item_count = 0

            for item in cart_items:
                quantity = item.get('quantity', 0)
                item_price = item.get('price', 0)

                item_total = quantity * item_price
                subtotal += item_total
                item_count += quantity

                # Calculate savings if this was a sale item
                product_id = item.get('product_id')
                if product_id:
                    product_result = get_product_details(product_id)
                    if product_result['status'] == 'success':
                        product = product_result['data']
                        regular_price = product.get('regular_price', 0)
                        sale_price = product.get('sale_price')

                        if sale_price and sale_price < regular_price:
                            item_savings = (regular_price - sale_price) * quantity
                            total_savings += item_savings

            return {
                'subtotal': subtotal,
                'total_savings': total_savings,
                'item_count': item_count,
                'currency': 'PKR',
                'formatted_subtotal': f"PKR {subtotal:,}",
                'formatted_savings': f"PKR {total_savings:,}" if total_savings > 0 else None
            }

        except Exception as e:
            logger.error(f"Error calculating cart total: {e}")
            return {
                'subtotal': 0,
                'total_savings': 0,
                'item_count': 0,
                'currency': 'PKR',
                'formatted_subtotal': "PKR 0",
                'formatted_savings': None
            }

    def get_products_on_sale(self, category_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Get products that are currently on sale

        Args:
            category_id: Optional category filter
            limit: Maximum number of results

        Returns:
            Dict with sale products
        """
        try:
            query = self.supabase.table('products')\
                .select('*, categories(id, name)')\
                .not_.is_('sale_price', 'null')\
                .limit(limit)

            if category_id:
                query = query.eq('category_id', category_id)

            response = query.execute()

            if response.data:
                # Filter to ensure sale_price < regular_price
                sale_products = []
                for product in response.data:
                    sale_price = product.get('sale_price')
                    regular_price = product.get('regular_price', 0)

                    if sale_price and sale_price < regular_price:
                        product['price_info'] = self.format_price_display(product)
                        sale_products.append(product)

                return {
                    'status': 'success',
                    'data': sale_products,
                    'count': len(sale_products)
                }

            return {
                'status': 'success',
                'data': [],
                'count': 0
            }

        except Exception as e:
            logger.error(f"Error fetching sale products: {e}")
            return {
                'status': 'error',
                'message': 'Failed to fetch sale products',
                'error': str(e)
            }

    def apply_bulk_discount(self, product_ids: List[str], discount_percentage: float, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Apply discount to multiple products (admin function)

        Args:
            product_ids: List of product IDs
            discount_percentage: Discount percentage (0-100)
            end_date: Optional end date for the sale

        Returns:
            Dict with operation results
        """
        try:
            if not 0 <= discount_percentage <= 100:
                return {
                    'status': 'error',
                    'message': 'Invalid discount percentage'
                }

            updated_products = []
            errors = []

            for product_id in product_ids:
                try:
                    # Get current product
                    product_result = get_product_details(product_id)
                    if product_result['status'] != 'success':
                        errors.append(f"Product {product_id} not found")
                        continue

                    product = product_result['data']
                    regular_price = product.get('regular_price', 0)

                    if regular_price <= 0:
                        errors.append(f"Invalid regular price for product {product_id}")
                        continue

                    # Calculate sale price
                    discount_amount = regular_price * (discount_percentage / 100)
                    sale_price = regular_price - discount_amount

                    # Update product
                    update_data = {
                        'sale_price': round(sale_price, 2)
                    }

                    if end_date:
                        update_data['sale_end_date'] = end_date

                    response = self.supabase.table('products')\
                        .update(update_data)\
                        .eq('id', product_id)\
                        .execute()

                    updated_products.append({
                        'product_id': product_id,
                        'regular_price': regular_price,
                        'sale_price': sale_price,
                        'discount_percentage': discount_percentage
                    })

                except Exception as e:
                    errors.append(f"Error updating product {product_id}: {str(e)}")

            return {
                'status': 'success',
                'updated_count': len(updated_products),
                'error_count': len(errors),
                'updated_products': updated_products,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error applying bulk discount: {e}")
            return {
                'status': 'error',
                'message': 'Failed to apply bulk discount',
                'error': str(e)
            }

# Global instance
_price_manager = None

def get_price_manager() -> PriceManager:
    """Get global price manager instance"""
    global _price_manager
    if _price_manager is None:
        _price_manager = PriceManager()
    return _price_manager

def get_effective_price(product: Dict[str, Any]) -> float:
    """Get effective price for a product"""
    manager = get_price_manager()
    return manager.get_effective_price(product)

def format_price_display(product: Dict[str, Any]) -> Dict[str, Any]:
    """Format price display for a product"""
    manager = get_price_manager()
    return manager.format_price_display(product)