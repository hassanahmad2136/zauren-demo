#!/usr/bin/env python3
"""
Simple test for strict matching validation
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_validation_logic():
    """Test the validation logic directly"""
    print("🧪 Testing Validation Logic...\n")
    
    # Test color detection
    test_queries = [
        "blue clothes",
        "green kurta", 
        "plain waistcoat",
        "embroidered shirt",
        "cotton shalwar"
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        
        # Simple color detection test
        query_lower = query.lower()
        colors = ['blue', 'green', 'red', 'black', 'white']
        materials = ['cotton', 'silk', 'velvet', 'linen']
        styles = ['embroidered', 'plain']
        
        found_colors = [c for c in colors if c in query_lower]
        found_materials = [m for m in materials if m in query_lower]
        found_styles = [s for s in styles if s in query_lower]
        
        print(f"  Colors: {found_colors}")
        print(f"  Materials: {found_materials}")
        print(f"  Styles: {found_styles}")
        print()
    
    # Test product validation logic
    print("Testing product validation...")
    
    # Mock product data
    test_products = [
        {
            'id': '1',
            'name': 'Blue Denim Kurta',
            'description': 'This is a blue kurta made of denim',
            'color': 'blue'
        },
        {
            'id': '2', 
            'name': 'Green Striped Kurta',
            'description': 'This is a green kurta with stripes and blue accents',
            'color': 'green'
        },
        {
            'id': '3',
            'name': 'Navy Blue Embroidered Kurta', 
            'description': 'This is an embroidered kurta in navy blue',
            'color': 'navy'
        }
    ]
    
    # Test blue search
    query = "blue clothes"
    print(f"\nTesting '{query}' against products:")
    
    for product in test_products:
        name_lower = product['name'].lower()
        desc_lower = product['description'].lower()
        
        # Check if product matches "blue" search
        matches_blue = False
        
        # Strict blue validation
        if 'blue' in name_lower and not any(other_color in name_lower for other_color in ['green', 'teal', 'navy', 'purple']):
            matches_blue = True
        elif 'blue' in name_lower and 'navy' not in name_lower:  # Allow "blue" but not "navy blue" for pure blue search
            matches_blue = True
            
        # Check for green contamination
        has_green_contamination = any(term in desc_lower for term in ['green', 'hint', 'accent', 'touch'])
        if has_green_contamination:
            matches_blue = False
            
        print(f"  {product['name']}: {'✅ MATCH' if matches_blue else '❌ NO MATCH'}")
        if not matches_blue and 'green' in desc_lower:
            print(f"    → Rejected: Contains green elements")
    
    print("\n✅ Validation logic test completed!")

if __name__ == "__main__":
    test_validation_logic()
