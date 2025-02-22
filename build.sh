docker build -t video-summarizer .
gcloud builds submit --tag us-central1-docker.pkg.dev/glossy-reserve-450922-p9/video-summarizer/video-summarizer
docker push us-central1-docker.pkg.dev/glossy-reserve-450922-p9/video-summarizer/video-summarizer
gcloud run deploy fastapi-video-summarizer \
  --image us-central1-docker.pkg.dev/glossy-reserve-450922-p9/video-summarizer/video-summarizer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated