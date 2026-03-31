#!/bin/bash

echo "🛡️ Initializing OpticFlow Deployment to GCP..."
echo "Building using Dockerfile and deploying container to Cloud Run service [opticflow-agent] in region [us-central1]..."

gcloud run deploy opticflow-agent \
  --source . \
  --project project-xxxx-xxxx-xxxx \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi

echo "✅ Deployment pipeline complete!"
