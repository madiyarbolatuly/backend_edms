# Comprehensive setup script for DocFlow Docker environment
Write-Host "🚀 Setting up DocFlow Docker environment..." -ForegroundColor Cyan

# Check if .env file exists
if (-not (Test-Path "app\.env")) {
    Write-Host "📝 Creating .env file..." -ForegroundColor Yellow
    
    $envContent = @"
# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
DATABASE_HOSTNAME=postgres
POSTGRES_PORT=5432
POSTGRES_DB=docflow

# Application Configuration
TITLE=DocFlow
DESCRIPTION=Electronic Document Management System
DEBUG=True

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MIN=30
REFRESH_TOKEN_EXPIRE_MIN=1440
ALGORITHM=HS256
JWT_SECRET_KEY=your-secret-key-here-change-this-in-production
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key-here-change-this-in-production

# Storage Configuration
LOCAL_STORAGE_PATH=./uploads

# Email Configuration (optional for development)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL=your-email@gmail.com
APP_PASSWORD=your-app-password
"@
    
    $envContent | Out-File -FilePath "app\.env" -Encoding UTF8
    Write-Host "✅ .env file created!" -ForegroundColor Green
}

# Create uploads directory if it doesn't exist
if (-not (Test-Path "uploads")) {
    Write-Host "📁 Creating uploads directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "uploads" -Force | Out-Null
    Write-Host "✅ Uploads directory created!" -ForegroundColor Green
}

# Start the main services
Write-Host "🐳 Starting Docker services..." -ForegroundColor Yellow
docker compose up -d --build

# Wait for services to be ready
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Run database migrations
Write-Host "🗄️ Running database migrations..." -ForegroundColor Yellow
docker compose exec api alembic upgrade head

# Seed initial data
Write-Host "🌱 Seeding initial data..." -ForegroundColor Yellow
docker compose -f docker-compose.yml -f docker-compose.seed.yml --profile seed up seed-data --build

Write-Host "✅ Setup completed successfully!" -ForegroundColor Green
Write-Host "🌐 API is available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 API documentation at: http://localhost:8000/docs" -ForegroundColor Cyan 