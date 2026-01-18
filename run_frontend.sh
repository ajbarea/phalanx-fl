#!/bin/bash
# Start the IntelliFL development servers (API and frontend).
#
# Launches both the FastAPI backend server and Vite frontend development
# server, with automatic cleanup on exit. Logs are saved to tests/logs/
# for debugging.
#
# Usage: ./run_frontend.sh
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
    (cd frontend && npm install)
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
log_info "Press Ctrl+C to stop both servers"
echo ""

mkdir -p tests/logs
API_LOG="tests/logs/api_dev_$(date +%Y%m%d_%H%M%S).log"
FRONTEND_LOG="tests/logs/frontend_dev_$(date +%Y%m%d_%H%M%S).log"
: > "$API_LOG"
: > "$FRONTEND_LOG"

uvicorn intellifl.api.main:app --reload --port 8000 > "$API_LOG" 2>&1 &
API_PID=$!

(cd frontend && npm run dev > "../$FRONTEND_LOG" 2>&1) &
FRONTEND_PID=$!

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
fi

# Open browser automatically if a supported command is available.
if command_exists xdg-open; then
    xdg-open http://localhost:5173 2>/dev/null || true
elif command_exists open; then
    open http://localhost:5173 2>/dev/null || true
elif command_exists start; then
    start http://localhost:5173 2>/dev/null || true
fi

# Clean up both server processes and any orphaned children on exit.
#
# Process cleanup is platform-specific: Windows requires taskkill with /T
# to terminate child processes, while Unix can kill process groups directly.
# The lsof fallback catches orphaned processes that may have detached from
# their parent (common with uvicorn --reload which spawns worker processes).
cleanup() {
    echo ""
    log_info "🛑 Stopping servers..."

    if command_exists taskkill; then
        # Windows: /T kills child processes, /F forces termination.
        taskkill //F //T //PID $API_PID 2>/dev/null || true
        taskkill //F //T //PID $FRONTEND_PID 2>/dev/null || true
    else
        # Unix: kill process group first, fall back to direct PID if not a group leader.
        kill -- -$API_PID 2>/dev/null || kill $API_PID 2>/dev/null || true
        kill -- -$FRONTEND_PID 2>/dev/null || kill $FRONTEND_PID 2>/dev/null || true
    fi

    # Catch orphaned processes still bound to our ports (uvicorn workers, node).
    if command_exists lsof; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    fi

    wait $API_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    log_info "Servers stopped. Logs saved to tests/logs/"
    exit 0
}

# Trap INT (Ctrl+C) and TERM signals to ensure cleanup runs on exit.
trap cleanup INT TERM

echo ""
log_info "📋 Tailing logs (Ctrl+C to stop)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

tail -f "$API_LOG" "$FRONTEND_LOG" 2>/dev/null | while IFS= read -r line; do
    case "$line" in
        *"==> $API_LOG <=="*)
            echo ""
            echo "🔵 [API]"
            ;;
        *"==> $FRONTEND_LOG <=="*)
            echo ""
            echo "🟢 [FRONTEND]"
            ;;
        "")
            ;;
        *)
            echo "$line"
            ;;
    esac
done
