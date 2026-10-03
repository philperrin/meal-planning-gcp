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

# 3. Parse .env variables for Cloud Run deployment (excluding local redirect URI)
ENV_VARS=()
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    while IFS='=' read -r key val || [ -n "$key" ]; do
        # Strip comments and whitespace
        key=$(echo "$key" | tr -d '[:space:]')
        if [[ ! "$key" =~ ^# && -n "$key" && "$key" != "GOOGLE_REDIRECT_URI" && "$key" != "PORT" ]]; then
            val=$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            ENV_VARS+=("$key=$val")
        fi
    done < ".env"
fi
ENV_VARS_STRING=$(IFS=','; echo "${ENV_VARS[*]}")

# 4. Build container image with Cloud Build
IMAGE_TAG="gcr.io/$PROJECT_ID/$SERVICE_NAME"
echo "Building container image ($IMAGE_TAG) with Cloud Build..."
gcloud builds submit --tag "$IMAGE_TAG" --project "$PROJECT_ID"

# 5. Deploy container to Cloud Run
echo "Deploying container to Cloud Run..."
if [ -n "$ENV_VARS_STRING" ]; then
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --project "$PROJECT_ID" \
        --region "$REGION" \
        --allow-unauthenticated \
        --platform managed \
        --memory 512Mi \
        --timeout 300 \
        --set-env-vars "$ENV_VARS_STRING"
else
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --project "$PROJECT_ID" \
        --region "$REGION" \
        --allow-unauthenticated \
        --platform managed \
        --memory 512Mi \
        --timeout 300
fi

echo ""
echo "=========================================================="
echo "✅ Deployment complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format 'value(status.url)')
echo "🌐 Service URL: $SERVICE_URL"
echo "=========================================================="
