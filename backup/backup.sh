#!/bin/sh
set -e

BACKUP_DIR="/backups/$(date +%Y-%m-%d_%H-%M-%S)"
mkdir -p "$BACKUP_DIR"

echo "[backup] Starting backup at $(date)"

# PostgreSQL
echo "[backup] Dumping PostgreSQL..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > "$BACKUP_DIR/postgres.sql.gz"
echo "[backup] PostgreSQL done."

# Qdrant snapshot
echo "[backup] Creating Qdrant snapshot..."
SNAPSHOT=$(curl -sf -X POST "http://qdrant:6333/snapshots" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$SNAPSHOT" ]; then
  curl -sf "http://qdrant:6333/snapshots/$SNAPSHOT" -o "$BACKUP_DIR/qdrant_snapshot.tar"
  echo "[backup] Qdrant snapshot saved: $SNAPSHOT"
else
  echo "[backup] Qdrant snapshot failed or empty"
fi

# MinIO mirror (mc must be available)
if command -v mc > /dev/null 2>&1; then
  echo "[backup] Mirroring MinIO bucket..."
  mc alias set minio "http://minio:9000" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --quiet
  mc mirror "minio/$MINIO_BUCKET" "$BACKUP_DIR/minio/" --quiet
  echo "[backup] MinIO mirror done."
fi

# Remove backups older than BACKUP_RETAIN_DAYS (default 7)
RETAIN="${BACKUP_RETAIN_DAYS:-7}"
find /backups -maxdepth 1 -type d -mtime "+$RETAIN" -exec rm -rf {} + 2>/dev/null || true

echo "[backup] Completed at $(date). Saved to $BACKUP_DIR"
