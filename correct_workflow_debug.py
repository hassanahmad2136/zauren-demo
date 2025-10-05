#!/usr/bin/env python3
"""
Debug workflow intent classification with correct initialization
"""

import asyncio
import sys
import httpx
sys.path.insert(0, '/home/ec2-user/retail-ai')

async def debug_workflow_intent():
    """Debug the workflow intent classification with proper initialization"""
    
    print("🔍 Debugging Workflow Intent Classification (Corrected)...")
    print("=" * 60)
    
    # Test 1: Direct workflow testing with correct initialization
    print("1. Testing Workflow Components Directly...")
    
    try:
        from apps.orchestrator.context_manager import ContextManager
        from apps.orchestrator.workflow_engine import RetailWorkflow
        from core.llm.groq_client import GroqClient
        from core.database.redis_client import RedisClient
        
        # Initialize components the same way as main.py
        context_manager = ContextManager()  # No parameters
        workflow_engine = RetailWorkflow()  # No parameters
        
        print("✅ Components initialized correctly")
        print(f"✅ RetailWorkflow methods: {[m for m in dir(workflow_engine) if not m.startswith('_')]}")
        
        # Test the classify_intent method directly
        print("\n🧪 Testing classify_intent method...")
        
        # Create a test state (check what format it expects)
        test_messages = [
            "I want to buy Nike shoes",
            "Show me my cart", 
            "I need help with my order",
            "Hello there"
        ]
        
        for message in test_messages:
            print(f"\n📝 Testing: '{message}'")
            
            # Try different state formats to see what works
            test_states = [
                # Format 1: Simple
                {"messages": [{"user": message}], "user_id": "test", "tenant_id": "test"},
                
                # Format 2: With current_message
                {"current_message": message, "user_id": "test", "tenant_id": "test"},
                
                # Format 3: Direct message
                {"message": message, "user_id": "test", "tenant_id": "test"}
            ]
            
            for i, state in enumerate(test_states):
                try:
                    result = await workflow_engine.classify_intent(state)
                    print(f"   ✅ State format {i+1} worked: {result}")
                    
                    # Extract the intent from result
                    if isinstance(result, dict):
                        intent = result.get('intent', result.get('classified_intent', 'unknown'))
                        print(f"   🎯 Extracted intent: {intent}")
                    else:
                        print(f"   🎯 Raw result: {result}")
                    
                    break  # If one format works, no need to try others
                    
                except Exception as e:
                    print(f"   ❌ State format {i+1} failed: {e}")
                    if i == len(test_states) - 1:  # Last attempt
                        print(f"   🚨 All state formats failed for this message")
        
    except Exception as e:
        print(f"❌ Direct workflow test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: HTTP endpoint testing with detailed analysis
    print(f"\n" + "=" * 60)
    print("2. Testing HTTP Endpoints with Intent Analysis...")
    
    test_cases = [
        {"content": "I want to buy Nike shoes", "expected": "product_search"},
        {"content": "Show me my cart", "expected": "cart_management"}, 
        {"content": "I need help with my order", "expected": "order_support"},
        {"content": "Hello there", "expected": "general"},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 HTTP Test {i}: '{test_case['content']}'")
        
        message = {
            "user_id": f"intent_test_{i}",
            "tenant_id": "intent_test_tenant",
            "channel": "console",
            "channel_user_id": f"intent_test_{i}",
            "content": test_case['content'],
            "timestamp": "2025-09-26T10:00:00Z",
            "metadata": {"test_case": i}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8001/process",
                    json=message,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    print(f"   📊 Full response structure:")
                    print(f"      Success: {result.get('success')}")
                    print(f"      Processing time: {result.get('processing_time_ms')}ms")
                    
                    # Deep dive into response structure
                    if "response" in result:
                        resp = result["response"]
                        print(f"      Response keys: {list(resp.keys())}")
                        
                        # Look for intent in all possible places
                        places_to_check = [
                            ("response.intent", resp.get("intent")),
                            ("response.classified_intent", resp.get("classified_intent")),
                            ("response.metadata.intent", resp.get("metadata", {}).get("intent")),
                            ("response.intent_classification", resp.get("intent_classification")),
                        ]
                        
                        for location, value in places_to_check:
                            if value:
                                print(f"      🎯 Found intent at {location}: {value}")
                                match = "✅" if value == test_case['expected'] else "❌"
                                print(f"      {match} Expected: {test_case['expected']}, Got: {value}")
                        
                        # Check if intent is buried in content
                        content = resp.get("content", "")
                        if content:
                            print(f"      📝 Response content preview: {content[:100]}...")
                            # Sometimes intent might be mentioned in the response text
                            for intent in ["product_search", "cart_management", "order_support", "general"]:
                                if intent in content.lower():
                                    print(f"      🔍 Found '{intent}' mentioned in response content")
                    
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                    print(f"   Response: {response.text}")
                    
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
    
    # Test 3: Check stats again
    print(f"\n" + "=" * 60)
    print("3. Final Stats Check...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/stats", timeout=5.0)
            if response.status_code == 200:
                stats = response.json()
                print(f"📊 Final Stats:")
                print(f"   Total processed: {stats['stats']['total_processed']}")
                print(f"   Intent distribution: {stats['stats']['intents_distribution']}")
                
                if not stats['stats']['intents_distribution']:
                    print("   🚨 CONFIRMED BUG: Intent distribution is still empty!")
                    print("   This means intents are being classified but not recorded in stats")
                else:
                    print("   ✅ Intent distribution is working!")
                
    except Exception as e:
        print(f"❌ Stats check failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_workflow_intent())