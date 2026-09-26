#!/usr/bin/env bash
# ==============================================================================
# Cloud Run Automated Deployment Script
# Target Project: meal-planning-app-507921
# ==============================================================================

set -e

PROJECT_ID="meal-planning-app-507921"
SERVICE_NAME="meal-planning-app"
REGION="us-central1"

echo "=========================================================="
echo "🚀 Deploying Meal Planning Assistant to Google Cloud Run"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region:  $REGION"
echo "=========================================================="

# 1. Ensure project configuration
echo "Configuring gcloud project..."
gcloud config set project "$PROJECT_ID"

# 2. Enable Required APIs (Idempotent)
echo "Ensuring required Cloud APIs are enabled..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    calendar-json.googleapis.com \
    docs.googleapis.com \
    drive.googleapis.com

# 3. Deploy from source to Cloud Run
echo "Building container and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --allow-unauthenticated \
    --platform managed \
    --memory 512Mi \
    --timeout 300

echo ""
echo "=========================================================="
echo "✅ Deployment complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format 'value(status.url)')
echo "🌐 Service URL: $SERVICE_URL"
echo "=========================================================="
