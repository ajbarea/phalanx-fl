#!/bin/bash
# Run SonarQube static analysis on the FL execution framework.

set -e

# Helper functions
log_info() { echo "✅ $1"; }
log_error() { echo "❌ $1" >&2; }
log_warning() { echo "⚠️  $1"; }
command_exists() { command -v "$1" >/dev/null 2>&1; }

# Navigate to root
cd "$(dirname "$0")/../.."

log_info "🔍 Starting SonarQube Analysis"

# Check Docker
if ! command_exists docker; then
    log_error "Docker not found. SonarQube requires Docker to run locally."
    exit 1
fi

log_info "🐳 Checking SonarQube container status..."
if docker ps -a --format "{{.Names}}" | grep -q "^sonarqube$"; then
    if ! docker ps --format "{{.Names}}" | grep -q "^sonarqube$"; then
        log_info "🔄 Starting existing SonarQube container..."
        docker start sonarqube
    else
        log_info "✅ SonarQube container is already running."
    fi
else
    log_info "🚀 Creating new SonarQube container..."
    docker run -d --name sonarqube -p 9000:9000 sonarqube:community
fi

# Wait for SonarQube
log_info "⏳ Waiting for SonarQube to start..."
for i in {1..30}; do
    if curl -s http://localhost:9000/api/system/status | grep -q "UP"; then
        log_info "✅ SonarQube is ready!"
        break
    fi
    sleep 2
done

# Sonar Scanner discovery
SONAR_SCANNER_CMD=""
if command_exists sonar-scanner; then
    SONAR_SCANNER_CMD="sonar-scanner"
elif [ -f "frontend/node_modules/.bin/sonar-scanner" ]; then
    SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner"
elif [ -f "frontend/node_modules/.bin/sonar-scanner.cmd" ]; then
    SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner.cmd"
fi

if [ -z "$SONAR_SCANNER_CMD" ]; then
    log_error "sonar-scanner not found. Please install via 'npm install' in the frontend directory."
    exit 1
fi

log_info "🚀 Running SonarQube scanner..."
"$SONAR_SCANNER_CMD" \
    -Dsonar.projectKey=fl-execution-framework \
    -Dsonar.projectName="FL Execution Framework" \
    -Dsonar.projectVersion=1.0 \
    -Dsonar.host.url=http://localhost:9000 \
    -Dsonar.sources=intellifl \
    -Dsonar.tests=tests \
    -Dsonar.python.version=3.12 \
    -Dsonar.python.coverage.reportPaths=tests/logs/coverage.xml \
    -Dsonar.exclusions="**/__pycache__/**,**/.venv/**,**/venv/**,tests/logs/**" \
    -Dsonar.working.directory=tests/logs/.sonarwork
