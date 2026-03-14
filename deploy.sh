#!/bin/bash

echo "🛡️ Initializing OpticFlow Deployment to GCP..."
echo "Building using Dockerfile and deploying container to Cloud Run service [opticflow-agent] in region [us-central1]..."

gcloud run deploy opticflow-agent \
  --source . \
  --project project-22a1faa3-ae47-4585-b52 \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi

echo "✅ Deployment pipeline complete!"