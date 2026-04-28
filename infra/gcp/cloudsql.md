# Google Cloud SQL Setup

## Prerequisites
- GCP project with billing enabled
- Cloud SQL Admin API enabled
- gcloud CLI installed and authenticated

## Create Cloud SQL instance

```bash
gcloud sql instances create volunteer-platform-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --availability-type=ZONAL
```

## Create database

```bash
gcloud sql databases create volunteer_platform \
  --instance=volunteer-platform-db
```

## Create user

```bash
gcloud sql users create volunteer_user \
  --instance=volunteer-platform-db \
  --password=<STRONG_PASSWORD>
```

## Get connection details

```bash
gcloud sql instances describe volunteer-platform-db --format='value(ipAddresses[0].ipAddress)'
```

## Connection string (private IP from Cloud Run)

```
postgresql://volunteer_user:<PASSWORD>@<PRIVATE_IP>/volunteer_platform
```

## Environment variables for Cloud Run

- `DATABASE_URL`: postgresql://volunteer_user:<PASSWORD>@<PRIVATE_IP>/volunteer_platform
- `GOOGLE_APPLICATION_CREDENTIALS`: path to service account JSON (should be set by Cloud Run)
