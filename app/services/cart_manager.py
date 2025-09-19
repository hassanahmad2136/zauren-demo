"""
Enhanced Cart Management Service for ECS Shoe Store
Handles product variants with colors and sizes
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from .db_inventory import get_supabase_client, get_product_details

logger = logging.getLogger(__name__)

class CartManager:
    def __init__(self):
        self.supabase = get_supabase_client()

    def create_cart_item_key(self, product_name: str, color: str, size: str) -> str:
        """
        Create a unique key for cart items based on product name, color, and size

        Args:
            product_name: Name of the product
            color: Selected color
            size: Selected size

        Returns:
            str: Unique key for the cart item
        """
        return f"{product_name.lower().strip()}|{color.lower().strip()}|{size.lower().strip()}"

    def parse_cart_item_key(self, key: str) -> Dict[str, str]:
        """
        Parse cart item key back to components

        Args:
            key: Cart item key

        Returns:
            Dict with product_name, color, size
        """
        try:
            parts = key.split('|')
            if len(parts) == 3:
                return {
                    'product_name': parts[0],
                    'color': parts[1],
                    'size': parts[2]
                }
        except:
            pass

        # Fallback for old cart format
        return {
            'product_name': key,
            'color': '',
            'size': ''
        }

    def add_to_cart(self, cart_json: str, product_id: str, product_name: str, color: str, size: str, quantity: int = 1) -> Dict[str, Any]:
        """
        Add a product variant to the cart

        Args:
            cart_json: Current cart as JSON string
            product_id: Product ID
            product_name: Product name
            color: Selected color
            size: Selected size
            quantity: Quantity to add

        Returns:
            Dict with updated cart and status
        """
        try:
            # Parse existing cart
            cart = json.loads(cart_json) if cart_json else {}
            logger.debug(f"Current cart: {cart}")
            # Get product details to validate variant
            product_result = get_product_details(product_id)
            if product_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': 'Product not found',
                    'cart': cart_json
                }

            product = product_result['data']

            # Validate color and size availability
            available_colors = product.get('colors', [])
            available_sizes = product.get('available_sizes', [])

            if color and color not in available_colors:
                return {
                    'status': 'error',
                    'message': f'Color "{color}" not available for {product_name}',
                    'available_colors': available_colors,
                    'cart': cart_json
                }

            if size and size not in available_sizes:
                return {
                    'status': 'error',
                    'message': f'Size "{size}" not available for {product_name}',
                    'available_sizes': available_sizes,
                    'cart': cart_json
                }

            # Create cart item key
            cart_key = self.create_cart_item_key(product_name, color, size)

            # Determine price (use sale_price if available, otherwise regular_price)
            price = product.get('sale_price') or product.get('regular_price', 0)

            # Add to cart or update quantity
            if cart_key in cart:
                cart[cart_key]['quantity'] += quantity
            else:
                cart[cart_key] = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'color': color,
                    'size': size,
                    'quantity': quantity,
                    'price': price,
                    'images': product.get('images', [])
                }

            return {
                'status': 'success',
                'message': f'Added {quantity} x {product_name} ({color}, {size}) to cart',
                'cart': json.dumps(cart),
                'cart_item': cart[cart_key]
            }

        except Exception as e:
            logger.error(f"❌ Error adding to cart: {e}")
            return {
                'status': 'error',
                'message': 'Failed to add item to cart',
                'error': str(e),
                'cart': cart_json
            }

    def remove_from_cart(self, cart_json: str, product_name: str, color: str = '', size: str = '', quantity: Optional[int] = None) -> Dict[str, Any]:
        """
        Remove a product variant from the cart

        Args:
            cart_json: Current cart as JSON string
            product_name: Product name
            color: Color to remove (optional for partial match)
            size: Size to remove (optional for partial match)
            quantity: Specific quantity to remove (None = remove all)

        Returns:
            Dict with updated cart and status
        """
        try:
            cart = json.loads(cart_json) if cart_json else {}

            if not cart:
                return {
                    'status': 'error',
                    'message': 'Cart is empty',
                    'cart': cart_json
                }

            # Find matching cart items
            matching_keys = []
            for cart_key in cart.keys():
                item_info = self.parse_cart_item_key(cart_key)

                # Check if product name matches
                if item_info['product_name'].lower() == product_name.lower():
                    # If color and size are specified, they must match
                    if color and item_info['color'].lower() != color.lower():
                        continue
                    if size and item_info['size'].lower() != size.lower():
                        continue
                    matching_keys.append(cart_key)

            if not matching_keys:
                return {
                    'status': 'error',
                    'message': f'Item not found in cart: {product_name}' + (f' ({color}, {size})' if color or size else ''),
                    'cart': cart_json
                }

            removed_items = []

            # Remove or reduce quantity for matching items
            for cart_key in matching_keys:
                if quantity is None:
                    # Remove all
                    removed_items.append(cart[cart_key].copy())
                    del cart[cart_key]
                else:
                    # Reduce quantity
                    if cart[cart_key]['quantity'] > quantity:
                        cart[cart_key]['quantity'] -= quantity
                        removed_items.append({
                            **cart[cart_key],
                            'quantity': quantity
                        })
                    else:
                        # Remove entire item if quantity to remove >= current quantity
                        removed_items.append(cart[cart_key].copy())
                        del cart[cart_key]

            return {
                'status': 'success',
                'message': f'Removed {len(removed_items)} item(s) from cart',
                'cart': json.dumps(cart),
                'removed_items': removed_items
            }

        except Exception as e:
            logger.error(f"❌ Error removing from cart: {e}")
            return {
                'status': 'error',
                'message': 'Failed to remove item from cart',
                'error': str(e),
                'cart': cart_json
            }

    def get_cart_summary(self, cart_json: str) -> Dict[str, Any]:
        """
        Get a summary of the cart contents

        Args:
            cart_json: Cart as JSON string

        Returns:
            Dict with cart summary
        """
        try:
            cart = json.loads(cart_json) if cart_json else {}

            if not cart:
                return {
                    'status': 'success',
                    'message': 'Cart is empty',
                    'items': [],
                    'total_items': 0,
                    'total_price': 0
                }

            items = []
            total_items = 0
            total_price = 0

            for cart_key, item in cart.items():
                item_total = item['quantity'] * item['price']
                total_items += item['quantity']
                total_price += item_total

                items.append({
                    'cart_key': cart_key,
                    'product_name': item['product_name'],
                    'color': item['color'],
                    'size': item['size'],
                    'quantity': item['quantity'],
                    'price': item['price'],
                    'item_total': item_total,
                    'images': item.get('images', [])
                })

            return {
                'status': 'success',
                'items': items,
                'total_items': total_items,
                'total_price': total_price,
                'message': f'Cart contains {total_items} items worth ${total_price:.2f}'
            }

        except Exception as e:
            logger.error(f"❌ Error getting cart summary: {e}")
            return {
                'status': 'error',
                'message': 'Failed to get cart summary',
                'error': str(e)
            }

    def validate_cart_availability(self, cart_json: str) -> Dict[str, Any]:
        """
        Validate that all cart items are still available

        Args:
            cart_json: Cart as JSON string

        Returns:
            Dict with validation results
        """
        try:
            cart = json.loads(cart_json) if cart_json else {}

            if not cart:
                return {
                    'status': 'success',
                    'message': 'Cart is empty',
                    'valid': True,
                    'issues': []
                }

            issues = []
            valid_items = {}

            for cart_key, item in cart.items():
                # Get current product details
                product_result = get_product_details(item['product_id'])

                if product_result['status'] != 'success':
                    issues.append({
                        'cart_key': cart_key,
                        'issue': 'product_not_found',
                        'message': f'Product {item["product_name"]} is no longer available'
                    })
                    continue

                product = product_result['data']

                # Check if color is still available
                available_colors = product.get('colors', [])
                if item['color'] and item['color'] not in available_colors:
                    issues.append({
                        'cart_key': cart_key,
                        'issue': 'color_unavailable',
                        'message': f'Color {item["color"]} is no longer available for {item["product_name"]}',
                        'available_colors': available_colors
                    })
                    continue

                # Check if size is still available
                available_sizes = product.get('available_sizes', [])
                if item['size'] and item['size'] not in available_sizes:
                    issues.append({
                        'cart_key': cart_key,
                        'issue': 'size_unavailable',
                        'message': f'Size {item["size"]} is no longer available for {item["product_name"]}',
                        'available_sizes': available_sizes
                    })
                    continue

                # Check for price changes
                current_price = product.get('sale_price') or product.get('regular_price', 0)
                if current_price != item['price']:
                    issues.append({
                        'cart_key': cart_key,
                        'issue': 'price_changed',
                        'message': f'Price changed for {item["product_name"]}: ${item["price"]} → ${current_price}',
                        'old_price': item['price'],
                        'new_price': current_price
                    })

                valid_items[cart_key] = item

            return {
                'status': 'success',
                'valid': len(issues) == 0,
                'issues': issues,
                'valid_items': valid_items,
                'message': f'Cart validation complete: {len(issues)} issues found' if issues else 'Cart is valid'
            }

        except Exception as e:
            logger.error(f"❌ Error validating cart: {e}")
            return {
                'status': 'error',
                'message': 'Failed to validate cart',
                'error': str(e)
            }

# Global instance
_cart_manager = None

def get_cart_manager() -> CartManager:
    """Get global cart manager instance"""
    global _cart_manager
    if _cart_manager is None:
        _cart_manager = CartManager()
    return _cart_manager