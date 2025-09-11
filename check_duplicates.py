#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict

load_dotenv()

def check_interactive_messages():
    """Check for duplicate secondary_ids in interactive_messages table"""
    
    supabase = create_client(os.getenv('INVENTORY_SUPABASE_URL'), os.getenv('INVENTORY_SUPABASE_KEY'))
    
    # Get all interactive messages
    result = supabase.table('interactive_messages').select('secondary_id, id, body').execute()
    
    print(f"📊 Total interactive messages: {len(result.data)}")
    
    # Group by secondary_id to find duplicates
    groups = defaultdict(list)
    for msg in result.data:
        if msg['secondary_id']:
            groups[msg['secondary_id']].append(msg)
    
    # Find duplicates
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    
    print(f"🔍 Duplicate secondary_ids found: {len(duplicates)}")
    
    if duplicates:
        print("\n🚨 Duplicate entries:")
        for sec_id, messages in list(duplicates.items())[:10]:  # Show first 10 duplicates
            print(f"\n  Secondary ID: {sec_id}")
            print(f"  Duplicate count: {len(messages)}")
            for i, msg in enumerate(messages[:3]):  # Show first 3 of each duplicate
                body_preview = msg['body'][:50] if msg['body'] else 'No body'
                print(f"    [{i+1}] ID: {msg['id']}")
                print(f"        Body: {body_preview}...")
    else:
        print("✅ No duplicates found!")

if __name__ == "__main__":
    check_interactive_messages()
