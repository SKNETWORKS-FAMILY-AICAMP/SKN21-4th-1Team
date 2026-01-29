#!/bin/bash
IMAGE_NAME="qdrant_test:latest"
CONTAINER_QDRANT_NAME="qdrant_test"
QDRANT_SERVER_DATA_DIR="/home/ubuntu/qdrant_data"
QDRANT_DATA_DIR="/qdrant/storage"
QDRANT_PORT=6333

# Docker 빌드
docker build -f docker_build/Dockerfile -t $IMAGE_NAME .

QDRANT_EXISTING=$(docker ps -a -q -f name=$CONTAINER_QDRANT_NAME)
if [ -n "$QDRANT_EXISTING" ]; then
    docker rm -f $CONTAINER_QDRANT_NAME
fi

# 데이터 디렉토리 생성
mkdir -p $QDRANT_SERVER_DATA_DIR



#qdrant 컨테이너 실행
docker run -d \
    --name $CONTAINER_QDRANT_NAME \
    -p $QDRANT_PORT:$QDRANT_PORT \
    -v $QDRANT_SERVER_DATA_DIR:$QDRANT_DATA_DIR \
    $IMAGE_NAME


docker ps -f name=$CONTAINER_QDRANT_NAME