#!/usr/bin/env python3
"""
Test the enhanced strict matching rules
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.db_inventory import strict_product_search
from app.services.llm_product_search import validate_product_recommendations, extract_search_terms

def test_enhanced_strict_matching():
    """Test the enhanced strict matching rules"""
    print("🧪 Testing Enhanced Strict Matching Rules...\n")
    
    # Test cases that should be very strict
    test_cases = [
        {
            'query': 'blue clothes',
            'expected_behavior': 'Should only return PRIMARILY blue items, no green with blue hints'
        },
        {
            'query': 'green kurta',
            'expected_behavior': 'Should only return PRIMARILY green kurtas'
        },
        {
            'query': 'plain waistcoat',
            'expected_behavior': 'Should only return waistcoats WITHOUT embroidery or patterns'
        },
        {
            'query': 'embroidered kurta',
            'expected_behavior': 'Should only return kurtas WITH embroidery mentioned'
        },
        {
            'query': 'cotton shalwar',
            'expected_behavior': 'Should only return shalwars made of cotton'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"📝 Test {i}: '{test_case['query']}'")
        print(f"Expected: {test_case['expected_behavior']}")
        
        # Extract search terms
        search_terms = extract_search_terms(test_case['query'])
        print(f"Search terms: {search_terms}")
        
        # Test strict search
        results = strict_product_search(search_terms, exact_match=True)
        
        if results['status'] == 'success':
            print(f"Found {len(results['data'])} results:")
            
            for product in results['data'][:3]:  # Show first 3 results
                name = product.get('name', 'Unknown')
                color = product.get('color', 'N/A')
                material = product.get('material', 'N/A')
                desc = product.get('description', '')[:100] + "..."
                
                print(f"  - {name}")
                print(f"    Color: {color}, Material: {material}")
                print(f"    Description: {desc}")
                
                # Manual validation
                query_lower = test_case['query'].lower()
                name_lower = name.lower()
                
                if 'blue' in query_lower and 'green' in name_lower and 'blue' not in name_lower:
                    print(f"    ❌ WARNING: Found green item in blue search!")
                elif 'plain' in query_lower and any(term in desc.lower() for term in ['embroidered', 'embroidery', 'pattern']):
                    print(f"    ❌ WARNING: Found patterned item in plain search!")
                else:
                    print(f"    ✅ Looks correct")
        else:
            print(f"Error: {results.get('error', 'Unknown error')}")
        
        print("-" * 50)
    
    print("\n✅ Enhanced strict matching test completed!")

if __name__ == "__main__":
    try:
        test_enhanced_strict_matching()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
