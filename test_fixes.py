#!/usr/bin/env python3
"""
Test script to verify the fixes for:
1. Strict product matching (blue clothes should not show green items)
2. Interactive message duplication fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.db_inventory import strict_product_search
from app.services.llm_product_search import extract_search_terms, ProductSearchOptimizer

def test_strict_matching():
    """Test that strict matching works for color requirements"""
    print("🧪 Testing Strict Product Matching...")
    
    # Test 1: Search for blue items - should not return green items
    print("\n📝 Test 1: Searching for 'blue clothes'")
    blue_results = strict_product_search("blue clothes", limit=10)
    
    print(f"Found {len(blue_results)} results:")
    for product in blue_results:
        name = product.get('name', 'Unknown')
        desc = product.get('description', '')[:100] + "..."
        print(f"  - {name}: {desc}")
        
        # Check if any green items appear in blue search
        if 'green' in name.lower() and 'blue' not in name.lower():
            print(f"  ❌ ERROR: Found green item '{name}' in blue search!")
        elif 'blue' in name.lower():
            print(f"  ✅ CORRECT: Blue item found")
    
    # Test 2: Search for green items
    print("\n📝 Test 2: Searching for 'green clothes'")
    green_results = strict_product_search("green clothes", limit=10)
    
    print(f"Found {len(green_results)} results:")
    for product in green_results:
        name = product.get('name', 'Unknown')
        desc = product.get('description', '')[:100] + "..."
        print(f"  - {name}: {desc}")

def test_search_term_extraction():
    """Test the enhanced search term extraction"""
    print("\n🧪 Testing Search Term Extraction...")
    
    test_queries = [
        "I want blue clothes",
        "Show me formal wear",
        "Looking for green kurta",
        "Need black shoes for wedding"
    ]
    
    for query in test_queries:
        terms = extract_search_terms(query)
        print(f"Query: '{query}' → Terms: {terms}")

def test_interactive_message_logic():
    """Test the interactive message secondary_id logic"""
    print("\n🧪 Testing Interactive Message Logic...")
    
    # Simulate the fixed logic
    def test_secondary_id_calculation(total_items, current_index):
        """Simulate the fixed secondary_id calculation"""
        # This mimics the fix: next_category_index = i % len(response_data.get("category_details", [])) + 1
        next_index = current_index % total_items + 1
        return next_index
    
    # Test with different scenarios
    scenarios = [
        (3, 1),  # First item of 3
        (3, 2),  # Middle item of 3
        (3, 3),  # Last item of 3 (this was the bug case)
        (5, 5),  # Last item of 5
    ]
    
    for total, current in scenarios:
        next_id = test_secondary_id_calculation(total, current)
        print(f"Total: {total}, Current: {current} → Next: {next_id}")
        
        if current == total and next_id == 1:
            print(f"  ✅ CORRECT: Last item ({current}) correctly points to first item (1)")
        elif next_id == current + 1:
            print(f"  ✅ CORRECT: Item {current} points to next item {next_id}")
        else:
            print(f"  ❌ ERROR: Unexpected next_id calculation")

if __name__ == "__main__":
    print("🚀 Testing the implemented fixes...\n")
    
    try:
        test_strict_matching()
        test_search_term_extraction()
        test_interactive_message_logic()
        
        print("\n✅ All tests completed! Check the results above for any issues.")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
