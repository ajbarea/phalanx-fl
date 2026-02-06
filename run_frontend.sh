#!/bin/bash
# Start the IntelliFL development servers (Redis, Celery, API, Frontend).
#
# Launches all required services for local development with automatic
# cleanup on exit. Logs are saved to tests/logs/ for debugging.
#
# Usage: ./run_frontend.sh
#
# Servers:
#   - Redis: localhost:6379 (task queue broker)
#   - Celery: worker for simulation execution
#   - API: http://localhost:8000 (FastAPI with uvicorn)
#   - Frontend: http://localhost:5173 (Vite dev server)
#
# For running simulations without the web UI, use ./run_simulation.sh instead
# (no Redis/Celery required for direct CLI execution).
#
# Dependencies: npm, uvicorn, curl, redis-server (optional) or Docker (for Redis), celery

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
echo "  - Redis: localhost:6379"
echo "  - Celery: worker (concurrency=1)"
echo "  - API: http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo ""
log_info "Press Ctrl+C to stop all servers"
echo ""

mkdir -p tests/logs
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REDIS_LOG="tests/logs/redis_dev_${TIMESTAMP}.log"
CELERY_LOG="tests/logs/celery_dev_${TIMESTAMP}.log"
API_LOG="tests/logs/api_dev_${TIMESTAMP}.log"
FRONTEND_LOG="tests/logs/frontend_dev_${TIMESTAMP}.log"
: > "$REDIS_LOG"
: > "$CELERY_LOG"
: > "$API_LOG"
: > "$FRONTEND_LOG"

# Start Redis (required for Celery task queue)
REDIS_PID=""
REDIS_LOG_PID=""
REDIS_STARTED_WITH_COMPOSE=""
REDIS_START_FAILED=""
COMPOSE_CMD=""

get_compose_cmd() {
    if command_exists docker; then
        if docker compose version >/dev/null 2>&1; then
            echo "docker compose"
            return 0
        fi
    fi
    if command_exists docker-compose; then
        echo "docker-compose"
        return 0
    fi
    return 1
}

start_redis_with_compose() {
    COMPOSE_CMD="$(get_compose_cmd || true)"
    if [ -z "$COMPOSE_CMD" ]; then
        return 1
    fi

    if command_exists docker; then
        if ! docker info >/dev/null 2>&1; then
            log_error "Docker is installed but not running. Start Docker Desktop and retry."
            REDIS_START_FAILED="true"
            return 1
        fi
    fi

    log_info "Starting Redis via Docker Compose..."
    if ! $COMPOSE_CMD up -d redis > "$REDIS_LOG" 2>&1; then
        log_error "Failed to start Redis via Docker Compose."
        REDIS_START_FAILED="true"
        return 1
    fi

    REDIS_STARTED_WITH_COMPOSE="true"

    # Follow container logs into the Redis log file for unified tailing.
    if command_exists docker; then
        docker logs -f intellifl-redis >> "$REDIS_LOG" 2>&1 &
        REDIS_LOG_PID=$!
    fi

    return 0
}

redis_ready() {
    if command_exists redis-cli; then
        redis-cli ping 2>/dev/null | grep -q PONG && return 0
    fi

    if [ -n "${REDIS_STARTED_WITH_COMPOSE:-}" ] && [ -n "${COMPOSE_CMD:-}" ]; then
        $COMPOSE_CMD exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && return 0
    fi

    return 1
}

if command_exists redis-server; then
    log_info "Starting Redis server..."
    redis-server --daemonize no --port 6379 > "$REDIS_LOG" 2>&1 &
    REDIS_PID=$!
elif start_redis_with_compose; then
    :
else
    if [ -n "${REDIS_START_FAILED:-}" ]; then
        exit 1
    fi
    log_error "Redis not found. Install redis-server or Docker Desktop."
    exit 1
fi

# Wait for Redis to be ready
log_info "Waiting for Redis (up to 120s)..."
max_redis_attempts=60
redis_attempt=0
while [ $redis_attempt -lt $max_redis_attempts ]; do
    if redis_ready; then
        log_info "Redis is ready!"
        break
    fi
    if [ -n "${REDIS_PID:-}" ] && ! command_exists redis-cli; then
        sleep 2
        log_info "Redis assumed ready (no redis-cli to verify)"
        break
    fi
    redis_attempt=$((redis_attempt + 1))
    sleep 2
done

if [ $redis_attempt -eq $max_redis_attempts ]; then
    log_error "Redis failed to start within 120 seconds"
    if [ -n "${COMPOSE_CMD:-}" ]; then
        log_warning "Docker Compose status:"
        $COMPOSE_CMD ps redis 2>/dev/null || true
        log_warning "Redis logs (last 50 lines):"
        $COMPOSE_CMD logs --tail 50 redis 2>/dev/null || true
    elif command_exists docker; then
        log_warning "Redis logs (last 50 lines):"
        docker logs --tail 50 intellifl-redis 2>/dev/null || true
    fi
    exit 1
fi

# Start Celery worker
log_info "Starting Celery worker..."
celery -A intellifl.celery_app worker --loglevel=info --concurrency=1 > "$CELERY_LOG" 2>&1 &
CELERY_PID=$!

# Wait briefly for Celery to connect to Redis
sleep 2

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

# Clean up all server processes and any orphaned children on exit.
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
        taskkill //F //T //PID $FRONTEND_PID 2>/dev/null || true
        taskkill //F //T //PID $API_PID 2>/dev/null || true
        taskkill //F //T //PID $CELERY_PID 2>/dev/null || true
        [ -n "${REDIS_LOG_PID:-}" ] && taskkill //F //T //PID $REDIS_LOG_PID 2>/dev/null || true
        [ -n "${REDIS_PID:-}" ] && taskkill //F //T //PID $REDIS_PID 2>/dev/null || true
    else
        # Unix: kill process group first, fall back to direct PID if not a group leader.
        kill -- -$FRONTEND_PID 2>/dev/null || kill $FRONTEND_PID 2>/dev/null || true
        kill -- -$API_PID 2>/dev/null || kill $API_PID 2>/dev/null || true
        kill -- -$CELERY_PID 2>/dev/null || kill $CELERY_PID 2>/dev/null || true
        [ -n "${REDIS_LOG_PID:-}" ] && (kill -- -$REDIS_LOG_PID 2>/dev/null || kill $REDIS_LOG_PID 2>/dev/null || true)
        [ -n "${REDIS_PID:-}" ] && (kill -- -$REDIS_PID 2>/dev/null || kill $REDIS_PID 2>/dev/null || true)
    fi

    # Stop Docker Redis container if we started one
    if [ -n "${REDIS_STARTED_WITH_COMPOSE:-}" ] && [ -n "${COMPOSE_CMD:-}" ]; then
        $COMPOSE_CMD stop redis 2>/dev/null || true
    else
        docker stop intellifl-redis 2>/dev/null || true
    fi

    # Catch orphaned processes still bound to our ports (uvicorn workers, node, celery).
    if command_exists lsof; then
        lsof -ti:6379 | xargs kill -9 2>/dev/null || true
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    fi

    wait $FRONTEND_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
    wait $CELERY_PID 2>/dev/null || true
    [ -n "$REDIS_PID" ] && wait $REDIS_PID 2>/dev/null || true
    log_info "Servers stopped. Logs saved to tests/logs/"
    exit 0
}

# Trap INT (Ctrl+C) and TERM signals to ensure cleanup runs on exit.
trap cleanup INT TERM

echo ""
log_info "📋 Tailing logs (Ctrl+C to stop)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

tail -f "$REDIS_LOG" "$CELERY_LOG" "$API_LOG" "$FRONTEND_LOG" 2>/dev/null | while IFS= read -r line; do
    case "$line" in
        *"==> $REDIS_LOG <=="*)
            echo ""
            echo "🔴 [REDIS]"
            ;;
        *"==> $CELERY_LOG <=="*)
            echo ""
            echo "🟠 [CELERY]"
            ;;
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
