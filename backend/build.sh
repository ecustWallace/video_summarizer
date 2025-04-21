gcloud run deploy backend \
  --source . \
  --region us-central1 \
  --vpc-connector=wallace-connector \
  --allow-unauthenticated
