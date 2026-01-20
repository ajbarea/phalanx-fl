#!/bin/bash
# Start the IntelliFL development servers with heartbeat monitoring.
#
# Launches both the FastAPI backend server and Vite frontend development
# server with automatic cleanup on exit. Logs are saved to logs/ directory.
# Terminal displays only periodic health status (heartbeat) for both servers.
#
# Usage: ./run_frontend_monitored.sh
#
# Servers:
#   - API: http://localhost:8000 (FastAPI with uvicorn)
#   - Frontend: http://localhost:5173 (Vite dev server)
#
# Dependencies: npm, uvicorn, curl (for health checks)

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/tests/scripts/common.sh"

navigate_to_root

log_info "🚀 Starting IntelliFL Development Servers..."

if ! ensure_virtual_environment; then
    log_warning "Virtual environment not found. Running reinstall_requirements.sh..."
    ./reinstall_requirements.sh
    setup_virtual_environment
fi

find_python_interpreter

if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    log_info "📦 Installing frontend dependencies..."
    (cd frontend && npm install --silent)
    log_info "Frontend dependencies installed"
else
    log_error "Frontend directory or package.json not found"
    exit 1
fi

log_info "✅ Setup complete!"
echo ""
log_info "Starting servers..."
echo "  - API: http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo ""

# Create timestamped log directory for this session
SESSION_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION_LOG_DIR="logs/session_${SESSION_TIMESTAMP}"
mkdir -p "$SESSION_LOG_DIR"

API_LOG="${SESSION_LOG_DIR}/api_dev.log"
FRONTEND_LOG="${SESSION_LOG_DIR}/frontend_dev.log"
: > "$API_LOG"
: > "$FRONTEND_LOG"

log_info "Logs are being written to:"
echo "  - ${SESSION_LOG_DIR}/"
echo ""
log_info "Press Ctrl+C to stop both servers"
echo ""

# Start API server
uvicorn intellifl.api.main:app --reload --port 8000 >> "$API_LOG" 2>&1 &
API_PID=$!

# Start frontend server - strip ANSI color codes for clean logs
# Use sed to remove escape sequences: ESC[ followed by any sequence ending in a letter
if command_exists sed; then
    (cd frontend && npm run dev 2>&1 | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' >> "../$FRONTEND_LOG") &
else
    # Fallback if sed is not available
    (cd frontend && npm run dev >> "../$FRONTEND_LOG" 2>&1) &
fi
FRONTEND_PID=$!

# Wait for API to be ready
log_info "Waiting for API to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        log_info "API is ready!"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    log_error "API failed to start within 30 seconds"
    log_error "Check $API_LOG for details"
    exit 1
fi

# Wait for frontend to be ready
log_info "Waiting for frontend to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        log_info "Frontend is ready!"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

# Open browser automatically if a supported command is available
if command_exists xdg-open; then
    xdg-open http://localhost:5173 2>/dev/null || true
elif command_exists open; then
    open http://localhost:5173 2>/dev/null || true
elif command_exists start; then
    start http://localhost:5173 2>/dev/null || true
fi

# Clean up both server processes and any orphaned children on exit
cleanup() {
    echo ""
    log_info "🛑 Stopping servers..."

    if command_exists taskkill; then
        # Windows: /T kills child processes, /F forces termination
        taskkill //F //T //PID $API_PID 2>/dev/null || true
        taskkill //F //T //PID $FRONTEND_PID 2>/dev/null || true
    else
        # Unix: kill process group first, fall back to direct PID if not a group leader
        kill -- -$API_PID 2>/dev/null || kill $API_PID 2>/dev/null || true
        kill -- -$FRONTEND_PID 2>/dev/null || kill $FRONTEND_PID 2>/dev/null || true
    fi

    # Catch orphaned processes still bound to our ports
    if command_exists lsof; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    fi

    wait $API_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    log_info "Servers stopped. Logs saved to: ${SESSION_LOG_DIR}/"
    exit 0
}

# Trap INT (Ctrl+C) and TERM signals to ensure cleanup runs on exit
trap cleanup INT TERM

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "📊 Server Health Monitor (updates every 10 seconds)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to check server health
check_health() {
    # Move cursor up to overwrite previous output (in-place update)
    if [ $LINES_TO_CLEAR -gt 0 ]; then
        printf "\033[${LINES_TO_CLEAR}A\033[J"  # Move up and clear to end of screen
    fi

    local api_status="❌ DOWN"
    local frontend_status="❌ DOWN"
    local api_response_time=""
    local frontend_response_time=""

    # Check API health
    if curl -s --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
        api_status="✅ UP"
        # Measure response time
        api_response_time=$(curl -o /dev/null -s -w '%{time_total}' --max-time 2 http://localhost:8000/api/health 2>/dev/null || echo "N/A")
    fi

    # Check frontend health
    if curl -s --max-time 2 http://localhost:5173 > /dev/null 2>&1; then
        frontend_status="✅ UP"
        frontend_response_time=$(curl -o /dev/null -s -w '%{time_total}' --max-time 2 http://localhost:5173 2>/dev/null || echo "N/A")
    fi

    # Get last few lines from logs for error detection
    local api_errors=$(grep -i "error\|exception\|failed" "$API_LOG" 2>/dev/null | tail -1 || echo "")
    local frontend_errors=$(grep -i "error\|exception\|failed" "$FRONTEND_LOG" 2>/dev/null | tail -1 || echo "")

    # Display status box
    echo "┌─────────────────────────────────────────────────────┐"
    printf "│ %-51s │\n" "$(date '+%Y-%m-%d %H:%M:%S')"
    echo "├─────────────────────────────────────────────────────┤"
    printf "│ API Server:      %-32s │\n" "$api_status"
    if [ "$api_response_time" != "N/A" ] && [ -n "$api_response_time" ]; then
        printf "│   Response time: %-30s │\n" "${api_response_time}s"
    fi
    printf "│ Frontend Server: %-32s │\n" "$frontend_status"
    if [ "$frontend_response_time" != "N/A" ] && [ -n "$frontend_response_time" ]; then
        printf "│   Response time: %-30s │\n" "${frontend_response_time}s"
    fi
    echo "├─────────────────────────────────────────────────────┤"
    printf "│ API PID: %-42s │\n" "$API_PID"
    printf "│ Frontend PID: %-38s │\n" "$FRONTEND_PID"
    echo "└─────────────────────────────────────────────────────┘"
    
    # Show recent errors if any
    if [ -n "$api_errors" ]; then
        echo ""
        echo "⚠️  Recent API error: ${api_errors:0:60}..."
    fi
    if [ -n "$frontend_errors" ]; then
        echo ""
        echo "⚠️  Recent frontend error: ${frontend_errors:0:60}..."
    fi
    
    echo ""
    echo "View full logs with: tail -f $API_LOG $FRONTEND_LOG"
    echo "Press Ctrl+C to stop servers"
    echo ""

    # Count lines printed for cursor repositioning
    LINES_TO_CLEAR=15  # Base box is ~15 lines
    [ -n "$api_response_time" ] && LINES_TO_CLEAR=$((LINES_TO_CLEAR + 1)) || true
    [ -n "$frontend_response_time" ] && LINES_TO_CLEAR=$((LINES_TO_CLEAR + 1)) || true
    [ -n "$api_errors" ] && LINES_TO_CLEAR=$((LINES_TO_CLEAR + 2)) || true
    [ -n "$frontend_errors" ] && LINES_TO_CLEAR=$((LINES_TO_CLEAR + 2)) || true
}

# Track lines to overwrite for in-place updates
LINES_TO_CLEAR=0

# Main monitoring loop
while true; do
    check_health
    sleep 10
done
