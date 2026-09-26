# ==============================================================================
# Cloud Run Automated Deployment Script (PowerShell)
# Target Project: meal-planning-app-507921
# ==============================================================================

$ErrorActionPreference = "Stop"

$ProjectId = "meal-planning-app-507921"
$ServiceName = "meal-planning-app"
$Region = "us-central1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 Deploying Meal Planning Assistant to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project: $ProjectId"
Write-Host "Service: $ServiceName"
Write-Host "Region:  $Region"
Write-Host "=========================================================="

# 1. Configure gcloud project
Write-Host "Configuring gcloud project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# 2. Enable Required APIs
Write-Host "Ensuring required Cloud APIs are enabled..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    artifactregistry.googleapis.com `
    cloudbuild.googleapis.com `
    calendar-json.googleapis.com `
    docs.googleapis.com `
    drive.googleapis.com

# 3. Deploy to Cloud Run
Write-Host "Building container and deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --allow-unauthenticated `
    --platform managed `
    --memory 512Mi `
    --timeout 300

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "✅ Deployment complete!" -ForegroundColor Green
$ServiceUrl = gcloud run services describe $ServiceName --platform managed --region $Region --format 'value(status.url)'
Write-Host "🌐 Service URL: $ServiceUrl" -ForegroundColor Green
Write-Host "=========================================================="
