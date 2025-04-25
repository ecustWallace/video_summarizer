#!/bin/bash
# 构建和部署脚本

# 获取项目ID
PROJECT_ID=$(gcloud config get-value project)
echo "Using project: $PROJECT_ID"

# 构建Docker镜像
docker build -t backend .

# 确保服务账号存在并有正确的权限
SERVICE_ACCOUNT="video-summarizer-backend@$PROJECT_ID.iam.gserviceaccount.com"

# 检查服务账号是否存在，如果不存在则创建
if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT &>/dev/null; then
  echo "Creating service account: $SERVICE_ACCOUNT"
  gcloud iam service-accounts create video-summarizer-backend \
    --display-name="Video Summarizer Backend Service Account"
fi

# 确保服务账号有 Pub/Sub 权限
echo "Granting Pub/Sub publisher and subscriber roles to service account"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/pubsub.subscriber"

# 部署到Cloud Run
gcloud run deploy backend \
  --image backend \
  --platform managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --concurrency=80 \
  --timeout=3600 \
  --memory=512Mi \
  --cpu=1 \
  --session-affinity \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
  --service-account=$SERVICE_ACCOUNT \
  --region=us-central1
