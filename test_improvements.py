"""
Test script for WhatsApp Bot improvements
Run this script to validate the key fixes and improvements
"""

import json
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.services.db_inventory import (
        get_all_products, 
        reserve_stock, 
        release_reserved_stock,
        get_available_stock,
        cleanup_expired_reservations
    )
    from app.services.webhook_service import (
        update_cart_add_products,
        update_cart_remove_products
    )
    from app.services.cart_cleanup import CartCleanupService
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_stock_management():
    """Test stock reservation and release functionality"""
    print("\n🧪 Testing Stock Management...")
    
    # Get a sample product
    products_result = get_all_products()
    if products_result['status'] != 'success' or not products_result['data']:
        print("❌ No products found for testing")
        return False
    
    product = products_result['data'][0]
    product_id = product['id']
    test_user_id = "test_user_123"
    
    print(f"Using product: {product['name']} (ID: {product_id})")
    
    # Test stock availability check
    stock_info = get_available_stock(product_id)
    if stock_info['status'] == 'success':
        print(f"✅ Available stock: {stock_info['available_stock']}")
    else:
        print(f"❌ Failed to get stock info: {stock_info['error']}")
        return False
    
    # Test stock reservation
    reserve_result = reserve_stock(product_id, 2, test_user_id)
    if reserve_result['status'] == 'success':
        print(f"✅ Reserved 2 units successfully")
    else:
        print(f"❌ Failed to reserve stock: {reserve_result['error']}")
        return False
    
    # Test stock release
    release_result = release_reserved_stock(product_id, 1, test_user_id)
    if release_result['status'] == 'success':
        print(f"✅ Released 1 unit successfully")
    else:
        print(f"❌ Failed to release stock: {release_result['error']}")
        return False
    
    # Clean up - release remaining reservation
    release_remaining = release_reserved_stock(product_id, 10, test_user_id)  # Release all remaining
    print(f"🧹 Cleanup: {release_remaining['status']}")
    
    return True

def test_cart_quantity_removal():
    """Test partial quantity removal from cart"""
    print("\n🧪 Testing Cart Quantity Removal...")
    
    # Create a test user session
    test_session = {
        'user_id': 'test_user_123',
        'cart': {
            'items': [
                {
                    'id': 'test_product_1',
                    'name': 'Test Kurta',
                    'quantity': 3,
                    'price': 50.0
                }
            ],
            'total': 150.0
        }
    }
    
    print(f"Initial cart: {test_session['cart']['items'][0]['quantity']} kurtas")
    
    # Test removing partial quantity
    response_data = {
        'intent': 'remove_from_cart',
        'products': [
            {
                'product': 'Test Kurta',
                'product_id': 'test_product_1',
                'quantity': 1  # Remove only 1 item
            }
        ]
    }
    
    # Test the removal function
    try:
        update_cart_remove_products(test_session, response_data)
        remaining_quantity = test_session['cart']['items'][0]['quantity']
        
        if remaining_quantity == 2:
            print(f"✅ Partial removal successful: {remaining_quantity} kurtas remaining")
            return True
        else:
            print(f"❌ Unexpected quantity after removal: {remaining_quantity}")
            return False
    except Exception as e:
        print(f"❌ Error in cart removal: {e}")
        return False

def test_cleanup_service():
    """Test cart cleanup service"""
    print("\n🧪 Testing Cart Cleanup Service...")
    
    try:
        # Test cleanup service initialization
        cleanup_service = CartCleanupService(
            cleanup_interval_hours=1,
            cart_expiry_hours=12,
            reservation_expiry_hours=12
        )
        
        print("✅ Cleanup service initialized successfully")
        
        # Test manual cleanup (without starting the background service)
        cleanup_service.cleanup_expired_stock_reservations()
        print("✅ Manual stock reservation cleanup completed")
        
        return True
    except Exception as e:
        print(f"❌ Error in cleanup service: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting WhatsApp Bot Improvements Test Suite")
    print("=" * 50)
    
    tests = [
        ("Stock Management", test_stock_management),
        ("Cart Quantity Removal", test_cart_quantity_removal),
        ("Cleanup Service", test_cleanup_service)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The improvements are working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
