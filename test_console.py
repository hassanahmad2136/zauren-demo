# test_console.py
"""
Console test script for message bus
Run this to test your message bus interactively
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Dict, Any

class MessageBusConsoleTest:
    """Interactive console for testing message bus"""
    
    def __init__(self, message_bus_url: str = "http://localhost:8000"):
        self.message_bus_url = message_bus_url
        self.default_tenant_id = "test_retailer"
        self.default_user_id = "console_test_user"
        self.session_count = 0
        
    async def test_connection(self):
        """Test if message bus is running"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.message_bus_url}/health")
                if response.status_code == 200:
                    print("✅ Message Bus is running!")
                    print(f"📍 Health check: {response.json()}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"❌ Cannot connect to message bus: {e}")
            print(f"   Make sure it's running on {self.message_bus_url}")
            return False
    
    async def send_console_message(self, content: str, user_id: str = None, 
                                 tenant_id: str = None) -> Dict[str, Any]:
        """Send a message through console channel"""
        message_data = {
            "content": content,
            "user_id": user_id or self.default_user_id,
            "metadata": {
                "source": "console_test",
                "session_id": f"test_session_{self.session_count}",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        headers = {
            "x-tenant-id": tenant_id or self.default_tenant_id,
            "x-api-key": "test_key",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.message_bus_url}/normalize/console",
                    json=message_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print("✅ Message processed successfully!")
                    print(f"📨 Normalized message:")
                    self._pretty_print_json(result)
                    return result
                
                elif response.status_code == 429:
                    print("⚠️  Rate limit exceeded!")
                    print(f"   {response.json()}")
                    return {"error": "rate_limited", "details": response.json()}
                
                else:
                    print(f"❌ Error {response.status_code}: {response.text}")
                    return {"error": "http_error", "status": response.status_code}
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return {"error": "request_failed", "details": str(e)}
    
    async def test_rate_limiting(self):
        """Test rate limiting by sending multiple messages quickly"""
        print("\n🔥 Testing rate limiting...")
        print("Sending 10 messages rapidly...")
        
        results = []
        for i in range(10):
            result = await self.send_console_message(f"Rate limit test message {i+1}")
            results.append(result)
            
            if "error" in result and result["error"] == "rate_limited":
                print(f"   Rate limit hit at message {i+1}")
                break
        
        success_count = len([r for r in results if "error" not in r])
        print(f"   ✅ {success_count} messages succeeded")
        print(f"   ❌ {len(results) - success_count} messages rate limited")
    
    async def test_different_channels(self):
        """Test normalization for different channels (mock data)"""
        print("\n📱 Testing different channel formats...")
        
        # Test WhatsApp format
        whatsapp_data = {
            "messages": [{
                "from": "1234567890",
                "body": "Hello from WhatsApp test",
                "timestamp": str(int(datetime.now().timestamp())),
                "id": "wamid_test_123"
            }],
            "contacts": [{
                "profile": {"name": "Test User"},
                "wa_id": "1234567890"
            }]
        }
        
        # Test Web format  
        web_data = {
            "session_id": "web_test_session_123",
            "message": "Hello from web widget test",
            "user_info": {
                "email": "test@example.com",
                "name": "Test User"
            },
            "page_info": {
                "url": "https://teststore.com/products",
                "title": "Test Store - Products"
            }
        }
        
        test_cases = [
            ("whatsapp", whatsapp_data),
            ("web", web_data)
        ]
        
        headers = {
            "x-tenant-id": self.default_tenant_id,
            "x-api-key": "test_key",
            "Content-Type": "application/json"
        }
        
        for channel, data in test_cases:
            print(f"\n   Testing {channel} channel...")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.message_bus_url}/normalize/{channel}",
                        json=data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        print(f"   ✅ {channel} normalization successful")
                        result = response.json()
                        print(f"      User ID: {result.get('user_id')}")
                        print(f"      Content: {result.get('content')}")
                    else:
                        print(f"   ❌ {channel} failed: {response.status_code}")
                        
            except Exception as e:
                print(f"   ❌ {channel} error: {e}")
    
    async def get_system_metrics(self):
        """Get system metrics and status"""
        print("\n📊 Getting system metrics...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Health check
                health = await client.get(f"{self.message_bus_url}/health")
                print(f"   Health: {health.json() if health.status_code == 200 else 'Failed'}")
                
                # Metrics  
                metrics = await client.get(f"{self.message_bus_url}/metrics")
                if metrics.status_code == 200:
                    print("   📈 Rate limiting metrics:")
                    self._pretty_print_json(metrics.json())
                else:
                    print(f"   📈 Metrics endpoint returned: {metrics.status_code}")
                
                # Supported channels
                channels = await client.get(f"{self.message_bus_url}/channels")
                if channels.status_code == 200:
                    supported = [ch["name"] for ch in channels.json()["supported_channels"]]
                    print(f"   🔗 Supported channels: {', '.join(supported)}")
                else:
                    print(f"   🔗 Channels endpoint returned: {channels.status_code}")
                    
        except Exception as e:
            print(f"   ❌ Failed to get metrics: {e}")
    
    def _pretty_print_json(self, data: Dict[str, Any], indent: int = 4):
        """Pretty print JSON data"""
        print(json.dumps(data, indent=2, default=str))
    
    async def interactive_mode(self):
        """Interactive console mode"""
        print("\n🎮 Interactive Mode - Type messages to test!")
        print("Commands:")
        print("  /quit          - Exit")
        print("  /user <id>     - Change user ID")  
        print("  /tenant <id>   - Change tenant ID")
        print("  /test-rate     - Test rate limiting")
        print("  /test-channels - Test different channels")
        print("  /metrics       - Show system metrics")
        print("  /help          - Show this help")
        print("="*50)
        
        while True:
            try:
                user_input = input(f"\n[{self.default_user_id}@{self.default_tenant_id}] > ").strip()
                
                if not user_input:
                    continue
                
                if user_input == "/quit":
                    print("👋 Goodbye!")
                    break
                
                elif user_input.startswith("/user "):
                    self.default_user_id = user_input.split(" ", 1)[1]
                    print(f"✅ User ID changed to: {self.default_user_id}")
                
                elif user_input.startswith("/tenant "):
                    self.default_tenant_id = user_input.split(" ", 1)[1]
                    print(f"✅ Tenant ID changed to: {self.default_tenant_id}")
                
                elif user_input == "/test-rate":
                    await self.test_rate_limiting()
                
                elif user_input == "/test-channels":
                    await self.test_different_channels()
                
                elif user_input == "/metrics":
                    await self.get_system_metrics()
                
                elif user_input == "/help":
                    print("Commands: /quit, /user <id>, /tenant <id>, /test-rate, /test-channels, /metrics")
                
                else:
                    # Send as regular message
                    self.session_count += 1
                    await self.send_console_message(user_input)
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

async def main():
    """Main test function"""
    print("🚀 Message Bus Console Tester")
    print("="*40)
    
    tester = MessageBusConsoleTest()
    
    # Test connection first
    if not await tester.test_connection():
        print("\n💡 To start the message bus, run:")
        print("   uvicorn apps.message_bus.main:app --host 0.0.0.0 --port 8000 --reload")
        return
    
    print("\n✅ Connection successful! Choose test mode:")
    print("1. Send a single test message")
    print("2. Test rate limiting") 
    print("3. Test different channels")
    print("4. Interactive mode")
    print("5. System metrics")
    
    try:
        choice = input("\nEnter choice (1-5) or press Enter for interactive mode: ").strip()
        
        if choice == "1":
            await tester.send_console_message("Hello from console test!")
        
        elif choice == "2":
            await tester.test_rate_limiting()
        
        elif choice == "3":
            await tester.test_different_channels()
        
        elif choice == "4" or not choice:
            await tester.interactive_mode()
        
        elif choice == "5":
            await tester.get_system_metrics()
        
        else:
            print("Invalid choice, starting interactive mode...")
            await tester.interactive_mode()
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())