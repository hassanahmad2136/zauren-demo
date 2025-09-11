#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def test_interactive_navigation():
    """Test interactive message navigation logic"""
    
    supabase = create_client(os.getenv('INVENTORY_SUPABASE_URL'), os.getenv('INVENTORY_SUPABASE_KEY'))
    
    print("🧪 Testing Interactive Message Navigation...")
    
    # Simulate a button payload format
    test_payloads = [
        "12345678-91234567890-2-next",  # Click Next on product 2
        "12345678-91234567890-1-addtocart",  # Add to cart product 1
        "12345678-91234567890-3-details",  # View details of product 3
    ]
    
    for payload in test_payloads:
        print(f"\n🔍 Testing payload: {payload}")
        
        # Split the payload to extract parts
        parts = payload.split("-")
        print(f"  Parts: {parts}")
        
        if len(parts) >= 4:
            # Extract base parts (UUID + sender_id)
            base_parts = parts[:-2]  # Everything except last two (index and action)
            current_index = int(parts[-2])  # Current index
            action = parts[-1]  # Action (next, addtocart, details)
            
            print(f"  Base parts: {base_parts}")
            print(f"  Current index: {current_index}")
            print(f"  Action: {action}")
            
            # For "next" action, construct the next item query
            if action == "next":
                # Query pattern: secondary_id = payload
                print(f"  Looking for secondary_id: {payload}")
                
                # Show what button IDs would be generated in response
                show_index = current_index  # The item we're showing
                print(f"  Response buttons would be:")
                print(f"    Next: {'-'.join(base_parts + [str(show_index + 1), 'next'])}")
                print(f"    Add to Cart: {'-'.join(base_parts + [str(show_index + 1), 'addtocart'])}")
                print(f"    Details: {'-'.join(base_parts + [str(show_index + 1), 'details'])}")
        else:
            print(f"  ❌ Invalid payload format")
    
    print("\n✅ Navigation logic test completed!")
    
    # Test the actual database lookup
    print("\n🔍 Testing actual database lookups...")
    recent_messages = supabase.table('interactive_messages').select('id, secondary_id, body').limit(5).execute()
    
    if recent_messages.data:
        print("Recent interactive messages:")
        for msg in recent_messages.data:
            print(f"  ID: {msg['id']}")
            print(f"  Secondary ID: {msg['secondary_id']}")
            print(f"  Body: {msg['body'][:50]}...")
            print()
    else:
        print("No recent interactive messages found.")

if __name__ == "__main__":
    test_interactive_navigation()
