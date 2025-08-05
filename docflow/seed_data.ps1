# PowerShell script to seed tenants and departments data
Write-Host "🌱 Seeding tenants and departments data..." -ForegroundColor Green

# Run the seeding service
docker compose -f docker-compose.yml -f docker-compose.seed.yml --profile seed up seed-data --build

Write-Host "✅ Seeding completed!" -ForegroundColor Green 