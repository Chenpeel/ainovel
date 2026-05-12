#!/usr/bin/env bash
# 构建测试镜像并启动容器（8001 端口）
# 用法：./build-test.sh [--no-frontend]
set -e

PLATFORM=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')
IMAGE=mumuainovel:world-map-test
CONTAINER=mumuainovel-test

# 1. 构建前端（除非传 --no-frontend）
if [[ "$1" != "--no-frontend" ]]; then
  echo "==> 构建前端..."
  cd frontend && npm run build && cd ..
fi

# 2. 构建 Docker 镜像（临时允许 backend/static/）
DOCKERIGNORE=.dockerignore
BACKUP=$(mktemp)
cp "$DOCKERIGNORE" "$BACKUP"

# 移除 backend/static/ 排除规则
sed -i.bak '/^backend\/static\/$/d' "$DOCKERIGNORE"
sed -i.bak '/^# 后端静态文件/d' "$DOCKERIGNORE"
rm -f "${DOCKERIGNORE}.bak"

echo "==> 构建测试镜像 $IMAGE ..."
docker build --no-cache -f Dockerfile.test --platform "$PLATFORM" -t "$IMAGE" .

# 恢复 .dockerignore
cp "$BACKUP" "$DOCKERIGNORE"
rm -f "$BACKUP"

# 3. 停止并删除旧容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "==> 停止旧容器..."
  docker stop "$CONTAINER" 2>/dev/null || true
  docker rm "$CONTAINER" 2>/dev/null || true
fi

# 4. 读取 .env 里的数据库配置（必须由 .env 提供，避免硬编码凭据）
if [[ ! -f .env ]]; then
  echo "错误：未找到 .env 文件，请先创建并配置 POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB" >&2
  exit 1
fi
source <(grep -E '^(POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB)=' .env)
: "${POSTGRES_USER:?请在 .env 中设置 POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?请在 .env 中设置 POSTGRES_PASSWORD}"
: "${POSTGRES_DB:?请在 .env 中设置 POSTGRES_DB}"

# 5. 启动新容器
echo "==> 启动容器 $CONTAINER ..."
docker run -d \
  --name "$CONTAINER" \
  --platform "$PLATFORM" \
  --network mumuainovel_ai-story-network \
  -p 8001:8000 \
  --env-file .env \
  -e "DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}" \
  -e DB_HOST=postgres \
  -e APP_PORT=8000 \
  -e SESSION_COOKIE_SECURE=false \
  -e FRONTEND_URL=http://localhost:8001 \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/storage/generated_covers:/app/storage/generated_covers" \
  "$IMAGE"

echo "==> 完成！访问 http://localhost:8001"
