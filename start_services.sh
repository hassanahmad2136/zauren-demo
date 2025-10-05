#!/bin/bash

# start_services.sh - Fixed version for EC2 environment
# Retail AI Platform Service Startup Script

set -e  # Exit on any error

echo "🚀 Starting Retail AI Platform Services..."
echo "========================================="

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $port is already in use"
        return 0
    else
        return 1
    fi
}

# Function to find Python executable
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python" 
    else
        echo "❌ Error: Python not found. Please install Python 3.7+"
        exit 1
    fi
}

# Get the correct Python command
PYTHON_CMD=$(find_python)
echo "📍 Using Python: $PYTHON_CMD"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment active: $(basename $VIRTUAL_ENV)"
else
    echo "⚠️  Warning: No virtual environment detected"
fi

echo "Checking for existing services..."

# 1. Check Redis
echo "1. Checking Redis..."
if systemctl is-active --quiet redis 2>/dev/null; then
    echo "Redis is already running (systemctl)"
elif pgrep redis-server > /dev/null; then
    echo "Redis is already running (process)"
else
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   sudo systemctl start redis"
    echo "   OR"  
    echo "   redis-server &"
    exit 1
fi

# Test Redis connection
if $PYTHON_CMD -c "import redis; r=redis.Redis(); r.ping()" 2>/dev/null; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis connection failed"
    exit 1
fi

# 2. Start Message Bus Service
echo "2. Starting Message Bus (Port 8000)..."
if check_port 8000; then
    echo "✅ Message Bus already running on port 8000"
    MESSAGE_BUS_PID=$(lsof -ti:8000)
    echo "Message Bus PID: $MESSAGE_BUS_PID"
else
    cd apps/message_bus
    nohup $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port 8000 > ../../logs/message_bus.log 2>&1 &
    MESSAGE_BUS_PID=$!
    cd ../..
    
    # Wait a moment and check if it started
    sleep 3
    if kill -0 $MESSAGE_BUS_PID 2>/dev/null; then
        echo "Message Bus PID: $MESSAGE_BUS_PID"
        echo "✅ Message Bus started successfully"
    else
        echo "❌ Message Bus failed to start"
        echo "Check logs/message_bus.log for details"
        cat logs/message_bus.log
        exit 1
    fi
fi

# 3. Start Orchestrator Service  
echo "3. Starting Orchestrator (Port 8001)..."
if check_port 8001; then
    echo "✅ Orchestrator already running on port 8001"
    ORCHESTRATOR_PID=$(lsof -ti:8001)
    echo "Orchestrator PID: $ORCHESTRATOR_PID"
else
    cd apps/orchestrator
    nohup $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port 8001 > ../../logs/orchestrator.log 2>&1 &
    ORCHESTRATOR_PID=$!
    cd ../..
    
    # Wait a moment and check if it started
    sleep 3
    if kill -0 $ORCHESTRATOR_PID 2>/dev/null; then
        echo "Orchestrator PID: $ORCHESTRATOR_PID"
        echo "✅ Orchestrator started successfully"
    else
        echo "❌ Orchestrator failed to start"
        echo "Check logs/orchestrator.log for details"
        cat logs/orchestrator.log
        exit 1
    fi
fi

# 4. Health Check All Services
echo "4. Running health checks..."
sleep 2

# Check Message Bus
echo -n "Message Bus: "
if curl -s -f http://localhost:8000/health > /dev/null; then
    echo "✅ Healthy"
else
    echo "❌ Unhealthy"
fi

# Check Orchestrator  
echo -n "Orchestrator: "
if curl -s -f http://localhost:8001/health > /dev/null; then
    echo "✅ Healthy" 
else
    echo "❌ Unhealthy"
fi

# 5. Save PIDs for easy stopping
echo "$MESSAGE_BUS_PID" > .message_bus.pid 2>/dev/null || true
echo "$ORCHESTRATOR_PID" > .orchestrator.pid 2>/dev/null || true

echo ""
echo "🎉 All services started successfully!"
echo "========================================="
echo "📊 Service Status:"
echo "  • Redis: Running"
echo "  • Message Bus: http://localhost:8000 (PID: $MESSAGE_BUS_PID)"
echo "  • Orchestrator: http://localhost:8001 (PID: $ORCHESTRATOR_PID)"
echo ""
echo "📋 Useful Commands:"
echo "  • View logs: tail -f logs/message_bus.log"
echo "  • View logs: tail -f logs/orchestrator.log" 
echo "  • Stop services: sudo bash stop_services.sh"
echo "  • Test system: python test_orchestrator.py"
echo ""
echo "✅ Platform is ready for testing!"