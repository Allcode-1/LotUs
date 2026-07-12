# MinIO object storage

This compose file runs a single-node MinIO server for learning S3-compatible object storage.

## VPS setup

Copy the example env file and replace the credentials:

```bash
cp .env.minio.example .env.minio
nano .env.minio
```

Start MinIO:

```bash
docker compose --env-file .env.minio -f docker-compose.minio.yml pull
docker compose --env-file .env.minio -f docker-compose.minio.yml up -d
```

Check status and logs:

```bash
docker compose --env-file .env.minio -f docker-compose.minio.yml ps
docker compose --env-file .env.minio -f docker-compose.minio.yml logs -f minio
docker compose --env-file .env.minio -f docker-compose.minio.yml logs minio-init
```

Open the console:

```text
http://<vps-ip>:9001
```

The S3 API endpoint is:

```text
http://<vps-ip>:9000
```

## App settings

For FastAPI/boto3, use MinIO as an S3-compatible endpoint:

```env
S3_ENDPOINT_URL=http://<vps-ip>:9000
S3_BUCKET=lotus-media
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=lotus-root
S3_SECRET_ACCESS_KEY=change-me-to-a-long-random-password
S3_FORCE_PATH_STYLE=true
```

With an IP-based endpoint, configure the S3 client for path-style addressing.

## Notes

- Keep the bucket private with `MINIO_DEFAULT_BUCKET_ANONYMOUS_POLICY=none`.
- Generate presigned URLs from the backend when users need to read private images.
- Do not commit `.env.minio`; it contains real storage credentials.
- For a public test bucket, set `MINIO_DEFAULT_BUCKET_ANONYMOUS_POLICY=download`.
- For real production, put MinIO behind HTTPS, restrict firewall access, and create a limited app access key instead of using root credentials.
- If logs show `Fatal glibc error: CPU does not support x86-64-v2`, use the pinned `cpuv1` images from `.env.minio.example` or move to a newer VPS CPU.

## Stop

```bash
docker compose --env-file .env.minio -f docker-compose.minio.yml down
```

To delete stored objects too:

```bash
docker compose --env-file .env.minio -f docker-compose.minio.yml down -v
```
