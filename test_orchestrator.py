# test_orchestrator.py
"""
Comprehensive test script for the Orchestrator and Message Bus
Tests the complete flow from message input to response generation
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any, List
import time

# Test configuration
MESSAGE_BUS_URL = "http://localhost:8000"
ORCHESTRATOR_URL = "http://localhost:8001"

class RetailAITester:
    """Test suite for the retail AI platform"""
    
    def __init__(self):
        self.message_bus = httpx.AsyncClient(base_url=MESSAGE_BUS_URL, timeout=30.0)
        self.orchestrator = httpx.AsyncClient(base_url=ORCHESTRATOR_URL, timeout=30.0)
        self.test_results = []
        
    async def test_health_checks(self):
        """Test that all services are healthy"""
        print("\n🔍 Testing Health Checks...")
        
        # Test Message Bus health
        try:
            response = await self.message_bus.get("/health")
            assert response.status_code == 200
            print("✅ Message Bus is healthy")
        except Exception as e:
            print(f"❌ Message Bus health check failed: {e}")
            
        # Test Orchestrator health
        try:
            response = await self.orchestrator.get("/health")
            assert response.status_code == 200
            data = response.json()
            print(f"✅ Orchestrator is healthy")
            print(f"   - Redis: {data['connections']['redis']}")
            print(f"   - Groq: {data['connections']['groq']}")
        except Exception as e:
            print(f"❌ Orchestrator health check failed: {e}")
    
    async def test_message_normalization(self):
        """Test message normalization for different channels"""
        print("\n🔍 Testing Message Normalization...")
        
        test_cases = [
            {
                "channel": "whatsapp",
                "data": {
                    "entry": [{
                        "changes": [{
                            "value": {
                                "messages": [{
                                    "from": "919876543210",
                                    "id": "msg_001",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": "Show me red shoes"}
                                }],
                                "contacts": [{
                                    "profile": {"name": "John Doe"},
                                    "wa_id": "919876543210"
                                }]
                            }
                        }]
                    }]
                },
                "headers": {"x-tenant-id": "test_retailer", "x-api-key": "test_key"}
            },
            {
                "channel": "web",
                "data": {
                    "session_id": "web_session_123",
                    "message": "I need help finding a gift",
                    "user_info": {
                        "email": "test@example.com",
                        "name": "Jane Smith"
                    }
                },
                "headers": {"x-tenant-id": "test_retailer", "x-api-key": "test_key"}
            }
        ]
        
        for test in test_cases:
            try:
                response = await self.message_bus.post(
                    f"/normalize/{test['channel']}",
                    json=test['data'],
                    headers=test['headers']
                )
                
                if response.status_code == 200:
                    normalized = response.json()
                    print(f"✅ {test['channel'].upper()} normalization successful")
                    print(f"   - User ID: {normalized['user_id']}")
                    print(f"   - Content: {normalized['content']}")
                else:
                    print(f"❌ {test['channel'].upper()} normalization failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ {test['channel'].upper()} test error: {e}")
    
    async def test_conversation_flow(self):
        """Test a complete conversation flow with context accumulation"""
        print("\n🔍 Testing Complete Conversation Flow...")
        
        # Simulate a multi-turn conversation
        conversation = [
            {"content": "Hello!", "expected_intent": "greeting"},
            {"content": "I'm looking for running shoes", "expected_intent": "product_search"},
            {"content": "Show me Nike ones", "expected_intent": "product_search"},
            {"content": "Under $200 please", "expected_intent": "product_search"},
            {"content": "I prefer red color", "expected_intent": "product_search"},
            {"content": "Add the first one to my cart", "expected_intent": "cart_action"},
            {"content": "What's your return policy?", "expected_intent": "support"}
        ]
        
        user_id = f"test_user_{int(time.time())}"
        tenant_id = "test_retailer"
        
        for i, turn in enumerate(conversation):
            print(f"\n📝 Turn {i+1}: '{turn['content']}'")
            
            # Create canonical message
            message = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "channel": "web",
                "channel_user_id": f"web_{user_id}",
                "content": turn["content"],
                "timestamp": datetime.now().isoformat(),
                "metadata": {"turn": i+1}
            }
            
            try:
                # Send to orchestrator
                response = await self.orchestrator.post("/process", json=message)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Processed successfully")
                    print(f"   - Intent: {result['metadata']['intent']} "
                          f"(confidence: {result['metadata'].get('confidence', 0):.2f})")
                    print(f"   - Language: {result['metadata']['language']}")
                    print(f"   - Response: {result['response'][:100]}...")
                    print(f"   - Execution time: {result['metadata']['execution_time_ms']}ms")
                    
                    # Check if intent matches expected
                    if result['metadata']['intent'] == turn['expected_intent']:
                        print(f"   ✅ Intent matched expected: {turn['expected_intent']}")
                    else:
                        print(f"   ⚠️ Intent mismatch - Expected: {turn['expected_intent']}, "
                              f"Got: {result['metadata']['intent']}")
                else:
                    print(f"❌ Processing failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Small delay between messages
            await asyncio.sleep(1)
        
        # Check final session state
        print("\n📊 Checking Final Session State...")
        try:
            response = await self.orchestrator.get(f"/session/{user_id}/{tenant_id}")
            if response.status_code == 200:
                session = response.json()
                print(f"✅ Session retrieved successfully")
                print(f"   - Message count: {session['message_count']}")
                print(f"   - Cart items: {len(session.get('cart_items', {}).get('items', []))}")
                print(f"   - Conversation context: {json.dumps(session['conversation_context'], indent=2)}")
        except Exception as e:
            print(f"❌ Session retrieval error: {e}")
    
    async def test_multilingual_support(self):
        """Test multilingual conversation support"""
        print("\n🔍 Testing Multilingual Support...")
        
        multilingual_tests = [
            {"content": "Bonjour, montrez-moi des chaussures", "language": "French"},
            {"content": "Hola, necesito zapatos deportivos", "language": "Spanish"},
            {"content": "مرحبا، أريد حذاء رياضي", "language": "Arabic"},
            {"content": "你好，我想买运动鞋", "language": "Chinese"},
            {"content": "Namaste, mujhe joote chahiye", "language": "Hindi"}
        ]
        
        for test in multilingual_tests:
            print(f"\n🌍 Testing {test['language']}: '{test['content']}'")
            
            message = {
                "user_id": f"multilingual_user_{int(time.time())}",
                "tenant_id": "test_retailer",
                "channel": "web",
                "channel_user_id": "web_multi",
                "content": test["content"],
                "timestamp": datetime.now().isoformat(),
                "metadata": {"test_language": test["language"]}
            }
            
            try:
                response = await self.orchestrator.post("/process", json=message)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Processed in {test['language']}")
                    print(f"   - Detected language: {result['metadata']['language']}")
                    print(f"   - Response preview: {result['response'][:100]}...")
                else:
                    print(f"❌ Failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
            
            await asyncio.sleep(0.5)
    
    async def test_search_entity_accumulation(self):
        """Test how search entity accumulates across messages"""
        print("\n🔍 Testing Search Entity Accumulation...")
        
        user_id = f"search_test_{int(time.time())}"
        tenant_id = "test_retailer"
        
        # Progressive refinement of search
        search_flow = [
            "I want to buy shoes",
            "Nike ones",
            "In red color",
            "Size 10",
            "Under $150",
            "Actually, make it blue instead of red"
        ]
        
        for i, query in enumerate(search_flow):
            print(f"\n🔎 Query {i+1}: '{query}'")
            
            message = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "channel": "web",
                "channel_user_id": f"web_{user_id}",
                "content": query,
                "timestamp": datetime.now().isoformat(),
                "metadata": {"query_number": i+1}
            }
            
            try:
                response = await self.orchestrator.post("/process", json=message)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Processed")
                    
                    # Get session to see search entity
                    session_response = await self.orchestrator.get(f"/session/{user_id}/{tenant_id}")
                    if session_response.status_code == 200:
                        # In production, we'd check the search_entity from session
                        print(f"   - Intent: {result['metadata']['intent']}")
                        print(f"   - Response: {result['response'][:150]}...")
                else:
                    print(f"❌ Failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
            
            await asyncio.sleep(0.5)
    
    async def test_performance_batch(self):
        """Test batch processing and performance"""
        print("\n🔍 Testing Batch Processing Performance...")
        
        # Create batch of messages
        batch_messages = []
        for i in range(10):
            batch_messages.append({
                "user_id": f"batch_user_{i}",
                "tenant_id": "test_retailer",
                "channel": "web",
                "channel_user_id": f"web_batch_{i}",
                "content": f"Show me product number {i}",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"batch_id": i}
            })
        
        try:
            start_time = time.time()
            response = await self.orchestrator.post("/process/batch", json=batch_messages)
            end_time = time.time()
            
            if response.status_code == 200:
                results = response.json()
                successful = sum(1 for r in results if r.get("success"))
                total_time = (end_time - start_time) * 1000
                avg_time = total_time / len(batch_messages)
                
                print(f"✅ Batch processing completed")
                print(f"   - Total messages: {len(batch_messages)}")
                print(f"   - Successful: {successful}")
                print(f"   - Total time: {total_time:.2f}ms")
                print(f"   - Average per message: {avg_time:.2f}ms")
            else:
                print(f"❌ Batch processing failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Batch test error: {e}")
    
    async def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n🔍 Testing Error Handling...")
        
        error_cases = [
            {
                "name": "Empty message",
                "message": {
                    "user_id": "error_test",
                    "tenant_id": "test_retailer",
                    "channel": "web",
                    "channel_user_id": "web_error",
                    "content": "",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {}
                }
            },
            {
                "name": "Very long message",
                "message": {
                    "user_id": "error_test",
                    "tenant_id": "test_retailer",
                    "channel": "web",
                    "channel_user_id": "web_error",
                    "content": "shoes " * 1000,  # Very long repetitive message
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {}
                }
            },
            {
                "name": "Special characters",
                "message": {
                    "user_id": "error_test",
                    "tenant_id": "test_retailer",
                    "channel": "web",
                    "channel_user_id": "web_error",
                    "content": "Show me shoes 👟 with price < $100 & size = 10",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {}
                }
            }
        ]
        
        for test_case in error_cases:
            print(f"\n⚠️ Testing: {test_case['name']}")
            
            try:
                response = await self.orchestrator.post("/process", json=test_case['message'])
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Handled successfully")
                    print(f"   - Response: {result['response'][:100]}...")
                else:
                    print(f"⚠️ Returned error status {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")
    
    async def test_stats_endpoint(self):
        """Test the statistics endpoint"""
        print("\n🔍 Testing Statistics Endpoint...")
        
        try:
            response = await self.orchestrator.get("/stats")
            
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Statistics retrieved")
                print(f"   - Total processed: {stats['stats']['total_processed']}")
                print(f"   - Average execution time: {stats['stats']['avg_execution_time']:.2f}ms")
                print(f"   - Intent distribution: {stats['stats']['intents_distribution']}")
                print(f"   - Languages processed: {stats['stats']['languages_processed']}")
            else:
                print(f"❌ Stats retrieval failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Stats test error: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.message_bus.aclose()
        await self.orchestrator.aclose()
    
    async def run_all_tests(self):
        """Run all test suites"""
        print("=" * 60)
        print("🚀 RETAIL AI PLATFORM - COMPREHENSIVE TEST SUITE")
        print("=" * 60)
        
        await self.test_health_checks()
        await self.test_message_normalization()
        await self.test_conversation_flow()
        await self.test_multilingual_support()
        await self.test_search_entity_accumulation()
        await self.test_performance_batch()
        await self.test_error_handling()
        await self.test_stats_endpoint()
        
        print("\n" + "=" * 60)
        print("✅ TEST SUITE COMPLETED")
        print("=" * 60)
        
        await self.cleanup()

async def main():
    """Main test execution"""
    tester = RetailAITester()
    
    # Wait a bit for services to be ready
    print("⏳ Waiting for services to initialize...")
    await asyncio.sleep(2)
    
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())