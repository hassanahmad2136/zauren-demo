import json
from supabase import create_client, Client
import os
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Supabase client
def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client using environment variables
    """
    # Get credentials from environment variables
    supabase_url = os.getenv("INVENTORY_SUPABASE_URL")
    supabase_key = os.getenv("INVENTORY_SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("INVENTORY_SUPABASE_URL and INVENTORY_SUPABASE_KEY environment variables must be set")
    
    return create_client(supabase_url, supabase_key)

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
    Fetch all products from the database
    
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
        
        # PostgreSQL ILIKE for case-insensitive search
        response = supabase.table('products')\
            .select('*, categories(id, name)')\
            .or_(f'name.ilike.%{search_term}%,description.ilike.%{search_term}%')\
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
                    .select('*, products(id, name, sku)')\
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
            .select('*, products(id, name, sku)')\
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
            .select('*, products(name)')\
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
        
        # Calculate total inventory value and other metrics
        total_value = 0
        category_values = {}
        stock_report = []
        
        for product in products:
            product_value = product['quantity'] * product['unit_price']
            total_value += product_value
            
            # Track value by category
            category_name = product['categories']['name'] if product['categories'] else 'Uncategorized'
            if category_name not in category_values:
                category_values[category_name] = 0
            category_values[category_name] += product_value
            
            # Add to detailed report
            stock_report.append({
                'id': product['id'],
                'name': product['name'],
                'sku': product['sku'],
                'category': category_name,
                'quantity': product['quantity'],
                'unit_price': product['unit_price'],
                'total_value': product_value,
                'status': 'Out of Stock' if product['quantity'] == 0 else 
                          'Low Stock' if product['quantity'] < 5 else 'In Stock'
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
        products_by_category[category_id].append({
            "id": product["id"],
            "name": product["name"],
            "description": product["description"],
            "quantity": product["quantity"],
            "fixed_price": product["unit_price"],
            "IMPORTANT": "PRICE IS FIXED, NO DISCOUNTS"
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

def reserve_stock(product_id: str, quantity: int, user_id: str) -> Dict[str, Any]:
    """
    Reserve stock for a product when added to cart
    
    Args:
        product_id: Product ID to reserve stock for
        quantity: Quantity to reserve
        user_id: User ID making the reservation
        
    Returns:
        Dict with status and result information
    """
    try:
        supabase = get_supabase_client()
        
        # Check current available stock
        product_response = supabase.table('products')\
            .select('quantity, name')\
            .eq('id', product_id)\
            .execute()
            
        if not product_response.data:
            return {
                'status': 'error',
                'error': 'Product not found'
            }
        
        product = product_response.data[0]
        available_stock = product['quantity']
        
        # Check if enough stock is available
        if available_stock < quantity:
            return {
                'status': 'error',
                'error': f'Insufficient stock. Available: {available_stock}, Requested: {quantity}'
            }
        
        # Create or update reservation
        reservation_response = supabase.table('stock_reservations')\
            .select('quantity')\
            .eq('product_id', product_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if reservation_response.data:
            # Update existing reservation
            current_reserved = reservation_response.data[0]['quantity']
            new_reserved = current_reserved + quantity
            
            # Check if total reservation would exceed available stock
            total_reserved_response = supabase.table('stock_reservations')\
                .select('quantity')\
                .eq('product_id', product_id)\
                .execute()
            
            total_reserved = sum(r['quantity'] for r in total_reserved_response.data if r['user_id'] != user_id)
            
            if available_stock < total_reserved + new_reserved:
                return {
                    'status': 'error',
                    'error': 'Not enough stock available for reservation'
                }
            
            supabase.table('stock_reservations')\
                .update({'quantity': new_reserved, 'updated_at': datetime.now().isoformat()})\
                .eq('product_id', product_id)\
                .eq('user_id', user_id)\
                .execute()
        else:
            # Create new reservation
            supabase.table('stock_reservations')\
                .insert({
                    'product_id': product_id,
                    'user_id': user_id,
                    'quantity': quantity,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                })\
                .execute()
        
        return {
            'status': 'success',
            'reserved_quantity': quantity,
            'product_name': product['name']
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def release_reserved_stock(product_id: str, quantity: int, user_id: str = None) -> Dict[str, Any]:
    """
    Release reserved stock when items are removed from cart
    
    Args:
        product_id: Product ID to release stock for
        quantity: Quantity to release
        user_id: User ID (if None, will try to release from any reservation)
        
    Returns:
        Dict with status and result information
    """
    try:
        supabase = get_supabase_client()
        
        if user_id:
            # Get current reservation for this user
            reservation_response = supabase.table('stock_reservations')\
                .select('quantity')\
                .eq('product_id', product_id)\
                .eq('user_id', user_id)\
                .execute()
            
            if not reservation_response.data:
                return {
                    'status': 'warning',
                    'message': 'No reservation found for this user'
                }
            
            current_reserved = reservation_response.data[0]['quantity']
            
            if quantity >= current_reserved:
                # Remove entire reservation
                supabase.table('stock_reservations')\
                    .delete()\
                    .eq('product_id', product_id)\
                    .eq('user_id', user_id)\
                    .execute()
            else:
                # Reduce reservation quantity
                new_reserved = current_reserved - quantity
                supabase.table('stock_reservations')\
                    .update({'quantity': new_reserved, 'updated_at': datetime.now().isoformat()})\
                    .eq('product_id', product_id)\
                    .eq('user_id', user_id)\
                    .execute()
        
        return {
            'status': 'success',
            'released_quantity': quantity
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def get_available_stock(product_id: str) -> Dict[str, Any]:
    """
    Get available stock for a product (total stock - reserved stock)
    
    Args:
        product_id: Product ID to check stock for
        
    Returns:
        Dict with available stock information
    """
    try:
        supabase = get_supabase_client()
        
        # Get total stock
        product_response = supabase.table('products')\
            .select('quantity, name')\
            .eq('id', product_id)\
            .execute()
            
        if not product_response.data:
            return {
                'status': 'error',
                'error': 'Product not found'
            }
        
        total_stock = product_response.data[0]['quantity']
        product_name = product_response.data[0]['name']
        
        # Get reserved stock
        reservations_response = supabase.table('stock_reservations')\
            .select('quantity')\
            .eq('product_id', product_id)\
            .execute()
        
        reserved_stock = sum(r['quantity'] for r in reservations_response.data)
        available_stock = total_stock - reserved_stock
        
        return {
            'status': 'success',
            'product_name': product_name,
            'total_stock': total_stock,
            'reserved_stock': reserved_stock,
            'available_stock': max(0, available_stock)
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def cleanup_expired_reservations(expiry_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up expired stock reservations (for inactive carts)
    
    Args:
        expiry_hours: Hours after which reservations expire
        
    Returns:
        Dict with cleanup results
    """
    try:
        supabase = get_supabase_client()
        
        # Calculate expiry timestamp
        expiry_time = datetime.now() - datetime.timedelta(hours=expiry_hours)
        
        # Delete expired reservations
        expired_response = supabase.table('stock_reservations')\
            .delete()\
            .lt('updated_at', expiry_time.isoformat())\
            .execute()
        
        return {
            'status': 'success',
            'cleaned_reservations': len(expired_response.data) if expired_response.data else 0
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def finalize_purchase(user_id: str, cart_items: List[Dict]) -> Dict[str, Any]:
    """
    Finalize purchase by reducing actual stock and clearing reservations
    
    Args:
        user_id: User ID making the purchase
        cart_items: List of cart items with product_id and quantity
        
    Returns:
        Dict with purchase finalization results
    """
    try:
        supabase = get_supabase_client()
        
        # Process each item
        processed_items = []
        for item in cart_items:
            product_id = item.get('id')
            quantity = item.get('quantity', 0)
            
            if not product_id:
                continue
            
            # Reduce actual stock
            product_response = supabase.table('products')\
                .select('quantity')\
                .eq('id', product_id)\
                .execute()
            
            if product_response.data:
                current_stock = product_response.data[0]['quantity']
                new_stock = max(0, current_stock - quantity)
                
                supabase.table('products')\
                    .update({'quantity': new_stock})\
                    .eq('id', product_id)\
                    .execute()
                
                # Remove reservation
                supabase.table('stock_reservations')\
                    .delete()\
                    .eq('product_id', product_id)\
                    .eq('user_id', user_id)\
                    .execute()
                
                processed_items.append({
                    'product_id': product_id,
                    'quantity_purchased': quantity,
                    'new_stock': new_stock
                })
        
        return {
            'status': 'success',
            'processed_items': processed_items
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

print(create_nested_inventory_json(get_all_categories()['data'], get_all_products()['data']))