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

# 3. Parse .env variables for Cloud Run deployment (excluding local redirect URI)
$EnvVars = @()
if (Test-Path ".env") {
    Write-Host "Loading environment variables from .env..." -ForegroundColor Yellow
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim()
            if ($k -ne "GOOGLE_REDIRECT_URI" -and $k -ne "PORT") {
                $EnvVars += "$k=$v"
            }
        }
    }
}
$EnvVarsString = ($EnvVars -join ",")

# 4. Build container image with Cloud Build
$ImageTag = "gcr.io/$ProjectId/$ServiceName"
Write-Host "Building container image ($ImageTag) with Cloud Build..." -ForegroundColor Yellow
gcloud builds submit --tag $ImageTag --project $ProjectId

# 5. Deploy container to Cloud Run
Write-Host "Deploying container to Cloud Run..." -ForegroundColor Yellow
if ($EnvVarsString) {
    gcloud run deploy $ServiceName `
        --image $ImageTag `
        --project $ProjectId `
        --region $Region `
        --allow-unauthenticated `
        --platform managed `
        --memory 512Mi `
        --timeout 300 `
        --set-env-vars $EnvVarsString
} else {
    gcloud run deploy $ServiceName `
        --image $ImageTag `
        --project $ProjectId `
        --region $Region `
        --allow-unauthenticated `
        --platform managed `
        --memory 512Mi `
        --timeout 300
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "✅ Deployment complete!" -ForegroundColor Green
$ServiceUrl = gcloud run services describe $ServiceName --platform managed --region $Region --format 'value(status.url)'
Write-Host "🌐 Service URL: $ServiceUrl" -ForegroundColor Green
Write-Host "=========================================================="
