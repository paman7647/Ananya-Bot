#!/bin/bash

# Startup script for Ananya Telegram Bot
# This script ensures the virtual environment is activated before running any Python commands

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first."
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Check if Python is available in venv
if ! command -v python &> /dev/null; then
    echo "❌ Python not found in virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated"
echo "🐍 Python: $(which python)"
echo "📦 Python version: $(python --version)"

# Function to start bot
start_bot() {
    echo "🤖 Starting Telegram Bot..."
    python -m src.bot.main
}

# Function to start web server
start_web() {
    echo "🌐 Starting Web Admin Panel..."
    python -m src.web.run
}

# Function to start both
start_all() {
    echo "🚀 Starting both Bot and Web Server..."
    # Start web server in background
    python -m src.web.run &
    WEB_PID=$!

    # Wait a moment for web server to start
    sleep 3

    # Start bot
    python -m src.bot.main &
    BOT_PID=$!

    echo "✅ Services started:"
    echo "   Web Server PID: $WEB_PID"
    echo "   Bot PID: $BOT_PID"
    echo ""
    echo "📝 To stop all services:"
    echo "   kill $WEB_PID $BOT_PID"
    echo ""
    echo "🌐 Web Admin: http://localhost:8080"
    echo "🤖 Bot is running in background"

    # Wait for both processes
    wait
}

# Function to show help
show_help() {
    echo "Ananya Telegram Bot - Startup Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  bot      Start the Telegram bot"
    echo "  web      Start the web admin panel"
    echo "  all      Start both bot and web server"
    echo "  help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 bot          # Start only the bot"
    echo "  $0 web          # Start only the web server"
    echo "  $0 all          # Start both services"
    echo "  $0              # Same as 'all'"
}

# Main logic
case "${1:-all}" in
    "bot")
        start_bot
        ;;
    "web")
        start_web
        ;;
    "all"|"")
        start_all
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac