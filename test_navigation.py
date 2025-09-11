#!/usr/bin/env python3
"""
Test the interactive message secondary_id logic
"""

def test_navigation_logic():
    """Test the navigation logic for interactive messages"""
    
    def calculate_next_index(current_i, total_items):
        """Simulate the fixed logic"""
        return current_i + 1 if current_i < total_items else 1
    
    print("🧪 Testing Navigation Logic...")
    
    # Test with 3 items
    print("\n📝 Testing with 3 items:")
    for i in range(1, 4):  # Items 1, 2, 3
        next_i = calculate_next_index(i, 3)
        print(f"  Item {i} → Next: {next_i}")
        
    # Test with 5 items  
    print("\n📝 Testing with 5 items:")
    for i in range(1, 6):  # Items 1, 2, 3, 4, 5
        next_i = calculate_next_index(i, 5)
        print(f"  Item {i} → Next: {next_i}")
        
    print("\n✅ Logic test complete!")

if __name__ == "__main__":
    test_navigation_logic()
