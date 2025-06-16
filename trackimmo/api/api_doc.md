# TrackImmo API Documentation

## Overview

The TrackImmo API provides comprehensive endpoints for managing real estate client processing, property assignments, and system administration. The API is built with FastAPI and follows RESTful principles with asynchronous processing capabilities.

## Base URL

``` txt
Production: http://147.93.94.3:8000
Development: http://localhost:8000
```

## Authentication

All API endpoints require authentication via API key headers:

- **Client Processing APIs**: `X-API-Key` header
- **Admin APIs**: `X-Admin-Key` header (falls back to `X-API-Key` if not configured)

```bash
# Client API calls
curl -H "X-API-Key: cb67274b99d89ab5" http://147.93.94.3:8000/api/...

# Admin API calls  
curl -H "X-Admin-Key: cb67274b99d89ab5" http://147.93.94.3:8000/admin/...
```

## Core Endpoints

### Health & Status

#### **GET /health**

Basic health check for the API service.

**Response:**

```json
{
  "status": "ok",
  "service": "TrackImmo API", 
  "version": "1.0.2"
}
```

#### **GET /version**

Get API version information.

**Response:**

```json
{
  "version": "1.0.2",
  "service": "TrackImmo API"
}
```

#### **GET /admin/health**

Detailed health check including database and email connectivity.

**Headers:** `X-Admin-Key`

**Response:**

```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {
      "status": "ok",
      "message": "Connected, 150 total clients"
    },
    "email": {
      "status": "ok", 
      "message": "SMTP configuration valid"
    }
  }
}
```

## Client Processing

### **POST /api/process-client**

Process a client to assign new properties following business rules.

**Headers:** `X-API-Key`

**Request Body:**

```json
{
  "client_id": "e86f4960-f848-4236-b45c-0759b95db5a3"
}
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

**Process Flow:**

1. Validates client exists and is active
2. Updates client's city data if stale (>90 days)
3. Scrapes new properties if insufficient data (<50 properties in 6-8 year range)
4. Assigns properties using weighted selection (favoring older properties)
5. **Sends email notification if successful** ✅
6. **Sends CTO alert if insufficient addresses found** ✅
7. Returns immediately with job ID for tracking

### **POST /api/add-addresses**

Add specific number of addresses to an existing client.

**Headers:** `X-API-Key`

**Request Body:**

```json
{
  "client_id": "client-uuid",
  "count": 5  // Optional, uses client's subscription default if omitted
}
```

**Response:**

```json
{
  "success": true,
  "job_id": "job-uuid", 
  "client_id": "client-uuid",
  "message": "Adding 5 addresses"
}
```

### **GET /api/job-status/{job_id}**

Get the status of a processing job.

**Headers:** `X-API-Key`

**Response:**

```json
{
  "job_id": "job-uuid",
  "client_id": "client-uuid", 
  "status": "completed",  // pending, processing, completed, failed
  "properties_assigned": 8,
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  "progress": {}
}
```

### **GET /api/get-client-properties/{client_id}**

Get properties assigned to a client with pagination.

**Headers:** `X-API-Key`

**Query Parameters:**

- `limit` (optional): Maximum properties to return (default: 100)
- `offset` (optional): Number of properties to skip (default: 0)

**Response:**

```json
{
  "success": true,
  "client_id": "client-uuid",
  "total_count": 45,
  "returned_count": 10,
  "properties": [
    {
      "address_id": "address-uuid",
      "address_raw": "123 Rue de la Paix",
      "city_name": "Paris", 
      "price": 450000,
      "surface": 75,
      "rooms": 3,
      "property_type": "apartment",
      "sale_date": "2018-06-15",
      "client_address_info": {
        "status": "new",
        "send_date": "2024-01-15T10:30:00Z",
        "notes": null
      }
    }
  ]
}
```

## Business Rules

### Property Assignment Logic

The API implements specific business rules for property assignment:

**Age Criteria:**

- Properties must be sold between **6-8 years ago**
- Calculated as 6*365 to 8*365 days from current date

**Selection Criteria:**

- Must match client's `chosen_cities`
- Must match client's `property_type_preferences`
- Cannot be previously assigned to the same client
- Automatic deduplication by address

**Weighted Selection:**

- Older properties within the range are favored
- Uses linear weighting: oldest property gets highest weight
- Semi-random selection maintains variety while prioritizing age

**Example Weight Calculation:**

```python
# For 10 properties sorted by sale_date (oldest first)
# Property 1 (oldest): weight = 10
# Property 2: weight = 9  
# Property 3: weight = 8
# ...
# Property 10 (newest): weight = 1
```

## Job Management

### **POST /api/process-retry-queue**

Process the retry queue for failed jobs.

**Headers:** `X-API-Key`

**Response:**

```json
{
  "success": true,
  "processed": 3,
  "failed": 1, 
  "message": "Processed 3 jobs, 1 failed"
}
```

### **POST /api/cleanup-jobs**

Clean up completed and failed jobs older than specified days.

**Headers:** `X-API-Key`

**Query Parameters:**

- `older_than_days` (optional): Days threshold (default: 7)

**Response:**

```json
{
  "success": true,
  "cleaned_jobs": 12,
  "message": "Cleaned 12 jobs older than 7 days"
}
```

## Administration

### **GET /admin/stats**

Get comprehensive system statistics.

**Headers:** `X-Admin-Key`

**Response:**

```json
{
  "total_clients": 150,
  "active_clients": 125,
  "total_properties": 50000,
  "total_assignments": 2400,
  "jobs_pending": 5,
  "jobs_processing": 2,
  "jobs_completed": 1200,
  "jobs_failed": 15
}
```

### **GET /admin/clients**

List clients with optional filtering.

**Headers:** `X-Admin-Key`

**Query Parameters:**

- `status` (optional): Filter by client status (active, inactive, etc.)
- `limit` (optional): Maximum clients to return (default: 50)
- `offset` (optional): Number of clients to skip (default: 0)

**Response:**

```json
[
  {
    "client_id": "client-uuid",
    "first_name": "John",
    "last_name": "Doe", 
    "email": "john@example.com",
    "status": "active",
    "subscription_type": "pro",
    "chosen_cities": ["city-uuid-1", "city-uuid-2"],
    "property_type_preferences": ["house", "apartment"],
    "addresses_per_report": 10,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### **GET /admin/client/{client_id}**

Get detailed information about a specific client.

**Headers:** `X-Admin-Key`

**Response:**

```json
{
  "client": {
    "client_id": "client-uuid",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "status": "active",
    "subscription_type": "pro",
    "chosen_cities": ["city-uuid-1"],
    "property_type_preferences": ["house", "apartment"]
  },
  "assigned_properties_count": 45,
  "recent_jobs": [
    {
      "job_id": "job-uuid",
      "status": "completed", 
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "cities": [
    {
      "city_id": "city-uuid",
      "name": "Paris",
      "postal_code": "75001",
      "insee_code": "75101"
    }
  ]
}
```

### **GET /admin/jobs**

List processing jobs with optional filtering.

**Headers:** `X-Admin-Key`

**Query Parameters:**

- `status` (optional): Filter by job status
- `limit` (optional): Maximum jobs to return (default: 50)
- `offset` (optional): Number of jobs to skip (default: 0)

**Response:**

```json
[
  {
    "job_id": "job-uuid",
    "client_id": "client-uuid",
    "status": "completed",
    "attempt_count": 1,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:35:00Z",
    "clients": {
      "first_name": "John",
      "last_name": "Doe", 
      "email": "john@example.com"
    }
  }
]
```

## Email System

### Email Templates

The API includes **five HTML email templates** with clean, simple design matching Supabase style:

1. **Client Notification**: New property assignments ✅
2. **Welcome**: New client onboarding ✅
3. **Monthly Notification**: Pre-notification about upcoming addresses ✨ **NEW**
4. **Error Alert**: Admin notifications for failures ✅
5. **Insufficient Addresses**: CTO alert when not enough properties found ✨ **NEW**

### Template Features

- **Clean Design**: Simple, readable layout matching Supabase template style
- **TrackImmo Branding**: Consistent colors (#6c63ff, #8b84ff) and logo
- **Responsive**: Mobile and desktop compatible
- **Professional**: Modern design with clear call-to-actions
- **Fallback Support**: Plain text versions for compatibility

### **POST /admin/test-email**

Test email functionality with different templates.

**Headers:** `X-Admin-Key`

**Request Body:**

```json
{
  "recipient": "test@example.com",
  "template_type": "notification"  // config, welcome, notification, monthly, insufficient, error
}
```

**Template Types:**

- `config`: Tests SMTP configuration and sends test email
- `welcome`: Sends welcome email template
- `notification`: Sends property notification template  
- `monthly`: Sends monthly pre-notification template ✨ **NEW**
- `insufficient`: Sends insufficient addresses alert to CTO ✨ **NEW**
- `error`: Sends admin error notification

**Response:**

```json
{
  "success": true,
  "message": "Notification email sent to test@example.com",
  "results": {
    "smtp_config": true,
    "connection": true,
    "send_test": true
  }
}
```

### Email Flow

#### Daily Processing Flow

1. **Monthly Notifications** (runs first):
   - Checks clients scheduled for tomorrow's `send_day`
   - Sends monthly pre-notification emails ✨ **NEW**
   - Handles end-of-month edge cases

2. **Client Processing**:
   - Processes clients matching today's `send_day`
   - Assigns new properties
   - Sends notification emails on success
   - Sends CTO alert if insufficient addresses ✨ **NEW**

3. **Retry Queue**:
   - Processes failed jobs
   - Sends CTO error notification after 3 failed attempts

#### Notification Triggers

| Event | Email Sent | Recipient |
|-------|------------|-----------|
| Successful property assignment | Client Notification | Client |
| Insufficient addresses found | Insufficient Addresses Alert | CTO |
| Day before send_day | Monthly Notification | Client |
| Job fails 3 times | Error Notification | CTO |
| New client registration | Welcome Email | Client |

## Testing & Utilities

### **POST /admin/test-client-processing**

Test client processing logic without full scraping.

**Headers:** `X-Admin-Key`

**Request Body:**

```json
{
  "client_id": "client-uuid", 
  "count": 5
}
```

**Response:**

```json
{
  "success": true,
  "client_id": "client-uuid",
  "properties_assigned": 5,
  "email_sent": true,
  "properties": [
    {
      "address_raw": "123 Test Street",
      "city_name": "Paris",
      "price": 450000,
      "property_type": "apartment"
    }
  ],
  "message": "Assigned 5 properties to John Doe"
}
```

### **POST /admin/client/{client_id}/reset-assignments**

Reset all property assignments for a client (testing purposes).

**Headers:** `X-Admin-Key`

**Response:**

```json
{
  "success": true,
  "deleted_assignments": 25,
  "message": "Reset 25 assignments for client"
}
```

### **DELETE /admin/jobs/cleanup**

Clean up old jobs with custom time threshold.

**Headers:** `X-Admin-Key`

**Query Parameters:**

- `older_than_days` (optional): Days threshold (default: 30)

**Response:**

```json
{
  "success": true,
  "deleted_jobs": 50,
  "message": "Deleted 50 jobs older than 30 days"
}
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error information:

### Common Status Codes

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Resource not found (client, job, etc.)
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "detail": "Client e86f4960-f848-4236-b45c-0759b95db5a3 not found or inactive"
}
```

### Retry Logic

- Jobs automatically retry up to 3 times with exponential backoff
- Permanent errors (missing client, invalid configuration) are not retried
- Failed jobs after max retries trigger admin notifications
- **CTO receives email alerts for permanent failures** ✅

## Rate Limiting

- Default: 100 requests per hour per API key
- Configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW` settings
- Rate limiting can be disabled with `RATE_LIMIT_ENABLED=false`

## Configuration

### Environment Variables

```bash
# Required
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key  
API_KEY=cb67274b99d89ab5

# Email (required for notifications)
EMAIL_SENDER=noreply@trackimmo.app
SMTP_SERVER=smtp.hostinger.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_user
SMTP_PASSWORD=your_smtp_password
CTO_EMAIL=netechoppe@proton.me  # Required for error/alert notifications

# Optional
ADMIN_API_KEY=cb67274b99d89ab5
API_BASE_URL=http://147.93.94.3:8000
DEFAULT_ADDRESSES_PER_REPORT=10
MIN_PROPERTY_AGE_YEARS=6
MAX_PROPERTY_AGE_YEARS=8
```

### Business Rule Configuration

```bash
# Property age criteria (in years)
MIN_PROPERTY_AGE_YEARS=6
MAX_PROPERTY_AGE_YEARS=8

# Minimum properties per city before scraping more
MIN_PROPERTIES_PER_CITY=50

# Default addresses per client report
DEFAULT_ADDRESSES_PER_REPORT=10

# Job processing settings
MAX_JOB_RETRIES=3
JOB_CLEANUP_DAYS=7
```

## Example Usage

### Complete Client Processing Workflow

```bash
# 1. Check API health
curl http://147.93.94.3:8000/health

# 2. Get client information  
curl -H "X-Admin-Key: cb67274b99d89ab5" \
     http://147.93.94.3:8000/admin/client/e86f4960-f848-4236-b45c-0759b95db5a3

# 3. Process client (assign new properties)
curl -X POST \
     -H "X-API-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"client_id": "e86f4960-f848-4236-b45c-0759b95db5a3"}' \
     http://147.93.94.3:8000/api/process-client

# 4. Check job status
curl -H "X-API-Key: cb67274b99d89ab5" \
     http://147.93.94.3:8000/api/job-status/$JOB_ID

# 5. Get assigned properties
curl -H "X-API-Key: cb67274b99d89ab5" \
     http://147.93.94.3:8000/api/get-client-properties/e86f4960-f848-4236-b45c-0759b95db5a3?limit=10
```

### Testing Email Configuration

```bash
# Test SMTP configuration
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "test@example.com", "template_type": "config"}' \
     http://147.93.94.3:8000/admin/test-email

# Test client notification template
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "test@example.com", "template_type": "notification"}' \
     http://147.93.94.3:8000/admin/test-email

# Test monthly notification template ✨ NEW
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "test@example.com", "template_type": "monthly"}' \
     http://147.93.94.3:8000/admin/test-email

# Test insufficient addresses alert ✨ NEW
curl -X POST \
     -H "X-Admin-Key: cb67274b99d89ab5" \
     -H "Content-Type: application/json" \
     -d '{"recipient": "cto@company.com", "template_type": "insufficient"}' \
     http://147.93.94.3:8000/admin/test-email
```

### Running Daily Updates Script

```bash
# Run daily updates (includes monthly notifications + client processing)
python trackimmo/scripts/run_daily_updates.py

# Test email functionality comprehensively
python trackimmo/scripts/test_email_functionality.py --recipient test@example.com

# Test specific email template
python trackimmo/scripts/test_email_functionality.py --recipient test@example.com --test monthly
```

## Daily Automation

The `run_daily_updates.py` script handles:

1. **Monthly Notifications**: Sent the day before each client's `send_day`
2. **Client Processing**: Assigns new properties to clients on their `send_day`
3. **Retry Queue**: Processes failed jobs with exponential backoff
4. **Error Handling**: Sends CTO alerts for persistent failures

### Cron Job Setup

```bash
# Run daily at 9 AM
0 9 * * * cd /opt/trackimmo && python trackimmo/scripts/run_daily_updates.py >> logs/daily_updates.log 2>&1
```

## Support

For technical support or questions about the API:

- **Documentation**: This document covers all endpoints and functionality
- **Health Monitoring**: Use `/admin/health` for system status
- **Error Tracking**: Failed jobs are logged and can be monitored via `/admin/jobs`
- **Email Testing**: Use `/admin/test-email` to verify email configuration
- **Comprehensive Testing**: Use `test_email_functionality.py` for full email verification

The API is designed to be self-monitoring with comprehensive error handling, automatic retry mechanisms, and email notifications for robust operation.
