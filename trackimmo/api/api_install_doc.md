# TrackImmo API Documentation

## Installation & Deployment

### Server Setup

The TrackImmo API is deployed on VPS at `http://147.93.94.3:8000` with the following setup:

```bash
# Project structure
/opt/trackimmo/                 # Main project directory
├── venv/                       # Python virtual environment
├── trackimmo/                  # API source code
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables
└── logs/                       # Application logs

# System service
/etc/systemd/system/trackimmo-api.service    # Systemd service file
```

### Environment Configuration

Required environment variables in `/opt/trackimmo/.env`:

```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# API Authentication
API_KEY=cb67274b99d89ab5
ADMIN_API_KEY=cb67274b99d89ab5

# Email Configuration
EMAIL_SENDER=noreply@trackimmo.app
SMTP_SERVER=smtp.hostinger.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_user
SMTP_PASSWORD=your_smtp_password

# API Settings
API_BASE_URL=http://147.93.94.3:8000
MIN_PROPERTY_AGE_YEARS=6
MAX_PROPERTY_AGE_YEARS=8
```

### Service Management

```bash
# Check API status
systemctl status trackimmo-api

# Start/stop API
systemctl start trackimmo-api
systemctl stop trackimmo-api

# View logs
journalctl -u trackimmo-api -f

# Restart API
systemctl restart trackimmo-api
```

### Deployment Process

Automatic deployment via GitHub Actions:

1. **Stop** current API service
2. **Backup** current version
3. **Update** code from GitHub
4. **Install** dependencies
5. **Test** app import
6. **Start** new API
7. **Verify** health check
8. **Rollback** if any step fails

## Base URL

``` txt
Production: http://147.93.94.3:8000
```

## Authentication

All endpoints require API key authentication:

```bash
# Client APIs
curl -H "X-API-Key: cb67274b99d89ab5" http://147.93.94.3:8000/api/...

# Admin APIs  
curl -H "X-Admin-Key: cb67274b99d89ab5" http://147.93.94.3:8000/admin/...
```

## Core Endpoints

### Health & Status

#### **GET /health**

Basic API health check.

```bash
curl http://147.93.94.3:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "service": "TrackImmo API", 
  "version": "1.0.1"
}
```

#### **GET /admin/health**

Detailed health check with database and email status.

```bash
curl -H "X-Admin-Key: cb67274b99d89ab5" http://147.93.94.3:8000/admin/health
```

## Client Processing

### **POST /api/process-client**

Process client with business rules (6-8 year old properties, weighted selection).

```bash
curl -X POST \
     -H "X-API-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"client_id": "e86f4960-f848-4236-b45c-0759b95db5a3"}' \
     http://147.93.94.3:8000/api/process-client
```

**Response:**

```json
{
  "success": true,
  "job_id": "job-uuid",
  "client_id": "client-uuid",
  "message": "Processing started"
}
```

### **POST /api/add-addresses**

Add specific number of addresses to client.

```bash
curl -X POST \
     -H "X-API-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"client_id": "client-uuid", "count": 5}' \
     http://147.93.94.3:8000/api/add-addresses
```

### **GET /api/job-status/{job_id}**

Check processing job status.

```bash
curl -H "X-API-Key: cb67274b99d89ab5" \
     http://147.93.94.3:8000/api/job-status/job-uuid
```

### **GET /api/get-client-properties/{client_id}**

Get client's assigned properties with pagination.

```bash
curl -H "X-API-Key: cb67274b99d89ab5" \
     "http://147.93.94.3:8000/api/get-client-properties/client-uuid?limit=10"
```

## Administration

### **GET /admin/stats**

System statistics (clients, properties, jobs).

```bash
curl -H "X-Admin-Key: cb67274b99d89ab5" \
     http://147.93.94.3:8000/admin/stats
```

### **GET /admin/clients**

List all clients with filtering.

```bash
curl -H "X-Admin-Key: cb67274b99d89ab5" \
     "http://147.93.94.3:8000/admin/clients?status=active&limit=10"
```

### **POST /admin/test-email**

Test email templates and SMTP configuration.

```bash
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "test@example.com", "template_type": "notification"}' \
     http://147.93.94.3:8000/admin/test-email
```

**Template Types:** `config`, `welcome`, `notification`, `error`

### **POST /admin/test-client-processing**

Test client processing without full scraping.

```bash
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"client_id": "client-uuid", "count": 3}' \
     http://147.93.94.3:8000/admin/test-client-processing
```

## Business Rules

### Property Assignment Logic

- **Age Filter**: Properties sold 6-8 years ago only
- **Client Match**: Must match client's cities and property types
- **No Duplicates**: Excludes previously assigned properties
- **Weighted Selection**: Prioritizes older properties with linear weighting
- **Auto Email**: Sends HTML notification email on successful assignment

## Error Handling

**HTTP Status Codes:**

- `200`: Success
- `401`: Invalid API key
- `404`: Resource not found
- `500`: Server error

**Error Format:**

```json
{
  "detail": "Error description"
}
```

## Complete Test Workflow

```bash
# Test client environment
API_KEY="cb67274b99d89ab5"
CLIENT_ID="e86f4960-f848-4236-b45c-0759b95db5a3"
BASE_URL="http://147.93.94.3:8000"

# 1. Health check
curl $BASE_URL/health

# 2. Client info
curl -H "X-Admin-Key: $API_KEY" $BASE_URL/admin/client/$CLIENT_ID

# 3. Current properties
curl -H "X-API-Key: $API_KEY" "$BASE_URL/api/get-client-properties/$CLIENT_ID?limit=3"

# 4. Add properties
RESPONSE=$(curl -s -X POST \
     -H "X-API-Key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d "{\"client_id\": \"$CLIENT_ID\", \"count\": 3}" \
     $BASE_URL/api/add-addresses)

# 5. Check job status
JOB_ID=$(echo $RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
curl -H "X-API-Key: $API_KEY" $BASE_URL/api/job-status/$JOB_ID

# 6. Test email
curl -X POST \
     -H "X-Admin-Key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "test@example.com", "template_type": "config"}' \
     $BASE_URL/admin/test-email
```

## Troubleshooting

### Check API Status

```bash
# Service status
systemctl status trackimmo-api

# Process check
ps aux | grep uvicorn

# Port check
netstat -tlnp | grep 8000

# Logs
journalctl -u trackimmo-api -f
```

### Manual Restart

```bash
# If service fails
cd /opt/trackimmo
source venv/bin/activate
python3 -m uvicorn trackimmo.app:app --host 0.0.0.0 --port 8000
```

### Database Test

```bash
cd /opt/trackimmo
source venv/bin/activate
python3 -c "from trackimmo.modules.db_manager import DBManager; print('DB OK')"
```

The API runs 24/7 with automatic deployment, monitoring, and rollback capabilities for reliable operation.
