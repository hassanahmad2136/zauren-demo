"""
Quick test for cart removal functionality
This will help debug the quantity removal issue
"""

import json
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_cart_removal_scenarios():
    """Test different cart removal scenarios"""
    print("🧪 Testing Cart Removal Scenarios")
    print("=" * 50)
    
    # Test scenario 1: Remove specific quantity
    print("\n📋 Scenario 1: Remove 1 item from 3 items")
    
    test_session = {
        'user_id': 'test_user_123',
        'cart': {
            'items': [
                {
                    'id': 'test_product_1',
                    'name': 'Kurta',
                    'quantity': 3,
                    'price': 50.0
                }
            ],
            'total': 150.0
        }
    }
    
    # Simulate LLM response for "remove 1 kurta"
    response_data_specific = {
        'intent': 'remove_from_cart',
        'products': [
            {
                'product': 'Kurta',
                'product_id': 'test_product_1',
                'quantity': 1  # Specific quantity
            }
        ]
    }
    
    print(f"Before removal: {test_session['cart']['items'][0]['quantity']} kurtas")
    print(f"LLM response: {response_data_specific}")
    
    # Import and test the function
    try:
        from app.services.webhook_service import update_cart_remove_products
        
        # Create a copy for testing
        import copy
        test_session_copy = copy.deepcopy(test_session)
        
        update_cart_remove_products(test_session_copy, response_data_specific)
        
        if test_session_copy['cart']['items']:
            remaining = test_session_copy['cart']['items'][0]['quantity']
            print(f"After removal: {remaining} kurtas")
            if remaining == 2:
                print("✅ PASSED: Correct partial removal")
            else:
                print(f"❌ FAILED: Expected 2, got {remaining}")
        else:
            print("❌ FAILED: All items were removed instead of partial")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test scenario 2: Remove without specific quantity (should ask for clarification)
    print("\n📋 Scenario 2: Remove kurta (no quantity specified)")
    
    response_data_no_quantity = {
        'intent': 'remove_from_cart',
        'products': [
            {
                'product': 'Kurta',
                'product_id': 'test_product_1'
                # No quantity specified
            }
        ]
    }
    
    print(f"LLM response: {response_data_no_quantity}")
    
    try:
        test_session_copy2 = copy.deepcopy(test_session)
        update_cart_remove_products(test_session_copy2, response_data_no_quantity)
        
        if not test_session_copy2['cart']['items']:
            print("⚠️ All items removed (expected behavior when no quantity specified)")
        else:
            remaining = test_session_copy2['cart']['items'][0]['quantity']
            print(f"After removal: {remaining} kurtas")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_llm_quantity_extraction():
    """Test if LLM correctly extracts quantities from user messages"""
    print("\n🧪 Testing LLM Quantity Extraction")
    print("=" * 50)
    
    test_messages = [
        "remove 1 kurta",
        "remove one kurta", 
        "remove 2 kurtas",
        "remove kurta",  # No quantity
        "remove all kurtas"
    ]
    
    # Mock cart with 3 kurtas
    mock_cart = {
        'items': [
            {
                'id': 'test_kurta',
                'name': 'Kurta',
                'quantity': 3,
                'price': 50.0
            }
        ],
        'total': 150.0
    }
    
    cart_json = json.dumps(mock_cart)
    
    try:
        from app.services.llm_shopping_cart_manage import handle_remove_from_cart_impl
        
        for message in test_messages:
            print(f"\n📝 Testing message: '{message}'")
            
            try:
                response = handle_remove_from_cart_impl(message, cart_json, [], "Test User")
                response_data = json.loads(response) if isinstance(response, str) else response
                
                if 'products' in response_data and response_data['products']:
                    product = response_data['products'][0]
                    quantity = product.get('quantity', 'not specified')
                    print(f"   Extracted quantity: {quantity}")
                    
                    if message == "remove 1 kurta" and quantity == 1:
                        print("   ✅ Correct extraction")
                    elif message == "remove 2 kurtas" and quantity == 2:
                        print("   ✅ Correct extraction")
                    elif "kurta" in message and quantity == "not specified":
                        need = response_data.get('NEED', [])
                        if 'quantity_clarification' in need:
                            print("   ✅ Correctly asking for clarification")
                        else:
                            print("   ⚠️ Should ask for quantity clarification")
                    else:
                        print(f"   ⚠️ Unexpected result for this message")
                else:
                    need = response_data.get('NEED', [])
                    print(f"   No products extracted, NEED: {need}")
                    
            except Exception as e:
                print(f"   ❌ Error processing message: {e}")
                
    except ImportError as e:
        print(f"❌ Cannot import LLM function: {e}")

if __name__ == "__main__":
    test_cart_removal_scenarios()
    test_llm_quantity_extraction()
    print("\n" + "=" * 50)
    print("🏁 Test completed!")
    print("\nIf you're still seeing issues:")
    print("1. Check the server logs for the detailed debug output")
    print("2. Test with actual WhatsApp messages")
    print("3. Make sure the LLM is extracting quantities correctly")
