#!/bin/bash
# stop_services.sh
# Stop script for Retail AI Platform

echo "🛑 Stopping Retail AI Platform Services..."
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stop services using PID files
if [ -f logs/message_bus.pid ]; then
    MB_PID=$(cat logs/message_bus.pid)
    if ps -p $MB_PID > /dev/null; then
        echo -e "${YELLOW}Stopping Message Bus (PID: $MB_PID)...${NC}"
        kill $MB_PID
        rm logs/message_bus.pid
        echo -e "${GREEN}✅ Message Bus stopped${NC}"
    else
        echo "Message Bus not running"
    fi
else
    echo "Message Bus PID file not found"
fi

if [ -f logs/orchestrator.pid ]; then
    ORCH_PID=$(cat logs/orchestrator.pid)
    if ps -p $ORCH_PID > /dev/null; then
        echo -e "${YELLOW}Stopping Orchestrator (PID: $ORCH_PID)...${NC}"
        kill $ORCH_PID
        rm logs/orchestrator.pid
        echo -e "${GREEN}✅ Orchestrator stopped${NC}"
    else
        echo "Orchestrator not running"
    fi
else
    echo "Orchestrator PID file not found"
fi

# Kill any remaining processes on ports
echo -e "\n${YELLOW}Cleaning up ports...${NC}"
for port in 8000 8001; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "Killing remaining process on port $port"
        lsof -ti:$port | xargs kill -9 2>/dev/null
    fi
done

echo -e "\n========================================="
echo -e "${GREEN}✅ All services stopped${NC}"
echo "========================================="