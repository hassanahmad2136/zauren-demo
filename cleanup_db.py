#!/usr/bin/env python3
"""
Database cleanup script to remove duplicate interactive_messages
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client

def cleanup_interactive_messages():
    """Remove all existing interactive messages to prevent constraint violations"""
    try:
        # Initialize Supabase client
        supabase_client = create_client(
            os.getenv("INVENTORY_SUPABASE_URL"), 
            os.getenv("INVENTORY_SUPABASE_KEY")
        )
        
        # Count existing records
        count_response = supabase_client.table('interactive_messages').select('id').execute()
        existing_count = len(count_response.data) if count_response.data else 0
        
        print(f"Found {existing_count} existing interactive message records")
        
        if existing_count > 0:
            # Delete all records to prevent constraint violations
            delete_response = supabase_client.table('interactive_messages').delete().neq('id', '').execute()
            print(f"✅ Cleaned up interactive_messages table")
        else:
            print("✅ No records to clean up")
            
        return True
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False

if __name__ == "__main__":
    print("🧹 Starting database cleanup...")
    
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    success = cleanup_interactive_messages()
    
    if success:
        print("✅ Database cleanup completed successfully!")
        print("You can now restart the application.")
    else:
        print("❌ Database cleanup failed!")
