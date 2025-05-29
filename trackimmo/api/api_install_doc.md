# TrackImmo API Documentation

## Installation & Setup

### Prerequisites

- Python 3.11+
- Ubuntu/Debian server
- Git access to repository
- Supabase database configured

### Quick Install

```bash
# 1. Clone repository
git clone <repository-url> /opt/trackimmo
cd /opt/trackimmo

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install fastapi uvicorn supabase pydantic-settings

# 4. Create environment file
cp .env.example .env
nano .env  # Configure your settings
```

### Environment Configuration (.env)

```bash
# Required Database Settings
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
API_KEY=cb67274b99d89ab5

# Email Settings (Optional)
EMAIL_SENDER=noreply@trackimmo.app
SMTP_SERVER=smtp.hostinger.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_user
SMTP_PASSWORD=your_smtp_password

# Server Settings
API_BASE_URL=http://147.93.94.3:8000
DEBUG=false
```

### Create Core Files

Create the main application files if missing:

**trackimmo/api/__init__.py**
```python
"""API package for TrackImmo."""
```

**trackimmo/utils/__init__.py**
```python
"""Utilities package for TrackImmo."""
```

### Service Setup

```bash
# Create systemd service
sudo nano /etc/systemd/system/trackimmo-api.service
```

**Service file content:**
```ini
[Unit]
Description=TrackImmo API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trackimmo
Environment=PATH=/opt/trackimmo/venv/bin
ExecStart=/opt/trackimmo/venv/bin/uvicorn trackimmo.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable trackimmo-api
sudo systemctl start trackimmo-api
sudo systemctl status trackimmo-api
```

### Verification

```bash
# Check service status
sudo systemctl status trackimmo-api

# Test API health
curl http://localhost:8000/health

# Check from external
curl http://147.93.94.3:8000/health
```

### GitHub Actions Deployment

The repository includes automated deployment via GitHub Actions. Required secrets:

- `HOST`: Server IP (147.93.94.3)
- `USERNAME`: SSH username (root)
- `SSH_KEY`: Private SSH key for server access

Deployment triggers on push to main branch and automatically:
1. Tests code syntax
2. Connects to server via SSH
3. Pulls latest changes
4. Installs dependencies
5. Restarts API service
6. Verifies deployment

### Troubleshooting

**API not responding:**
```bash
# Check process
ps aux | grep uvicorn

# Check logs
sudo journalctl -u trackimmo-api -f

# Manual restart
sudo systemctl restart trackimmo-api
```

**Missing files:**
```bash
# Create required directories
mkdir -p trackimmo/api trackimmo/utils tests

# Create missing __init__.py files
touch trackimmo/api/__init__.py
touch trackimmo/utils/__init__.py
```

**Database connection issues:**
```bash
# Test Supabase connection
python3 -c "
from trackimmo.modules.db_manager import DBManager
with DBManager() as db:
    response = db.get_client().table('clients').select('client_id').limit(1).execute()
    print('Database OK')
"
```

## API Reference

### Base URL
```
Production: http://147.93.94.3:8000
```

### Authentication
All endpoints require `X-API-Key` header:
```bash
curl -H "X-API-Key: cb67274b99d89ab5" http://147.93.94.3:8000/api/...
```

### Core Endpoints

#### Health Check
```bash
GET /health
# Response: {"status": "ok", "service": "TrackImmo API", "version": "1.0.0"}
```

#### Client Processing
```bash
POST /api/process-client
Content-Type: application/json
X-API-Key: cb67274b99d89ab5

{"client_id": "e86f4960-f848-4236-b45c-0759b95db5a3"}
```

#### Admin Statistics
```bash
GET /admin/stats
X-Admin-Key: cb67274b99d89ab5
```

### Example Usage

```bash
# Test client processing
curl -X POST \
  -H "X-API-Key: cb67274b99d89ab5" \
  -H "Content-Type: application/json" \
  -d '{"client_id": "e86f4960-f848-4236-b45c-0759b95db5a3"}' \
  http://147.93.94.3:8000/api/process-client

# Check job status (use job_id from response)
curl -H "X-API-Key: cb67274b99d89ab5" \
  http://147.93.94.3:8000/api/job-status/JOB_ID

# Get client properties
curl -H "X-API-Key: cb67274b99d89ab5" \
  "http://147.93.94.3:8000/api/get-client-properties/e86f4960-f848-4236-b45c-0759b95db5a3?limit=5"
```

### Business Logic

The API implements property assignment rules:
- Properties sold 6-8 years ago
- Weighted selection favoring older properties
- Matches client's city and property type preferences
- Automatic deduplication and email notifications

### Support

For issues:
1. Check service status: `sudo systemctl status trackimmo-api`
2. Review logs: `sudo journalctl -u trackimmo-api -f`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Verify configuration: `python3 -c "from trackimmo.config import settings; print('Config OK')"`