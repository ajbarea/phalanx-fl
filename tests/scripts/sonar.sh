#!/bin/sh
# SonarQube analysis script

. "$(dirname "$0")/common.sh"
navigate_to_root

setup_unicode_env

log_info "🔍 Starting SonarQube Analysis"

# Docker & SonarQube server
if ! command_exists docker; then
    log_error "Docker not found. SonarQube requires Docker to run locally."
    exit 1
fi

log_info "🐳 Checking SonarQube container status..."
CONTAINER_NEEDS_WAIT=false
if docker ps -a --format "{{.Names}}" | grep -q "^sonarqube$"; then
    if ! docker ps --format "{{.Names}}" | grep -q "^sonarqube$"; then
        log_info "🔄 Starting existing SonarQube container..."
        docker start sonarqube
        CONTAINER_NEEDS_WAIT=true
    else
        log_info "✅ SonarQube container is already running."
    fi
else
    log_info "🚀 Creating new SonarQube container..."
    docker run -d --name sonarqube -p 9000:9000 sonarqube:community
    CONTAINER_NEEDS_WAIT=true
fi

if [ "$CONTAINER_NEEDS_WAIT" = true ]; then
    log_info "⏳ Waiting for SonarQube to start (this may take up to 60 seconds)..."
    _counter=0
    while [ $_counter -lt 30 ]; do
        if curl -s http://localhost:9000/api/system/status | grep -q "UP"; then
            log_info "✅ SonarQube is ready!"
            break
        fi
        sleep 2
        _counter=$((_counter + 1))
    done
    if ! curl -s http://localhost:9000/api/system/status | grep -q "UP"; then
        log_error "SonarQube failed to start. Check Docker logs: docker logs sonarqube"
        exit 1
    fi
fi

# Sonar scanner
if ! command_exists npm; then
    log_error "npm not found. Please install npm first to install sonar-scanner."
    exit 1
fi

# Check if sonar-scanner is available (global, local, or in frontend node_modules)
SONAR_SCANNER_CMD=""
if command_exists sonar-scanner; then
    SONAR_SCANNER_CMD="sonar-scanner"
    log_info "✅ Found sonar-scanner in PATH"
elif [ -f "frontend/node_modules/.bin/sonar-scanner" ]; then
    SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner"
    log_info "✅ Found sonar-scanner in frontend/node_modules"
elif [ -f "frontend/node_modules/.bin/sonar-scanner.cmd" ]; then
    SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner.cmd"
    log_info "✅ Found sonar-scanner in frontend/node_modules"
else
    log_warning "sonar-scanner not found. Installing from frontend dependencies..."
    if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
        cd frontend
        if npm install; then
            cd ..
            if [ -f "frontend/node_modules/.bin/sonar-scanner" ]; then
                SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner"
            elif [ -f "frontend/node_modules/.bin/sonar-scanner.cmd" ]; then
                SONAR_SCANNER_CMD="frontend/node_modules/.bin/sonar-scanner.cmd"
            fi
            log_info "✅ sonar-scanner installed successfully"
        else
            cd ..
            log_error "Failed to install frontend dependencies. Trying global install..."
            if npm install -g sonar-scanner; then
                SONAR_SCANNER_CMD="sonar-scanner"
                log_info "✅ sonar-scanner installed globally"
            else
                log_error "Failed to install sonar-scanner. Please install manually: npm install -g sonar-scanner"
                exit 1
            fi
        fi
    else
        log_warning "Frontend directory not found. Attempting global install..."
        if npm install -g sonar-scanner; then
            SONAR_SCANNER_CMD="sonar-scanner"
            log_info "✅ sonar-scanner installed globally"
        else
            log_error "Failed to install sonar-scanner. Please install manually: npm install -g sonar-scanner"
            exit 1
        fi
    fi
fi


log_info "🚀 Running SonarQube scanner..."

if "$SONAR_SCANNER_CMD" \
    -Dsonar.projectKey=fl-execution-framework \
    -Dsonar.projectName="FL Execution Framework" \
    -Dsonar.projectVersion=1.0 \
    -Dsonar.host.url=http://localhost:9000 \
    -Dsonar.sources=src \
    -Dsonar.tests=tests \
    -Dsonar.python.version=3.10 \
    -Dsonar.python.coverage.reportPaths=tests/logs/coverage.xml \
    -Dsonar.exclusions="**/__pycache__/**,**/.venv/**,**/venv/**,tests/logs/**" \
    -Dsonar.working.directory=tests/logs/.sonarwork; then
    log_info "✅ SonarQube analysis completed successfully."
    log_info "   View the report at: http://localhost:9000/dashboard?id=fl-execution-framework"
else
    log_error "SonarQube analysis failed. Check the output above for details."
    exit 1
fi
