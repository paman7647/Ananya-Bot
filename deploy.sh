#!/bin/bash

# Ananya Bot - Quick Deployment Script
# This script performs all necessary checks and deploys the bot

set -e  # Exit on error

echo "=============================================="
echo "   Ananya Bot Deployment Script"
echo "=============================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo -e "${YELLOW}Creating from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from template${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env with your credentials before continuing${NC}"
    exit 1
fi

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker found${NC}"
    DOCKER_AVAILABLE=true
else
    echo -e "${YELLOW}⚠️  Docker not found, will use direct Python${NC}"
    DOCKER_AVAILABLE=false
fi

# Function to deploy with Docker
deploy_docker() {
    echo ""
    echo "=============================================="
    echo "   Docker Deployment"
    echo "=============================================="
    
    # Check if docker-compose is available
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        echo -e "${RED}❌ docker-compose not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Using: $COMPOSE_CMD${NC}"
    
    # Build and start
    echo ""
    echo "Building Docker images..."
    $COMPOSE_CMD build
    
    echo ""
    echo "Starting services..."
    $COMPOSE_CMD up -d
    
    echo ""
    echo -e "${GREEN}✓ Deployment complete!${NC}"
    echo ""
    echo "Services:"
    $COMPOSE_CMD ps
    
    echo ""
    echo "View logs: $COMPOSE_CMD logs -f"
    echo "Stop services: $COMPOSE_CMD down"
    echo "Web Admin Panel: http://localhost:8080"
}

# Function to deploy with Python
deploy_python() {
    echo ""
    echo "=============================================="
    echo "   Python Direct Deployment"
    echo "=============================================="
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
    
    # Check if virtual environment exists
    if [ ! -d ".venv" ]; then
        echo ""
        echo "Creating virtual environment..."
        python3 -m venv .venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
    
    # Activate virtual environment
    echo ""
    echo "Activating virtual environment..."
    source .venv/bin/activate
    
    # Install dependencies
    echo ""
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    
    # Check MongoDB connection
    echo ""
    echo "Checking MongoDB connection..."
    python3 -c "from src.utils.database import db; print('✓ MongoDB connected')" 2>/dev/null || {
        echo -e "${RED}❌ MongoDB connection failed${NC}"
        echo -e "${YELLOW}Make sure MongoDB is running and MONGODB_URI is correct in .env${NC}"
        exit 1
    }
    
    echo ""
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "=============================================="
    echo "   Starting Services"
    echo "=============================================="
    echo ""
    
    # Ask user what to start
    echo "What would you like to start?"
    echo "1) Bot only"
    echo "2) Web Admin Panel only"
    echo "3) Both (recommended)"
    read -p "Enter choice [1-3]: " choice
    
    case $choice in
        1)
            echo ""
            echo "Starting Bot..."
            python -m src.bot.main
            ;;
        2)
            echo ""
            echo "Starting Web Admin Panel..."
            python -m src.web.run
            ;;
        3)
            echo ""
            echo "Starting both services..."
            echo ""
            # Start web in background
            python -m src.web.run > logs/web.log 2>&1 &
            WEB_PID=$!
            echo -e "${GREEN}✓ Web Admin Panel started (PID: $WEB_PID)${NC}"
            echo -e "${GREEN}✓ Web Admin Panel: http://localhost:8080${NC}"
            
            # Wait a bit for web to start
            sleep 2
            
            # Start bot in foreground
            echo ""
            echo -e "${GREEN}Starting Telegram Bot...${NC}"
            python -m src.bot.main
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

# Main deployment logic
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo ""
    read -p "Use Docker for deployment? [Y/n]: " use_docker
    case $use_docker in
        [Nn]*)
            deploy_python
            ;;
        *)
            deploy_docker
            ;;
    esac
else
    deploy_python
fi

echo ""
echo -e "${GREEN}=============================================="
echo "   Deployment Complete!"
echo "==============================================${NC}"
