#!/usr/bin/env bash
# Build the backend image on Cloud Build and deploy it to Cloud Run.
# Usage (from anywhere):  backend/deploy/deploy.sh
# One-time setup first: see deploy/README.md.
set -euo pipefail

cd "$(dirname "$0")/.."   # backend/ is the build context

# --- Settings: deploy/settings.env; an environment variable overrides a line ---
while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Z_]+$ ]] || continue      # skip comments and blank lines
    value="${value%$'\r'}"                       # tolerate Windows line endings
    [[ -n "${!key:-}" ]] || printf -v "$key" '%s' "$value"
done < deploy/settings.env

PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="$GCP_REGION"
REPOSITORY="$GCP_REPOSITORY"
SERVICE="$GCP_SERVICE"
MEMORY="$GCP_MEMORY"
MAX_INSTANCES="$GCP_MAX_INSTANCES"

if [[ -z "$PROJECT" ]]; then
    echo "No GCP project: set GCP_PROJECT in deploy/settings.env or run 'gcloud config set project <id>'." >&2
    exit 1
fi

IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPOSITORY/$SERVICE:$(date +%Y%m%d-%H%M%S)"

echo "==> Building $IMAGE"
gcloud builds submit . \
    --project "$PROJECT" \
    --region "$REGION" \
    --config deploy/cloudbuild.yaml \
    --ignore-file deploy/.gcloudignore \
    --substitutions "_IMAGE=$IMAGE"

echo "==> Deploying $SERVICE to Cloud Run ($REGION, data: $BACKEND_DATA)"
gcloud run deploy "$SERVICE" \
    --project "$PROJECT" \
    --region "$REGION" \
    --image "$IMAGE" \
    --allow-unauthenticated \
    --set-env-vars "BACKEND_DATA=$BACKEND_DATA" \
    --memory "$MEMORY" \
    --max-instances "$MAX_INSTANCES" \
    --cpu-boost

echo "==> Live at: $(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
