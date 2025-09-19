import json
from supabase import create_client, Client
import os
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global client for connection reuse
_supabase_client = None

def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client using environment variables.
    Uses connection pooling for better concurrent performance.
    """
    global _supabase_client

    if _supabase_client is None:
        # Get credentials from environment variables
        supabase_url = os.getenv("INVENTORY_SUPABASE_URL")
        supabase_key = os.getenv("INVENTORY_SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("INVENTORY_SUPABASE_URL and INVENTORY_SUPABASE_KEY environment variables must be set")

        _supabase_client = create_client(supabase_url, supabase_key)

    return _supabase_client

# Function to get all categories
def get_all_categories() -> Dict[str, Any]:
    """
    Fetch all categories from the database
    
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table('categories').select('*').execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get all products
def get_all_products(include_categories: bool = True) -> Dict[str, Any]:
    """
    Fetch all products from the database with new schema support

    Args:
        include_categories: If True, includes the related category information

    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        query = supabase.table('products')

        if include_categories:
            # Include the related category data in the response
            query = query.select('*, categories(id, name, description)')
        else:
            query = query.select('*')

        response = query.execute()

        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get products by category
def get_products_by_category(category_id: str) -> Dict[str, Any]:
    """
    Fetch products that belong to a specific category
    
    Args:
        category_id: The UUID of the category to filter by
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table('products')\
            .select('*, categories(id, name)')\
            .eq('category_id', category_id)\
            .execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to search products
def search_products(search_term: str) -> Dict[str, Any]:
    """
    Search for products based on a search term
    
    Args:
        search_term: The term to search for in product names and descriptions
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        
        # PostgreSQL ILIKE for case-insensitive search with fuzzy matching
        # Search in title, description, colors array, material, style, occasion
        response = supabase.table('products')\
            .select('*, categories(id, name)')\
            .or_(f'title.ilike.%{search_term}%,description.ilike.%{search_term}%,colors::text.ilike.%{variation}%,material.ilike.%{search_term}%,style.ilike.%{search_term}%,occasion.ilike.%{search_term}%')\
            .limit(20)\
            .execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

def advanced_product_search(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advanced product search with multiple filters
    
    Args:
        filters: Dictionary containing search criteria:
            - search_terms: List of terms to search for
            - colors: List of colors to filter by
            - categories: List of category IDs
            - price_range: Dict with 'min' and 'max' price
            - materials: List of materials
            - occasions: List of occasions
            - limit: Maximum number of results (default 20)
    
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        
        # Start building the query
        query = supabase.table('products').select('*, categories(id, name)')
        
        # Build all filter conditions properly to avoid conflicting OR clauses
        
        # Start with base query
        base_filters = []
        
        # Search terms - check name, description, and attributes
        search_terms = filters.get('search_terms', [])
        if search_terms:
            search_conditions = []
            for term in search_terms:
                search_conditions.extend([
                    f'title.ilike.%{term}%',
                    f'description.ilike.%{term}%',
                    f'colors::text.ilike.%{term}%',
                    f'material.ilike.%{term}%',
                    f'style.ilike.%{term}%',
                    f'occasion.ilike.%{term}%'
                ])
            
            if search_conditions:
                query = query.or_(','.join(search_conditions))
        
        # Color filter - use separate query if search conditions were already applied
        colors = filters.get('colors', [])
        if colors and not search_terms:  # Only if no search terms to avoid OR conflict
            color_conditions = [f'colors::text.ilike.%{color}%' for color in colors]
            query = query.or_(','.join(color_conditions))
        
        # Category filter (use AND condition)
        categories = filters.get('categories', [])
        if categories:
            query = query.in_('category_id', categories)
        
        # Price range filter - use proper AND conditions
        price_range = filters.get('price_range', {})
        if price_range.get('min') is not None:
            min_price = price_range["min"]
            query = query.gte('regular_price', min_price)
        if price_range.get('max') is not None:
            max_price = price_range["max"]
            query = query.lte('regular_price', max_price)
        
        # Material filter - only if no other OR conditions applied
        materials = filters.get('materials', [])
        if materials and not search_terms and not colors:
            material_conditions = [f'material.ilike.%{material}%' for material in materials]
            query = query.or_(','.join(material_conditions))
        
        # Occasion filter - only if no other OR conditions applied
        occasions = filters.get('occasions', [])
        if occasions and not search_terms and not colors and not materials:
            occasion_conditions = [f'occasion.ilike.%{occasion}%' for occasion in occasions]
            query = query.or_(','.join(occasion_conditions))
        
        # Limit results
        limit = filters.get('limit', 20)
        query = query.limit(limit)
        
        # Execute query
        response = query.execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

def strict_product_search(search_terms: List[str], exact_match: bool = True) -> Dict[str, Any]:
    """
    Strict product search that only returns exact matches
    
    Args:
        search_terms: List of terms that must match exactly
        exact_match: If True, uses exact matching; if False, uses fuzzy matching
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        
        if not search_terms:
            return {
                'status': 'success',
                'data': [],
                'error': None
            }
        
        # Start with all products
        query = supabase.table('products').select('*, categories(id, name)')
        
        if exact_match:
            # Enhanced strict matching with special color validation
            conditions = []
            for term in search_terms:
                term_lower = term.lower()
                
                # Special strict color matching with shade support
                if term_lower == 'blue':
                    # Include all legitimate blue shades
                    blue_variations = ['blue', 'navy', 'royal blue', 'sky blue', 'light blue', 'dark blue', 'midnight blue']
                    blue_conditions = []
                    for variation in blue_variations:
                        blue_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(blue_conditions)})")
                    
                elif term_lower == 'green':
                    # Include all legitimate green shades
                    green_variations = ['green', 'olive', 'emerald', 'forest green', 'mint green', 'dark green', 'light green']
                    green_conditions = []
                    for variation in green_variations:
                        green_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(green_conditions)})")
                    
                elif term_lower == 'red':
                    # Include all legitimate red shades
                    red_variations = ['red', 'maroon', 'crimson', 'burgundy', 'wine red', 'cherry red', 'deep red']
                    red_conditions = []
                    for variation in red_variations:
                        red_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(red_conditions)})")
                    
                elif term_lower == 'white':
                    # Include all legitimate white shades
                    white_variations = ['white', 'ivory', 'cream', 'off-white', 'pearl white', 'bone white']
                    white_conditions = []
                    for variation in white_variations:
                        white_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(white_conditions)})")
                    
                elif term_lower == 'black':
                    # Include all legitimate black shades
                    black_variations = ['black', 'charcoal', 'jet black', 'midnight black', 'coal black']
                    black_conditions = []
                    for variation in black_variations:
                        black_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(black_conditions)})")
                    
                elif term_lower in ['brown', 'beige']:
                    # Include all legitimate brown shades
                    brown_variations = ['brown', 'beige', 'tan', 'khaki', 'chocolate', 'coffee brown']
                    brown_conditions = []
                    for variation in brown_variations:
                        brown_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(brown_conditions)})")
                    
                elif term_lower in ['grey', 'gray']:
                    # Include all legitimate grey shades
                    grey_variations = ['grey', 'gray', 'silver', 'charcoal grey', 'light grey', 'dark grey']
                    grey_conditions = []
                    for variation in grey_variations:
                        grey_conditions.extend([
                            f'title.ilike.*{variation}*',
                            f'colors::text.ilike.%{variation}%'
                        ])
                    conditions.append(f"({','.join(grey_conditions)})")
                    
                elif term_lower in ['navy', 'maroon', 'olive']:
                    # Handle specific shade requests
                    conditions.extend([
                        f'title.ilike.*{term}*',
                        f'colors::text.ilike.%{term}%',
                        f'description.ilike.*{term}*'
                    ])
                    
                elif term_lower in ['cotton', 'silk', 'velvet', 'linen', 'wool', 'denim', 'leather']:
                    # For materials, require exact match
                    conditions.append(f'material.ilike.{term}')
                    conditions.append(f'description.ilike.*{term}*')
                    
                elif term_lower in ['embroidered', 'embroidery', 'plain']:
                    # For styles, check both title and style field
                    conditions.append(f'title.ilike.*{term}*')
                    conditions.append(f'style.ilike.*{term}*')
                    conditions.append(f'description.ilike.*{term}*')
                    
                elif term_lower in ['formal', 'casual', 'wedding']:
                    # For occasions, require exact match
                    conditions.append(f'occasion.ilike.{term}')
                    conditions.append(f'description.ilike.*{term}*')
                    
                else:
                    # General terms
                    conditions.extend([
                        f'title.ilike.*{term}*',
                        f'description.ilike.*{term}*'
                    ])
            
            if conditions:
                query = query.or_(','.join(conditions))
        else:
            # Use fuzzy matching
            conditions = []
            for term in search_terms:
                conditions.extend([
                    f'title.ilike.%{term}%',
                    f'description.ilike.%{term}%',
                    f'colors::text.ilike.%{term}%',
                    f'material.ilike.%{term}%',
                    f'style.ilike.%{term}%',
                    f'occasion.ilike.%{term}%'
                ])
            
            if conditions:
                query = query.or_(','.join(conditions))
        
        # Limit results
        query = query.limit(15)
        
        # Execute query
        response = query.execute()
        
        # If exact_match is True, filter results more strictly
        if exact_match and response.data:
            filtered_results = []
            for product in response.data:
                product_matches = True  # Start with True and validate each requirement
                
                for term in search_terms:
                    term_lower = term.lower()
                    product_title = product.get('title', '').lower()
                    product_desc = product.get('description', '').lower()
                    product_colors = [color.lower() for color in product.get('colors', [])]
                    product_material = product.get('material', '').lower()
                    product_style = product.get('style', '').lower()
                    product_occasion = product.get('occasion', '').lower()
                    
                    term_matched = False
                    
                    # Strict color validation
                    if term_lower in ['blue', 'green', 'red', 'black', 'white', 'navy', 'maroon', 'grey', 'gray', 'brown', 'beige']:
                        # Color must be primary (in name) and not mixed with other colors
                        if term_lower == 'blue':
                            # Special validation for blue - reject if mixed with other colors
                            if ('blue' in product_title and
                                not any(other_color in product_title for other_color in ['green', 'teal', 'navy', 'purple', 'olive'] if other_color != 'blue')):
                                term_matched = True
                            elif ('blue' in product_colors and
                                  not any(other_color in product_desc[:100] for other_color in ['green', 'teal', 'hint', 'accent', 'touch'])):
                                term_matched = True
                        else:
                            # For other colors, check if it's the primary color
                            if term_lower in product_title or term_lower in product_colors:
                                term_matched = True
                    
                    # Strict material validation
                    elif term_lower in ['cotton', 'silk', 'velvet', 'linen', 'wool', 'denim', 'leather']:
                        if product_material == term_lower or term_lower in product_desc:
                            term_matched = True
                    
                    # Strict style validation
                    elif term_lower in ['embroidered', 'embroidery']:
                        if any(embr_term in product_title or embr_term in product_desc for embr_term in ['embroidered', 'embroidery']):
                            term_matched = True
                    elif term_lower == 'plain':
                        # Plain means NO embroidery or patterns
                        if not any(pattern_term in product_title or pattern_term in product_desc
                                 for pattern_term in ['embroidered', 'embroidery', 'pattern', 'printed', 'design']):
                            term_matched = True
                    
                    # Strict occasion validation
                    elif term_lower in ['formal', 'casual', 'wedding']:
                        if product_occasion == term_lower or term_lower in product_desc:
                            term_matched = True
                    
                    # General term matching
                    else:
                        if term_lower in product_title or term_lower in product_desc:
                            term_matched = True
                    
                    # If any term doesn't match, exclude this product
                    if not term_matched:
                        product_matches = False
                        break
                
                if product_matches:
                    filtered_results.append(product)
            
            response.data = filtered_results
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get product details by ID
def get_product_details(product_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific product
    
    Args:
        product_id: The UUID of the product
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table('products')\
            .select('*, categories(id, name, description)')\
            .eq('id', product_id)\
            .single()\
            .execute()
        
        # Get inventory transactions for this product
        transactions = supabase.table('inventory_transactions')\
            .select('*')\
            .eq('product_id', product_id)\
            .order('transaction_date', desc=True)\
            .execute()
        
        result = response.data
        result['transactions'] = transactions.data
        
        return {
            'status': 'success',
            'data': result,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get all suppliers
def get_all_suppliers() -> Dict[str, Any]:
    """
    Fetch all suppliers from the database
    
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table('suppliers').select('*').execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get purchase orders with items
def get_purchase_orders(include_items: bool = True) -> Dict[str, Any]:
    """
    Fetch all purchase orders, optionally including their items
    
    Args:
        include_items: If True, includes the related purchase order items
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        
        # Get purchase orders with supplier information
        response = supabase.table('purchase_orders')\
            .select('*, suppliers(id, name, contact_person)')\
            .execute()
        
        result = response.data
        
        # If requested, fetch items for each purchase order
        if include_items and result:
            for i, order in enumerate(result):
                items_response = supabase.table('purchase_order_items')\
                    .select('*, products(id, title, sku)')\
                    .eq('purchase_order_id', order['id'])\
                    .execute()
                    
                result[i]['items'] = items_response.data
        
        return {
            'status': 'success',
            'data': result,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get inventory transactions with filtering options
def get_inventory_transactions(
    product_id: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch inventory transactions with optional filtering
    
    Args:
        product_id: Filter by product ID (optional)
        transaction_type: Filter by transaction type (optional)
        start_date: Filter by transactions after this date (optional)
        end_date: Filter by transactions before this date (optional)
        limit: Maximum number of transactions to return
        
    Returns:
        Dict with status, data, and error information
    """
    try:
        supabase = get_supabase_client()
        query = supabase.table('inventory_transactions')\
            .select('*, products(id, title, sku)')\
            .order('transaction_date', desc=True)\
            .limit(limit)
        
        # Apply filters if provided
        if product_id:
            query = query.eq('product_id', product_id)
            
        if transaction_type:
            query = query.eq('transaction_type', transaction_type)
            
        if start_date:
            query = query.gte('transaction_date', start_date.isoformat())
            
        if end_date:
            query = query.lte('transaction_date', end_date.isoformat())
            
        response = query.execute()
        
        return {
            'status': 'success',
            'data': response.data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get inventory summary
def get_inventory_summary() -> Dict[str, Any]:
    """
    Get a summary of the current inventory status
    
    Returns:
        Dict with inventory statistics and product counts
    """
    try:
        supabase = get_supabase_client()
        
        # Get total product count
        products_response = supabase.table('products').select('count', count='exact').execute()
        total_products = products_response.count
        
        # Get low stock products (less than 5 items)
        low_stock_response = supabase.table('products')\
            .select('*, categories(name)')\
            .lt('quantity', 5)\
            .execute()
        
        # Get out of stock products
        out_of_stock_response = supabase.table('products')\
            .select('*, categories(name)')\
            .eq('quantity', 0)\
            .execute()
        
        # Get products by category counts
        categories_response = supabase.table('categories').select('id, name').execute()
        categories = categories_response.data
        
        category_counts = []
        for category in categories:
            count_response = supabase.table('products')\
                .select('count', count='exact')\
                .eq('category_id', category['id'])\
                .execute()
                
            category_counts.append({
                'category_id': category['id'],
                'category_name': category['name'],
                'product_count': count_response.count
            })
        
        # Get recent transactions
        recent_transactions_response = supabase.table('inventory_transactions')\
            .select('*, products(title)')\
            .order('transaction_date', desc=True)\
            .limit(10)\
            .execute()
        
        return {
            'status': 'success',
            'data': {
                'total_products': total_products,
                'low_stock_products': low_stock_response.data,
                'out_of_stock_products': out_of_stock_response.data,
                'category_counts': category_counts,
                'recent_transactions': recent_transactions_response.data
            },
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to export inventory as JSON
def export_inventory_to_json(file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Export the entire inventory database to a JSON file or return as a dict
    
    Args:
        file_path: If provided, saves the JSON to this file path
        
    Returns:
        Dict with status and data or file path information
    """
    try:
        # Get all data
        categories = get_all_categories()
        products = get_all_products()
        suppliers = get_all_suppliers()
        purchase_orders = get_purchase_orders()
        
        # Combine into a single export object
        export_data = {
            'categories': categories['data'],
            'products': products['data'],
            'suppliers': suppliers['data'],
            'purchase_orders': purchase_orders['data'],
            'export_date': datetime.now().isoformat()
        }
        
        # If file path is provided, save to file
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
                
            return {
                'status': 'success',
                'message': f'Inventory data exported to {file_path}',
                'file_path': file_path
            }
        
        # Otherwise return the data
        return {
            'status': 'success',
            'data': export_data,
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

# Function to get detailed stock status report
def get_stock_status_report() -> Dict[str, Any]:
    """
    Generate a detailed stock status report with valuations
    
    Returns:
        Dict with status and stock report data
    """
    try:
        supabase = get_supabase_client()
        
        # Get all products with their categories
        products_response = supabase.table('products')\
            .select('*, categories(name)')\
            .execute()
            
        products = products_response.data
        
        # Calculate total inventory value and other metrics using new price schema
        total_value = 0
        category_values = {}
        stock_report = []

        for product in products:
            # Use sale_price if available, otherwise regular_price
            regular_price = float(product.get('regular_price', 0)) if product.get('regular_price') else 0
            sale_price = float(product.get('sale_price', 0)) if product.get('sale_price') else 0
            unit_price = sale_price if sale_price > 0 else regular_price
            quantity = int(product.get('quantity', 0))
            product_value = quantity * unit_price
            total_value += product_value
            
            # Track value by category
            category_name = product['categories']['name'] if product['categories'] else 'Uncategorized'
            if category_name not in category_values:
                category_values[category_name] = 0
            category_values[category_name] += product_value
            
            # Add to detailed report with updated pricing
            stock_report.append({
                'id': product['id'],
                'title': product['title'],
                'sku': product.get('sku', ''),
                'category': category_name,
                'quantity': quantity,
                'regular_price': regular_price,
                'sale_price': sale_price,
                'effective_price': unit_price,
                'total_value': product_value,
                'colors': product.get('colors', []),
                'sizes': product.get('sizes', []),
                'available_sizes': product.get('available_sizes', []),
                'on_sale': sale_price > 0 and sale_price < regular_price,
                'status': 'Out of Stock' if quantity == 0 else
                          'Low Stock' if quantity < 5 else 'In Stock'
            })
        
        # Sort by value (highest first)
        stock_report.sort(key=lambda x: x['total_value'], reverse=True)
        
        # Calculate category percentages
        category_percentage = {}
        for category, value in category_values.items():
            category_percentage[category] = (value / total_value) * 100 if total_value > 0 else 0
        
        return {
            'status': 'success',
            'data': {
                'total_inventory_value': total_value,
                'category_values': category_values,
                'category_percentage': category_percentage,
                'detailed_report': stock_report,
                'report_date': datetime.now().isoformat()
            },
            'error': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error': str(e)
        }

def create_nested_inventory_json(categories, products):
    """
    Create a nested JSON representation of inventory with products nested under their categories.
    
    Args:
        categories: List of category dictionaries from Supabase
        products: List of product dictionaries from Supabase
    
    Returns:
        A JSON string containing the nested inventory structure
    """
    import json
    
    # Group products by category_id
    products_by_category = {}
    for product in products:
        category_id = product["category_id"]
        if category_id not in products_by_category:
            products_by_category[category_id] = []
        
        # Add simplified product to the appropriate category
        regular_price = float(product.get("regular_price", 0)) if product.get("regular_price") else 0
        sale_price = float(product.get("sale_price", 0)) if product.get("sale_price") else 0
        effective_price = sale_price if sale_price > 0 else regular_price

        products_by_category[category_id].append({
            "id": product["id"],
            "title": product["title"],
            "description": product["description"],
            "quantity": int(product.get("quantity", 0)),
            "regular_price": regular_price,
            "sale_price": sale_price,
            "effective_price": effective_price,
            "sizes": product.get("sizes", []),
            "colors": product.get("colors", []),
            "available_sizes": product.get("available_sizes", []),
            "on_sale": sale_price > 0 and sale_price < regular_price,
            "IMPORTANT": "EFFECTIVE PRICE IS THE CURRENT SELLING PRICE"
        })
    
    # Create the nested category structure with products
    nested_categories = []
    for category in categories:
        category_id = category["id"]
        nested_category = {
            "id": category_id,
            "name": category["name"],
            "description": category["description"],
            "products": products_by_category.get(category_id, [])
        }
        nested_categories.append(nested_category)
    
    # Create the final inventory object
    inventory = {
        "categories": nested_categories
    }
    
    # Convert to JSON string
    inventory_json = json.dumps(inventory)
    
    return inventory_json

print(create_nested_inventory_json(get_all_categories()['data'], get_all_products()['data']))