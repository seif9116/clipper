#!/bin/bash

# Function to handle script termination
cleanup() {
    echo "Shutting down services..."
    kill $(jobs -p)
}

# Trap SIGINT and SIGTERM to run cleanup
trap cleanup SIGINT SIGTERM EXIT

echo "Starting Backend (FastAPI) with uv..."
# Run the backend using uv
uv run uvicorn backend.main:app --reload --port 8000 &

echo "Starting Frontend (React/Vite)..."
cd frontend
npm run dev &

# Wait for processes to keep the script running
wait
