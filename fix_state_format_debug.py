#!/usr/bin/env python3
"""
Fix the state format issue and test intent classification
"""

import asyncio
import sys
import httpx
import json
sys.path.insert(0, '/home/ec2-user/retail-ai')

async def fix_and_test_intent():
    """Test intent classification with the correct state format"""
    
    print("🔧 Fixing State Format and Testing Intent Classification...")
    print("=" * 60)
    
    try:
        from apps.orchestrator.context_manager import ContextManager
        from apps.orchestrator.workflow_engine import RetailWorkflow
        
        context_manager = ContextManager()
        workflow_engine = RetailWorkflow()
        
        print("✅ Components initialized")
        
        # Test with the missing 'agents_used' field
        print("\n1. Testing with corrected state format...")
        
        test_messages = [
            ("I want to buy Nike shoes", "product_search"),
            ("Show me my cart", "cart_management"), 
            ("I need help with my order", "order_support"),
            ("Hello there", "general")
        ]
        
        for message, expected in test_messages:
            print(f"\n📝 Testing: '{message}'")
            
            # Add the missing 'agents_used' field that the error complained about
            correct_state = {
                "messages": [{"user": message}],
                "user_id": "test_user",
                "tenant_id": "test_tenant", 
                "agents_used": [],  # This was missing!
                "current_message": message,
                "conversation_history": [],
                "intent": None  # Initialize intent field
            }
            
            try:
                result = await workflow_engine.classify_intent(correct_state)
                print(f"   ✅ Classification successful!")
                print(f"   🎯 Result: {result}")
                
                # Check if result contains the state with classified intent
                if isinstance(result, dict):
                    classified_intent = result.get('intent', 'unknown')
                    print(f"   📊 Classified Intent: {classified_intent}")
                    print(f"   Match: {'✅' if classified_intent == expected else '❌'} (Expected: {expected})")
                    
                    # Show all keys in the result
                    print(f"   📋 Result keys: {list(result.keys())}")
                    
            except Exception as e:
                print(f"   ❌ Still failed: {e}")
                # Let's see what the method actually expects
                import inspect
                sig = inspect.signature(workflow_engine.classify_intent)
                print(f"   🔍 Method signature: {sig}")
    
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Fix the HTTP response parsing issue
    print(f"\n" + "=" * 60)
    print("2. Testing HTTP Response Structure...")
    
    try:
        async with httpx.AsyncClient() as client:
            message = {
                "user_id": "response_test",
                "tenant_id": "response_test_tenant",
                "channel": "console",
                "channel_user_id": "response_test",
                "content": "I want to buy Nike shoes",
                "timestamp": "2025-09-26T10:00:00Z",
                "metadata": {}
            }
            
            response = await client.post(
                "http://localhost:8001/process",
                json=message,
                timeout=15.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ HTTP Response received")
                print(f"📊 Response type: {type(result)}")
                print(f"📋 Response structure: {json.dumps(result, indent=2)}")
                
                # The issue was that result["response"] is a string, not a dict
                if "response" in result:
                    response_data = result["response"]
                    print(f"🔍 Response data type: {type(response_data)}")
                    
                    if isinstance(response_data, str):
                        print(f"🚨 ISSUE: Response is string, not dict!")
                        print(f"📝 Response content: {response_data}")
                        
                        # Check if it's JSON embedded in the string
                        try:
                            parsed_response = json.loads(response_data)
                            print(f"✅ Response contains embedded JSON: {parsed_response}")
                        except:
                            print(f"❌ Response is plain text, not JSON")
                    else:
                        print(f"✅ Response is proper dict: {response_data}")
                        
            else:
                print(f"❌ HTTP Error: {response.status_code}")
    
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")
    
    # Test 3: Check where intent should be recorded in stats
    print(f"\n" + "=" * 60)
    print("3. Investigating Stats Recording...")
    
    try:
        # Let's see if there's a method to manually update stats
        workflow_engine = RetailWorkflow()
        
        if hasattr(workflow_engine, 'get_stats'):
            stats = workflow_engine.get_stats()
            print(f"📊 Workflow internal stats: {stats}")
            
        if hasattr(workflow_engine, 'stats'):
            print(f"📊 Workflow stats attribute: {workflow_engine.stats}")
        
        # Check if there are methods to record intents
        stats_methods = [m for m in dir(workflow_engine) if 'stat' in m.lower() or 'record' in m.lower() or 'track' in m.lower()]
        print(f"📋 Stats-related methods: {stats_methods}")
        
    except Exception as e:
        print(f"❌ Stats investigation failed: {e}")

if __name__ == "__main__":
    asyncio.run(fix_and_test_intent())