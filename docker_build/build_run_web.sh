#!/bin/bash
IMAGE_NAME="test:latest"
CONTAINER_WEB_NAME="test"
WEB_SERVER_DATA_DIR="/home/ubuntu/docker_web_data"
WEB_DATA_DIR="/app/data"
WEB_PORT=8000

# Docker 빌드
docker build -f docker_build/Dockerfile -t $IMAGE_NAME .

# 기존 컨테이너 제거
WEB_EXISTING=$(docker ps -a -q -f name=$CONTAINER_WEB_NAME)
if [ -n "$WEB_EXISTING" ]; then
    docker rm -f $CONTAINER_WEB_NAME
fi

# 데이터 디렉토리 생성
mkdir -p $WEB_SERVER_DATA_DIR



#웹 컨테이너 실행
docker run -d \
    --name $CONTAINER_WEB_NAME \
    -p $WEB_PORT:$WEB_PORT \
    -v $WEB_SERVER_DATA_DIR:$WEB_DATA_DIR \
    $IMAGE_NAME


docker ps -f name=$CONTAINER_WEB_NAME