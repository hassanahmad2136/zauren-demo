#!/usr/bin/env python3
"""
Redis Diagnostic Script for Retail AI Platform
Checks Redis connectivity and configuration issues
"""

import sys
import subprocess
import socket

def check_redis_process():
    """Check if Redis process is running"""
    try:
        result = subprocess.run(['pgrep', 'redis-server'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"✅ Redis process found (PIDs: {', '.join(pids)})")
            return True
        else:
            print("❌ No Redis process found")
            return False
    except Exception as e:
        print(f"❌ Error checking Redis process: {e}")
        return False

def check_redis_port():
    """Check if Redis port 6379 is listening"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 6379))
        sock.close()
        
        if result == 0:
            print("✅ Redis port 6379 is listening")
            return True
        else:
            print("❌ Redis port 6379 is not listening")
            return False
    except Exception as e:
        print(f"❌ Error checking Redis port: {e}")
        return False

def test_redis_cli():
    """Test Redis with redis-cli"""
    try:
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("✅ Redis CLI test successful")
            return True
        else:
            print(f"❌ Redis CLI test failed: {result.stdout} {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Redis CLI test timed out")
        return False
    except FileNotFoundError:
        print("⚠️  redis-cli not found, trying alternative tests")
        return False
    except Exception as e:
        print(f"❌ Redis CLI test error: {e}")
        return False

def check_python_redis():
    """Test Python Redis client"""
    try:
        import redis
        print("✅ Python redis module found")
        
        # Try to connect
        r = redis.Redis(host='localhost', port=6379, decode_responses=True, socket_timeout=5)
        response = r.ping()
        if response:
            print("✅ Python Redis connection successful")
            
            # Test basic operations
            r.set('test_key', 'test_value')
            value = r.get('test_key')
            r.delete('test_key')
            
            if value == 'test_value':
                print("✅ Redis read/write operations working")
                return True
            else:
                print("❌ Redis read/write operations failed")
                return False
        else:
            print("❌ Python Redis ping failed")
            return False
            
    except ImportError:
        print("❌ Python redis module not installed")
        print("   Install with: pip install redis")
        return False
    except redis.ConnectionError as e:
        print(f"❌ Python Redis connection error: {e}")
        return False
    except redis.TimeoutError:
        print("❌ Python Redis connection timeout")
        return False
    except Exception as e:
        print(f"❌ Python Redis error: {e}")
        return False

def get_redis_config():
    """Get Redis configuration"""
    try:
        result = subprocess.run(['redis-cli', 'CONFIG', 'GET', '*'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            config = {}
            for i in range(0, len(lines), 2):
                if i + 1 < len(lines):
                    config[lines[i]] = lines[i + 1]
            
            print("\n📋 Redis Configuration:")
            important_configs = ['port', 'bind', 'protected-mode', 'requirepass', 'maxmemory']
            for key in important_configs:
                if key in config:
                    print(f"   {key}: {config[key]}")
                    
            return config
        else:
            print("❌ Could not get Redis config")
            return {}
    except Exception as e:
        print(f"❌ Error getting Redis config: {e}")
        return {}

def suggest_fixes():
    """Suggest potential fixes"""
    print("\n🔧 Potential Fixes:")
    print("1. Start Redis manually:")
    print("   redis-server")
    print("   OR")
    print("   sudo systemctl start redis")
    print()
    print("2. Check Redis configuration:")
    print("   redis-cli CONFIG GET bind")
    print("   redis-cli CONFIG GET protected-mode")
    print()
    print("3. Install Redis if not installed:")
    print("   # Amazon Linux 2:")
    print("   sudo amazon-linux-extras install redis6")
    print("   # OR")
    print("   sudo yum install redis")
    print()
    print("4. Install Python Redis client:")
    print("   pip install redis")
    print()
    print("5. Check if Redis is bound to localhost:")
    print("   netstat -tlnp | grep 6379")

def main():
    print("🔍 Redis Diagnostic Report")
    print("=" * 50)
    
    # Run all checks
    process_ok = check_redis_process()
    port_ok = check_redis_port()
    cli_ok = test_redis_cli()
    python_ok = check_python_redis()
    
    # Get config if possible
    config = get_redis_config()
    
    print("\n📊 Summary:")
    print(f"   Process Running: {'✅' if process_ok else '❌'}")
    print(f"   Port Listening: {'✅' if port_ok else '❌'}")
    print(f"   CLI Working: {'✅' if cli_ok else '❌'}")
    print(f"   Python Client: {'✅' if python_ok else '❌'}")
    
    if all([process_ok, port_ok, python_ok]):
        print("\n🎉 Redis is working perfectly!")
        return True
    else:
        suggest_fixes()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)