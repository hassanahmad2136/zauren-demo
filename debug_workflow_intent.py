#!/usr/bin/env python3
"""
Debug the actual workflow intent classification
"""

import asyncio
import sys
import httpx
sys.path.insert(0, '/home/ec2-user/retail-ai')

async def debug_workflow_intent():
    """Debug the actual workflow intent classification process"""
    
    print("🔍 Debugging Workflow Intent Classification...")
    print("=" * 60)
    
    # Test 1: Check what the orchestrator actually does
    print("1. Testing with different message types...")
    
    test_cases = [
        {"content": "I want to buy Nike shoes", "expected": "product_search"},
        {"content": "Show me my cart", "expected": "cart_management"},
        {"content": "I need help with my order", "expected": "order_support"},
        {"content": "Hello there", "expected": "general"},
        {"content": "Find me red dresses under $50", "expected": "product_search"},
        {"content": "Add this to my cart", "expected": "cart_management"},
        {"content": "Where is my order?", "expected": "order_support"},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: '{test_case['content']}'")
        print(f"   Expected: {test_case['expected']}")
        
        message = {
            "user_id": f"debug_user_{i}",
            "tenant_id": "debug_tenant",
            "channel": "console",
            "channel_user_id": f"debug_user_{i}",
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
                    
                    # Extract the actual intent from response
                    actual_intent = "unknown"
                    if "response" in result:
                        response_data = result["response"]
                        if "intent" in response_data:
                            actual_intent = response_data["intent"]
                        elif "metadata" in response_data and "intent" in response_data["metadata"]:
                            actual_intent = response_data["metadata"]["intent"]
                    
                    print(f"   ✅ Actual: {actual_intent}")
                    print(f"   Match: {'✅' if actual_intent == test_case['expected'] else '❌'}")
                    print(f"   Response time: {result.get('processing_time_ms', 0)}ms")
                    
                    # Check if response contains useful info
                    if "response" in result:
                        resp = result["response"]
                        if "content" in resp:
                            print(f"   Content preview: {resp['content'][:100]}...")
                        
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                    print(f"   Response: {response.text}")
                    
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
    
    # Test 2: Check orchestrator stats after our tests
    print(f"\n" + "=" * 60)
    print("2. Checking Updated Stats...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/stats", timeout=5.0)
            if response.status_code == 200:
                stats = response.json()
                print(f"📊 Stats after testing:")
                print(f"   Total processed: {stats['stats']['total_processed']}")
                print(f"   Avg execution time: {stats['stats']['avg_execution_time']:.1f}ms")
                print(f"   Intent distribution: {stats['stats']['intents_distribution']}")
                print(f"   Languages: {stats['stats']['languages_processed']}")
                
                # If intents_distribution is still empty, that's the bug!
                if not stats['stats']['intents_distribution']:
                    print("   🚨 ISSUE FOUND: intents_distribution is empty!")
                    print("   This means intents are not being recorded in stats")
                
    except Exception as e:
        print(f"❌ Stats check failed: {e}")
    
    # Test 3: Direct workflow engine testing
    print(f"\n" + "=" * 60)  
    print("3. Testing Workflow Engine Direct...")
    
    try:
        from apps.orchestrator.workflow_engine import RetailWorkflow
        from core.llm.groq_client import GroqClient
        from core.database.redis_client import RedisClient
        from apps.orchestrator.context_manager import ContextManager
        
        # Initialize components
        groq_client = GroqClient()
        await groq_client.initialize()
        
        redis_client = RedisClient()
        await redis_client.connect()
        
        context_manager = ContextManager(redis_client)
        
        # Create workflow
        workflow = RetailWorkflow(groq_client, context_manager)
        
        print("✅ Workflow components initialized")
        
        # Test the workflow directly if possible
        if hasattr(workflow, 'classify_intent'):
            print("🧪 Testing classify_intent method directly...")
            
            test_state = {
                "messages": [{"user": "I want to buy Nike shoes"}],
                "user_id": "direct_test_user",
                "tenant_id": "direct_test_tenant"
            }
            
            result = await workflow.classify_intent(test_state)
            print(f"   Direct classification result: {result}")
        else:
            print("❌ No classify_intent method found")
            workflow_methods = [m for m in dir(workflow) if not m.startswith('_')]
            print(f"   Available methods: {workflow_methods}")
            
    except Exception as e:
        print(f"❌ Direct workflow test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_workflow_intent())