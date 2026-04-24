#!/bin/bash
# Eko AI Business Automation — Setup Script
# Run this after cloning the repo to get started quickly.

set -e

echo "=========================================="
echo "Eko AI Business Automation — Setup"
echo "=========================================="

# Check prerequisites
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed. Aborting."; exit 1; }

cd "$(dirname "$0")/.."

# Copy env file if not exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env and add your API keys before starting services."
fi

# Create data directories
mkdir -p pgdata redisdata

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
if command -v npm >/dev/null 2>&1; then
    npm install
elif command -v yarn >/dev/null 2>&1; then
    yarn install
else
    echo "npm/yarn not found. Please install Node.js dependencies manually."
fi
cd ..

# Build and start services
echo "Building and starting services..."
docker-compose build
docker-compose up -d

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  Dashboard:  http://localhost:3000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  API Health: http://localhost:8000/health"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys (OpenAI, Resend, Outscraper)"
echo "  2. Restart services: docker-compose restart"
echo "  3. Visit http://localhost:3000 and run your first Discovery"
echo ""
