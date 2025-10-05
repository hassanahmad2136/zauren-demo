#!/usr/bin/env python3
"""
Simple debug to check actual class signatures
"""

import sys
sys.path.insert(0, '/home/ec2-user/retail-ai')

def check_classes():
    """Check the actual class signatures"""
    
    print("🔍 Checking Actual Class Signatures...")
    print("=" * 50)
    
    # Check ContextManager
    try:
        from apps.orchestrator.context_manager import ContextManager
        print("✅ ContextManager imported")
        
        # Check its __init__ method
        init_method = ContextManager.__init__
        print(f"ContextManager.__init__ signature: {init_method}")
        
        # Try to see the source or docs
        if hasattr(init_method, '__doc__'):
            print(f"ContextManager.__init__ docs: {init_method.__doc__}")
            
        # Try creating without parameters
        try:
            cm = ContextManager()
            print("✅ ContextManager() - no parameters works")
        except Exception as e:
            print(f"❌ ContextManager() failed: {e}")
            
    except Exception as e:
        print(f"❌ ContextManager import failed: {e}")
    
    # Check RetailWorkflow
    try:
        from apps.orchestrator.workflow_engine import RetailWorkflow
        print("✅ RetailWorkflow imported")
        
        # Check its __init__ method
        init_method = RetailWorkflow.__init__
        print(f"RetailWorkflow.__init__ signature: {init_method}")
        
        if hasattr(init_method, '__doc__'):
            print(f"RetailWorkflow.__init__ docs: {init_method.__doc__}")
            
        # Check available methods
        methods = [m for m in dir(RetailWorkflow) if not m.startswith('_') and callable(getattr(RetailWorkflow, m))]
        print(f"RetailWorkflow methods: {methods}")
        
    except Exception as e:
        print(f"❌ RetailWorkflow import failed: {e}")
    
    # Check what's actually in the orchestrator main.py
    print(f"\n🔍 Checking how orchestrator initializes components...")
    try:
        # Let's see how main.py actually creates these objects
        with open('/home/ec2-user/retail-ai/apps/orchestrator/main.py', 'r') as f:
            content = f.read()
            
        # Look for initialization patterns
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'ContextManager' in line or 'RetailWorkflow' in line:
                print(f"Line {i+1}: {line.strip()}")
                
    except Exception as e:
        print(f"❌ Could not read main.py: {e}")

if __name__ == "__main__":
    check_classes()