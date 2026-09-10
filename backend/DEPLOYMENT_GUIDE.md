# Deployment Guide

This guide covers deploying the backend and frontend to a production
environment. For local development setup, see `SETUP.md`.

---

## Pre-deployment checklist

Before deploying, verify:

- [ ] `REQUIRE_AUTH=true` is set in `.env`
- [ ] `API_KEY` and `ADMIN_API_KEY` are strong random strings
- [ ] `TRUSTED_ORIGINS` includes your production frontend URL
- [ ] `ALLOWED_RECIPIENTS` is set to your agent email addresses
- [ ] `DATABASE_URL` points to your production Postgres instance
- [ ] `SMTP_*` credentials are valid and an App Password is used
- [ ] `APP_ENV=production` and `LOG_LEVEL=WARNING`
- [ ] The database schema has been applied (`database_schema.sql`)
- [ ] HTTPS is configured (use a reverse proxy with Let's Encrypt)

---

## Backend deployment

### Option A: Docker

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ /app/

# Expose the port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Build and run:

```bash
docker build -t real-estate-agent:latest .

docker run -d \
  --name real-estate-agent \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/backend/data:/app/data \
  -v $(pwd)/backend/documents:/app/documents \
  --restart unless-stopped \
  real-estate-agent:latest
```

### Option B: Systemd service

Create `/etc/systemd/system/real-estate-agent.service`:

```ini
[Unit]
Description=Real Estate Voice Agent
After=network.target postgresql.service

[Service]
Type=simple
User=real-estate
WorkingDirectory=/opt/real-estate-agent/backend
EnvironmentFile=/opt/real-estate-agent/backend/.env
ExecStart=/opt/real-estate-agent/backend/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable real-estate-agent
sudo systemctl start real-estate-agent
sudo systemctl status real-estate-agent
```

### Reverse proxy (nginx)

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Rate limiting at the proxy level (defense in depth)
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 30s;
    }
}
```

### Reverse proxy (Caddy)

```caddy
api.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy automatically provisions and renews Let's Encrypt certificates.

---

## Frontend deployment

### Option A: Vercel (recommended)

The Next.js frontend deploys cleanly to Vercel:

1. Push the repository to GitHub
2. Import the repo into Vercel
3. Set the root directory to `frontend/`
4. Add environment variables:
   - `NEXT_PUBLIC_API_KEY` — your backend's `API_KEY`
   - `NEXT_PUBLIC_BACKEND_URL` — `https://api.yourdomain.com`
5. Deploy

### Option B: Self-hosted with PM2

```bash
cd frontend
npm install
npm run build

# Install PM2 globally
npm install -g pm2

# Start the Next.js production server
pm2 start npm --name "real-estate-frontend" -- start
pm2 save
pm2 startup
```

---

## Database deployment

Use a managed PostgreSQL service for production. Recommended options:

| Provider | Free tier | Notes |
|----------|-----------|-------|
| Neon | Yes (3 GB) | Serverless, autoscaling |
| Supabase | Yes (500 MB) | Includes auth and storage |
| AWS RDS | No | Most flexible, most setup |
| Google Cloud SQL | No | Similar to RDS |
| DigitalOcean Managed DB | No | Simple, predictable pricing |

Once your database is provisioned, apply the schema:

```bash
psql "$DATABASE_URL" -f backend/database_schema.sql
```

Verify the tables exist:

```bash
psql "$DATABASE_URL" -c "\dt"
```

You should see: `leads`, `call_sessions`, `property_recommendations`,
`appointments`, `followups`, `lead_memory`, `call_history`.

---

## Post-deployment verification

After deploying, run through these checks:

### 1. Health check

```bash
curl https://api.yourdomain.com/
# {"status":"ok","app":"real_estate_voice_agent","version":"1.0.0",...}
```

### 2. Property catalog

```bash
curl https://api.yourdomain.com/properties?limit=5
# Should return 5 properties with realistic Pakistani data
```

### 3. Authentication

```bash
# Without API key (should be 401)
curl -o /dev/null -w "%{http_code}\n" https://api.yourdomain.com/appointments
# 401

# With valid API key (should be 200)
curl -H "X-API-Key: $API_KEY" https://api.yourdomain.com/appointments
# {"appointments":[...]}
```

### 4. Email flow

```bash
curl -X POST https://api.yourdomain.com/appointments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "client_name":"Deploy Test",
    "client_phone":"+923001234567",
    "property_id":"P001",
    "property_title":"5 Marla House in DHA Phase 6",
    "scheduled_at":"2099-01-01T10:00:00+00:00",
    "employee_email":"founder@yourdomain.com"
  }'
```

Verify the email arrives in the founder@yourdomain.com inbox.

### 5. Frontend

Open `https://yourdomain.com` and:

- Verify the Properties tab loads 42 properties
- Send a chat message in the Assistant tab
- Verify the Agent Memory tab shows 5 topic clusters

---

## Backup strategy

### Database

Set up automated daily backups of your PostgreSQL database. Most managed
providers offer this out of the box (Neon: point-in-time recovery;
RDS: automated snapshots).

For self-hosted Postgres:

```bash
# Daily backup cron job
0 2 * * * pg_dump "$DATABASE_URL" | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz
# Retain 30 days
0 3 * * * find /backups -name "db-*.sql.gz" -mtime +30 -delete
```

### Conversation memory

The learner's corpus is stored in `backend/app/data/conversation_memory.json`.
Back this up to persistent storage (it's small, ~100 KB per 100 conversations).

### Property catalog

The CSV files in `backend/data/` are version-controlled and don't need
backup — they can be regenerated with `scripts/generate_dataset.py`.

---

## Monitoring

### Logs

The backend logs to stdout in a structured format. Pipe to your log
aggregator of choice (Loki, ELK, CloudWatch Logs).

Look for the `AUDIT` prefix on every request line for request-level
monitoring:

```
AUDIT ip=1.2.3.4 method=POST path=/appointments q= status=200 duration=850ms SENSITIVE
```

### Health check endpoint

Set up an external uptime monitor (UptimeRobot, Pingdom) hitting
`https://api.yourdomain.com/` every minute.

### Rate limit monitoring

```bash
curl -H "X-API-Key: $ADMIN_API_KEY" \
  https://api.yourdomain.com/admin/rate-limit/stats
```

Returns the current size of each rate-limit bucket per IP. Watch for
sustained high counts which indicate abuse.

---

## Updating the deployment

To deploy a new version:

```bash
# Backend
cd /opt/real-estate-agent
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart real-estate-agent

# Frontend (Vercel)
git push origin main
# Vercel auto-deploys on push

# Frontend (self-hosted)
cd /opt/real-estate-agent/frontend
git pull origin main
npm install
npm run build
pm2 restart real-estate-frontend
```

### Database migrations

When the schema changes, apply the new `database_schema.sql`:

```bash
psql "$DATABASE_URL" -f backend/database_schema.sql
```

The schema uses `CREATE TABLE IF NOT EXISTS` so it's safe to re-run.
For destructive changes (column renames, type changes), write a proper
migration with `ALTER TABLE` statements.
