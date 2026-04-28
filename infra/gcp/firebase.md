# Firebase Setup

## Prerequisites
- GCP project (same as Cloud SQL)
- Firebase enabled on the project
- Firebase CLI installed

## Initialize Firebase in GCP project

```bash
gcloud services enable firebase.googleapis.com
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member=serviceAccount:firebase-adminsdk-<IDENTIFIER>@<PROJECT_ID>.iam.gserviceaccount.com \
  --role=roles/firebase.admin
```

## Set up Firebase Authentication

1. Enable Sign-in providers:
   - Email/Password
   - Google (optional)
   - GitHub (optional)

2. Create web app in Firebase Console → Project Settings → Add App

3. Copy Firebase config for frontend:
   - API Key
   - Auth Domain
   - Project ID
   - Storage Bucket
   - Messaging Sender ID
   - App ID

## Set up Firebase Storage

1. Enable Cloud Storage for Firebase
2. Create bucket (default: gs://<PROJECT_ID>.appspot.com)
3. Set Storage Rules:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /volunteers/{volunteer_id}/certs/{document=**} {
      allow read: if request.auth.uid == volunteer_id;
      allow write: if request.auth.uid == volunteer_id;
    }
    match /ngos/{ngo_id}/events/{document=**} {
      allow read: if request.auth.uid != null;
      allow write: if request.auth.uid == resource.data.firebase_uid;
    }
  }
}
```

## Environment variables for Frontend

Set in `.env.local`:
- `NEXT_PUBLIC_FIREBASE_API_KEY`
- `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID`
- `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
- `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`
- `NEXT_PUBLIC_FIREBASE_APP_ID`

## Service account for backend

1. Go to Firebase Console → Project Settings → Service Accounts
2. Generate new private key (JSON)
3. Set `GOOGLE_APPLICATION_CREDENTIALS` to path of JSON file
