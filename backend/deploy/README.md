# Deploying the backend (Google Cloud Run)

The backend runs on [Cloud Run](https://cloud.google.com/run) as a container:
Cloud Build builds the image from `deploy/Dockerfile`, Artifact Registry stores
it, Cloud Run serves it on a public HTTPS URL and scales to zero when idle.
The build runs in the cloud, so you don't need Docker installed to deploy.

```
backend/ ──gcloud builds submit──▶ Cloud Build ──image──▶ Artifact Registry ──▶ Cloud Run (gunicorn → deploy/wsgi.py → main.create_app)
```

| File | What it does |
|---|---|
| `Dockerfile` | The image: Python 3.12, the requirements, the code and `test/mock_data/`, run by gunicorn |
| `wsgi.py` | Production entry point; picks mock or database from `BACKEND_DATA` |
| `requirements.txt` | The backend's requirements plus gunicorn (production only) |
| `cloudbuild.yaml` | Tells Cloud Build to build with `deploy/Dockerfile` |
| `.gcloudignore` | What gets left out of the upload (`.venv`, caches, `.env`) |
| `settings.env` | Deployment settings: project, region, service, data source, memory (no secrets) |
| `deploy.sh` | Build + deploy in one command (macOS, Linux, WSL, Git Bash) |

## One-time setup

### 1. Install the gcloud CLI

| OS | How |
|---|---|
| macOS | `brew install --cask google-cloud-sdk` |
| Windows | Download and run the installer from https://cloud.google.com/sdk/docs/install#windows, then open a new terminal |
| Linux | Follow https://cloud.google.com/sdk/docs/install#linux (apt/dnf packages or the tar archive) |

Then log in (opens a browser), on any OS:

```bash
gcloud auth login
```

### 2. Pick the project

The commands from here on are the same in every terminal (bash, zsh, PowerShell, cmd).

Only one person creates the project. Project ids are global, so add a suffix:

```bash
gcloud projects create firecal-<suffix>
```

Then link billing in the console (*Billing → Link a billing account*); the free
trial credit counts. Colleagues who deploy must be added in *IAM → Grant access*
(role *Editor* is enough for a hackathon).

Everyone, on their own machine:

```bash
gcloud config set project firecal-<suffix>
```

### 3. Enable the APIs and create the image repository (once per project)

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create firecal --repository-format docker --location europe-west1
```

## Deploy

### macOS, Linux, WSL, Git Bash

From the repository root:

```bash
backend/deploy/deploy.sh
```

It builds the image (~2 min the first time), deploys it and prints the URL.

### Settings

The project, region, service name, data source, memory and instance cap live in
[`settings.env`](settings.env), committed and shared by the team (settings
only, never secrets). Set `GCP_PROJECT` there once and nobody needs
`gcloud config set project`. To change a setting for one run only, set an
environment variable with the same name, e.g.
`BACKEND_DATA=database backend/deploy/deploy.sh`.

### Windows PowerShell

The same two steps as `deploy.sh`, from the `backend` folder, reading the same
`settings.env`:

```powershell
cd backend
$s = @{}
Get-Content deploy/settings.env | Where-Object { $_ -match '^([A-Z_]+)=(.*)$' } | ForEach-Object { $s[$Matches[1]] = $Matches[2] }
if (-not $s.GCP_PROJECT) { $s.GCP_PROJECT = gcloud config get-value project }
$IMAGE = "$($s.GCP_REGION)-docker.pkg.dev/$($s.GCP_PROJECT)/$($s.GCP_REPOSITORY)/$($s.GCP_SERVICE):$(Get-Date -Format yyyyMMdd-HHmmss)"

gcloud builds submit . --project $s.GCP_PROJECT --region $s.GCP_REGION --config deploy/cloudbuild.yaml `
  --ignore-file deploy/.gcloudignore --substitutions "_IMAGE=$IMAGE"

gcloud run deploy $s.GCP_SERVICE --project $s.GCP_PROJECT --region $s.GCP_REGION --image $IMAGE `
  --allow-unauthenticated --set-env-vars "BACKEND_DATA=$($s.BACKEND_DATA)" `
  --memory $s.GCP_MEMORY --max-instances $s.GCP_MAX_INSTANCES --cpu-boost
```

## Check it

Get the URL:

```bash
gcloud run services describe firecal-backend --region europe-west1 --format "value(status.url)"
```

Send a request (replace `<URL>`).

macOS / Linux / WSL / Git Bash:

```bash
curl -X POST "<URL>/api/calendar" -H 'Content-Type: application/json' \
  -d '{"feature":"calendar","lat":-10,"lon":-55,"radius":200,"date_time_from":"2020-01-01T00:00:00Z","date_time_to":"2022-12-31T23:59:59Z"}'
```

Windows PowerShell:

```powershell
$body = '{"feature":"calendar","lat":-10,"lon":-55,"radius":200,"date_time_from":"2020-01-01T00:00:00Z","date_time_to":"2022-12-31T23:59:59Z"}'
Invoke-RestMethod -Method Post -Uri "<URL>/api/calendar" -ContentType "application/json" -Body $body
```

Logs, on any OS: `gcloud run services logs read firecal-backend --region europe-west1`.

## Run the production setup locally (optional)

With Docker running, from `backend/`, on any OS:

```bash
docker build -f deploy/Dockerfile -t firecal-backend .
docker run --rm -p 8080:8080 firecal-backend
```

Without Docker, on macOS / Linux, from `backend/`:

```bash
pip install -r deploy/requirements.txt
gunicorn --bind :8080 deploy.wsgi:app
```

gunicorn does not run on Windows; there, use Docker or `python main.py`.

## Costs

Cloud Run bills only while it answers requests (free tier: 2 million
requests/month). The first request after an idle period takes a few seconds
(cold start, loading the data). For a demo, keep one instance warm:

```bash
gcloud run services update firecal-backend --region europe-west1 --min-instances 1
```

Set it back to `0` afterwards, since a warm instance is billed all the time.
