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

# 1. Auto-increment application build version in config.py
$ConfigFile = Join-Path $PSScriptRoot "config.py"
if (-not (Test-Path $ConfigFile)) {
    $ConfigFile = "config.py"
}

$NewVersion = $null
if (Test-Path $ConfigFile) {
    $ConfigContent = Get-Content $ConfigFile -Raw
    $VersionRegex = '(?m)^(\s*APP_VERSION\s*=\s*(?:os\.getenv\("APP_VERSION",\s*)?["''])(\d{4}\.\d+\.\d+)(["''].*)$'
    if ($ConfigContent -match $VersionRegex) {
        $OldVersion = $Matches[2]
        $parts = $OldVersion.Split('.')
        $Year = $parts[0]
        $Minor = $parts[1]
        $Build = [int]$parts[2]
        $NextBuild = $Build + 1
        $NextBuildStr = "{0:D3}" -f $NextBuild
        $NewVersion = "$Year.$Minor.$NextBuildStr"

        Write-Host "🔖 Incremented appVersion: $OldVersion -> $NewVersion" -ForegroundColor Cyan
        $ConfigContent = [regex]::Replace($ConfigContent, $VersionRegex, "`${1}$NewVersion`${3}")
        [System.IO.File]::WriteAllText((Resolve-Path $ConfigFile).Path, $ConfigContent, [System.Text.Encoding]::UTF8)
    } else {
        Write-Warning "Could not find APP_VERSION in $ConfigFile to increment."
    }
}

# 2. Configure gcloud project
Write-Host "Configuring gcloud project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# 3. Enable Required APIs
Write-Host "Ensuring required Cloud APIs are enabled..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    artifactregistry.googleapis.com `
    cloudbuild.googleapis.com `
    calendar-json.googleapis.com `
    docs.googleapis.com `
    drive.googleapis.com

# 4. Parse .env variables for Cloud Run deployment (excluding local redirect URI)
$EnvVars = @()
if (Test-Path ".env") {
    Write-Host "Loading environment variables from .env..." -ForegroundColor Yellow
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim()
            if ($k -ne "GOOGLE_REDIRECT_URI" -and $k -ne "PORT" -and $k -ne "APP_VERSION") {
                $EnvVars += "$k=$v"
            }
        }
    }
}
if ($NewVersion) {
    $EnvVars += "APP_VERSION=$NewVersion"
}
$EnvVarsString = ($EnvVars -join ",")

# 5. Build container image with Cloud Build
$ImageTag = "gcr.io/$ProjectId/$ServiceName"
Write-Host "Building container image ($ImageTag) with Cloud Build..." -ForegroundColor Yellow
gcloud builds submit --tag $ImageTag --project $ProjectId

# 6. Deploy container to Cloud Run
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
Write-Host "✅ Deployment complete! Deployed version: $NewVersion" -ForegroundColor Green
$ServiceUrl = gcloud run services describe $ServiceName --platform managed --region $Region --format 'value(status.url)'
Write-Host "🌐 Service URL: $ServiceUrl" -ForegroundColor Green
Write-Host "=========================================================="
