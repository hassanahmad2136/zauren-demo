#!/usr/bin/env python3
"""
Fixed debug script to test intent classification with actual methods
"""

import asyncio
import sys
import os
sys.path.insert(0, '/home/ec2-user/retail-ai')

async def test_intent_classification():
    """Test intent classification with actual available methods"""
    
    print("🔍 Testing Intent Classification (Fixed)...")
    print("=" * 50)
    
    # First, let's see what we actually have
    try:
        from core.llm.groq_client import GroqClient
        from config.settings import settings
        
        groq_client = GroqClient()
        print(f"✅ GroqClient imported successfully")
        print(f"Available methods: {[m for m in dir(groq_client) if not m.startswith('_') and callable(getattr(groq_client, m))]}")
        
        # Try to initialize
        await groq_client.initialize()
        print(f"✅ GroqClient initialized")
        
    except Exception as e:
        print(f"❌ GroqClient error: {e}")
        return
    
    # Test different method names that might exist
    test_message = "I want to buy Nike shoes"
    intent_prompt = f"""Classify the user's intent from this message: "{test_message}"

Available intents:
- product_search: User wants to find or browse products
- cart_management: User wants to add, remove, or view cart items  
- order_support: User needs help with orders, returns, or account
- general: Greeting, small talk, or unclear intent

Respond with ONLY the intent name, nothing else."""

    # Try different possible method names
    possible_methods = ['complete', 'chat_completion', 'create_completion', 'generate', 'call', 'ask']
    
    for method_name in possible_methods:
        if hasattr(groq_client, method_name):
            print(f"\n🔍 Found method: {method_name}")
            try:
                method = getattr(groq_client, method_name)
                print(f"Method signature: {method.__doc__ if hasattr(method, '__doc__') else 'No docs'}")
                
                # Try different parameter formats
                if method_name == 'complete':
                    result = await method(
                        messages=[{"role": "user", "content": intent_prompt}],
                        max_tokens=50,
                        temperature=0.1
                    )
                elif method_name in ['chat_completion', 'create_completion']:
                    result = await method(
                        messages=[{"role": "user", "content": intent_prompt}],
                        max_tokens=50,
                        temperature=0.1
                    )
                elif method_name == 'generate':
                    result = await method(intent_prompt)
                elif method_name == 'call':
                    result = await method(intent_prompt)
                elif method_name == 'ask':
                    result = await method(intent_prompt)
                
                print(f"✅ {method_name} worked! Result: '{result}'")
                break
                
            except Exception as e:
                print(f"❌ {method_name} failed: {e}")
    
    # Check workflow engine
    print(f"\n🔍 Checking Workflow Engine...")
    try:
        from apps.orchestrator import workflow_engine
        available_classes = [item for item in dir(workflow_engine) if not item.startswith('_') and isinstance(getattr(workflow_engine, item), type)]
        print(f"Available classes: {available_classes}")
        
        # Try to import whatever class exists
        if available_classes:
            WorkflowClass = getattr(workflow_engine, available_classes[0])
            print(f"✅ Found workflow class: {WorkflowClass}")
            
            # Check its methods
            workflow_methods = [m for m in dir(WorkflowClass) if not m.startswith('_') and callable(getattr(WorkflowClass, m))]
            print(f"Workflow methods: {workflow_methods}")
            
    except Exception as e:
        print(f"❌ Workflow engine error: {e}")
    
    # Check what's actually running in the orchestrator
    print(f"\n🔍 Checking Running Orchestrator...")
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Get orchestrator stats
            response = await client.get("http://localhost:8001/stats", timeout=5.0)
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Orchestrator stats: {stats}")
            
            # Try to see what endpoints exist
            response = await client.get("http://localhost:8001/", timeout=5.0)
            print(f"Root endpoint status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Orchestrator check error: {e}")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())