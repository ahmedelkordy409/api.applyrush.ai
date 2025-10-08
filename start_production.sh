#!/bin/bash

# ApplyRush.AI Production Startup Script
# Manages all backend services with proper process management

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/ahmed-elkordy/researchs/applyrush.ai/jobhire-ai-backend"
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$PROJECT_ROOT/pids"

# Create necessary directories
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

echo ""
echo "============================================================"
echo "  ApplyRush.AI Production Services Startup"
echo "============================================================"
echo ""

# Function to print colored messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to kill process by name pattern
kill_process() {
    local pattern=$1
    local name=$2

    print_status "Checking for existing $name processes..."
    if pgrep -f "$pattern" > /dev/null; then
        print_warning "Stopping existing $name processes..."
        pkill -f "$pattern" || true
        sleep 2

        # Force kill if still running
        if pgrep -f "$pattern" > /dev/null; then
            print_warning "Force killing $name processes..."
            pkill -9 -f "$pattern" || true
            sleep 1
        fi
        print_success "$name processes stopped"
    else
        print_success "No existing $name processes found"
    fi
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Step 1: Clean up existing processes
echo ""
print_status "Step 1: Cleaning up existing processes..."
echo "-----------------------------------------------------------"

kill_process "run_subscriptions_api.py" "Subscriptions API"
kill_process "uvicorn app.main:app" "Main Backend API"
kill_process "stripe listen" "Stripe Webhook Listener"

# Check if ports are free
if check_port 8001; then
    print_warning "Port 8001 is still in use. Waiting..."
    sleep 3
fi

print_success "Process cleanup completed"

# Step 2: Load environment variables
echo ""
print_status "Step 2: Loading environment configuration..."
echo "-----------------------------------------------------------"

cd "$PROJECT_ROOT"
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    print_success "Environment variables loaded from .env"
else
    print_warning "No .env file found, using system environment"
fi

# Step 3: Start Subscriptions API (Port 8001)
echo ""
print_status "Step 3: Starting Subscriptions API on port 8001..."
echo "-----------------------------------------------------------"

cd "$PROJECT_ROOT"
nohup python run_subscriptions_api.py \
    > "$LOG_DIR/subscriptions_api.log" 2>&1 &
API_PID=$!
echo $API_PID > "$PID_DIR/subscriptions_api.pid"

sleep 3

# Verify API started successfully
if ps -p $API_PID > /dev/null; then
    if check_port 8001; then
        print_success "✓ Subscriptions API started (PID: $API_PID)"
        print_status "  Logs: $LOG_DIR/subscriptions_api.log"
        print_status "  URL: http://localhost:8001"
        print_status "  Health: http://localhost:8001/health"
        print_status "  Docs: http://localhost:8001/docs"
    else
        print_error "API process running but port 8001 not listening"
        print_status "Check logs: tail -f $LOG_DIR/subscriptions_api.log"
    fi
else
    print_error "Failed to start Subscriptions API"
    print_status "Check logs: cat $LOG_DIR/subscriptions_api.log"
    exit 1
fi

# Step 4: Start Stripe Webhook Listener
echo ""
print_status "Step 4: Starting Stripe Webhook Listener..."
echo "-----------------------------------------------------------"

if command -v stripe &> /dev/null; then
    nohup stripe listen --forward-to localhost:8001/api/webhooks/stripe \
        > "$LOG_DIR/stripe_webhook.log" 2>&1 &
    STRIPE_PID=$!
    echo $STRIPE_PID > "$PID_DIR/stripe_webhook.pid"

    sleep 2

    if ps -p $STRIPE_PID > /dev/null; then
        print_success "✓ Stripe Webhook Listener started (PID: $STRIPE_PID)"
        print_status "  Logs: $LOG_DIR/stripe_webhook.log"
        print_warning "  IMPORTANT: Copy webhook signing secret from logs to .env"
    else
        print_error "Failed to start Stripe Webhook Listener"
        print_status "Check logs: cat $LOG_DIR/stripe_webhook.log"
    fi
else
    print_warning "Stripe CLI not installed. Skipping webhook listener."
    print_status "Install with: brew install stripe/stripe-cli/stripe (macOS)"
    print_status "Or visit: https://stripe.com/docs/stripe-cli"
fi

# Step 5: Health checks
echo ""
print_status "Step 5: Running health checks..."
echo "-----------------------------------------------------------"

sleep 2

# Check API health
if curl -s http://localhost:8001/health > /dev/null; then
    HEALTH_STATUS=$(curl -s http://localhost:8001/health | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ] || [ "$HEALTH_STATUS" = "degraded" ]; then
        print_success "✓ API health check passed (Status: $HEALTH_STATUS)"
    else
        print_warning "⚠ API health check: $HEALTH_STATUS"
    fi
else
    print_error "✗ API health check failed"
fi

# Summary
echo ""
echo "============================================================"
echo "  Service Status Summary"
echo "============================================================"
echo ""

print_success "All services started successfully!"
echo ""
print_status "Running Services:"
echo "  • Subscriptions API: http://localhost:8001 (PID: $API_PID)"
if [ ! -z "$STRIPE_PID" ] && ps -p $STRIPE_PID > /dev/null; then
    echo "  • Stripe Webhooks: Listening (PID: $STRIPE_PID)"
fi

echo ""
print_status "Logs Directory: $LOG_DIR"
print_status "  - subscriptions_api.log"
if [ ! -z "$STRIPE_PID" ]; then
    print_status "  - stripe_webhook.log"
fi

echo ""
print_status "To stop all services, run:"
echo "  ./stop_production.sh"
echo ""
print_status "To view logs in real-time:"
echo "  tail -f $LOG_DIR/subscriptions_api.log"
echo ""
echo "============================================================"
echo ""

# Save service status
cat > "$PID_DIR/services.json" <<EOF
{
  "subscriptions_api": {
    "pid": $API_PID,
    "port": 8001,
    "log": "$LOG_DIR/subscriptions_api.log"
  },
  "stripe_webhook": {
    "pid": ${STRIPE_PID:-null},
    "log": "$LOG_DIR/stripe_webhook.log"
  },
  "started_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

print_success "Service information saved to $PID_DIR/services.json"
