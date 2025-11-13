#!/bin/bash

echo "🚀 Starting Trading Journal Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run './install.sh' first."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create it from .env.example"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Start the server
echo "✅ Starting FastAPI server with auto-reload..."
echo "📍 Server will run on http://${HOST:-0.0.0.0}:${PORT:-8000}"
echo "📖 API docs available at http://localhost:${PORT:-8000}/docs"
echo ""

uvicorn main:app --reload --host ${HOST:-0.0.0.0} --port ${PORT:-8000}