#!/bin/bash
# EC2 Initial Setup Script
# Run this on your EC2 instance after cloning the repository

set -e

echo "🚀 Into the Repo - EC2 Initial Setup"
echo "======================================"
echo ""

# Check if running on EC2
if [ ! -f /sys/hypervisor/uuid ] && [ ! -d /sys/devices/virtual/dmi/id/ ]; then
    echo "⚠️  Warning: This doesn't appear to be an EC2 instance"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Prompt for values
echo "Please provide the following values:"
echo ""

read -p "Enter your EC2 Public IP Address: " EC2_IP
read -p "Enter your GitHub Personal Access Token: " GITHUB_TOKEN
read -p "Enter your Gemini API Key: " GEMINI_API_KEY

# Generate secure passwords
echo ""
echo "Generating secure passwords..."
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

echo "✓ Generated SECRET_KEY"
echo "✓ Generated DB_PASSWORD"
echo ""

# Create .env file
cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://repo_user:${DB_PASSWORD}@db:5432/into_the_repo
DB_USER=repo_user
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=into_the_repo
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_PORT=6379

# Authentication & Security
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# External APIs
GITHUB_TOKEN=${GITHUB_TOKEN}
GEMINI_API_KEY=${GEMINI_API_KEY}

# Application Configuration
BACKEND_PORT=8000
FRONTEND_PORT=3000
LOG_LEVEL=info
NODE_ENV=production

# Frontend API URL
NEXT_PUBLIC_API_URL=http://${EC2_IP}:8000
EOF

echo "✅ Created .env file"
echo ""

# Display configuration
echo "📋 Configuration Summary:"
echo "-------------------------"
echo "EC2 IP: ${EC2_IP}"
echo "Frontend URL: http://${EC2_IP}:3000"
echo "Backend API URL: http://${EC2_IP}:8000"
echo "Database Password: ${DB_PASSWORD}"
echo "Secret Key: ${SECRET_KEY:0:20}..."
echo ""

# Save credentials to a secure file
cat > ~/deployment-credentials.txt << EOF
Into the Repo - Deployment Credentials
======================================
Generated on: $(date)

EC2 Public IP: ${EC2_IP}
Database Password: ${DB_PASSWORD}
Secret Key: ${SECRET_KEY}

Frontend: http://${EC2_IP}:3000
Backend API: http://${EC2_IP}:8000/docs

IMPORTANT: Keep this file secure and delete after saving credentials elsewhere!
EOF

chmod 600 ~/deployment-credentials.txt
echo "💾 Credentials saved to: ~/deployment-credentials.txt"
echo "⚠️  IMPORTANT: Save these credentials securely, then delete the file!"
echo ""

# Ask to deploy
read -p "Start initial deployment now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔨 Starting Docker build and deployment..."
    echo "This may take 10-15 minutes..."
    echo ""
    
    # Build images
    docker compose build --no-cache
    
    # Start services
    docker compose up -d
    
    echo ""
    echo "⏳ Waiting for services to start..."
    sleep 30
    
    # Show status
    echo ""
    echo "📊 Service Status:"
    docker compose ps
    
    echo ""
    echo "📋 Recent Logs:"
    docker compose logs --tail=30
    
    echo ""
    echo "✅ Deployment complete!"
    echo ""
    echo "🌐 Access your application:"
    echo "   Frontend: http://${EC2_IP}:3000"
    echo "   Backend API: http://${EC2_IP}:8000/docs"
    echo ""
    echo "📝 View logs: docker compose logs -f"
    echo "🔄 Restart: docker compose restart"
    echo "🛑 Stop: docker compose down"
else
    echo ""
    echo "Deployment skipped. To deploy manually later, run:"
    echo "  docker compose build"
    echo "  docker compose up -d"
fi

echo ""
echo "🎉 Setup complete!"
