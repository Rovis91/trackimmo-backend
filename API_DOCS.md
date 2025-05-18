# TrackImmo API Documentation

## Overview

This document describes the TrackImmo backend API, which provides endpoints for processing client data and assigning properties. The API is designed to be used by both the frontend application and the automated cron job for scheduled processing.

## Base URL

``` txt
https://api.trackimmo.com
```

## Authentication

All API endpoints require API key authentication. The API key must be included in the request header:

``` txt
X-API-Key: your_api_key_here
```

The API key should be kept secure and only shared with authorized applications or developers.

## Endpoints

### Health Check

``` txt
GET /api/health
```

Returns the current API status. Used for monitoring and health checks.

**Response:**

```json
{
  "status": "ok"
}
```

### Process Client

``` txt
POST /api/process-client
```

Initiates asynchronous processing of a client's data, including city enrichment, property scraping, and property assignment. Returns immediately with a job ID.

**Request Body:**

```json
{
  "client_id": "uuid-of-client"
}
```

**Response:**

```json
{
  "success": true,
  "job_id": "uuid-of-job",
  "client_id": "uuid-of-client",
  "message": "Processing started"
}
```

**Processing Steps:**

1. Validates client existence and active status
2. Creates a job record in the `processing_jobs` table
3. Returns immediately with the job ID
4. In the background:
   - Updates city data if older than 3 months or missing information
   - Scrapes new properties for the client's selected cities
   - Assigns properties to the client based on their subscription tier
   - Sends notification email to the client
   - Updates the client's `last_updated` timestamp
   - Updates the job status to "completed" or "failed"

### Job Status

``` txt
GET /api/job-status/{job_id}
```

Gets the current status of a client processing job.

**Path Parameters:**

- `job_id`: UUID of the job to check

**Response:**

```json
{
  "job_id": "uuid-of-job",
  "client_id": "uuid-of-client",
  "status": "completed",
  "properties_assigned": 5,
  "error_message": null,
  "created_at": "2023-08-01T14:30:00Z",
  "updated_at": "2023-08-01T14:35:00Z"
}
```

**Status Values:**

- `pending`: Job is waiting to be processed (in retry queue)
- `processing`: Job is currently being processed
- `completed`: Job has successfully completed
- `failed`: Job has failed after all retry attempts

### Process Retry Queue

``` txt
POST /api/process-retry-queue
```

Processes failed jobs in the retry queue. Jobs will be retried with exponential backoff until they succeed or reach maximum retry attempts.

**Response:**

```json
{
  "success": true,
  "processed": 3,
  "failed": 1
}
```

## Error Handling

### Response Format

When an error occurs, the API returns an HTTP error status code along with an error message:

```json
{
  "detail": "Error message describing the issue"
}
```

### Common Error Codes

- **401 Unauthorized**: Invalid or missing API key
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Invalid request data
- **500 Internal Server Error**: Server-side error during processing

### Retry Mechanism

Failed client processing attempts are automatically added to a retry queue. The system will:

1. Retry the job after an initial 1-hour delay
2. Use exponential backoff for subsequent retries (2 hours, 4 hours)
3. After 3 failed attempts, send an error notification to the CTO
4. Mark the job as "failed" in the database

## Database Schema

### processing_jobs Table

Stores information about client processing jobs and their status:

| Column         | Type      | Description                               |
|----------------|-----------|-------------------------------------------|
| job_id         | UUID      | Primary key                               |
| client_id      | UUID      | Reference to clients table                |
| status         | VARCHAR   | 'pending', 'processing', 'completed', 'failed' |
| attempt_count  | INTEGER   | Number of processing attempts             |
| last_attempt   | TIMESTAMP | Time of last processing attempt           |
| next_attempt   | TIMESTAMP | Scheduled time for next attempt           |
| error_message  | TEXT      | Details of the most recent error          |
| created_at     | TIMESTAMP | Record creation time                      |
| updated_at     | TIMESTAMP | Record last update time                   |

## Processing Logic

### Client Processing Workflow

1. **Client Data Retrieval**:
   - Fetch client data from database
   - Verify client is active

2. **City Data Enrichment**:
   - For each selected city:
     - Check if data is older than 3 months
     - If outdated, use CityDataScraper to refresh
     - Update city information in database

3. **Property Scraping**:
   - For each selected city:
     - Use ImmoDataScraper to fetch properties
     - Focus on last 3 months of property data
     - Filter by client's preferred property types

4. **Property Assignment**:
   - Determine number of properties to assign (from client's `addresses_per_report`)
   - Filter properties that haven't been assigned to this client
   - Prioritize older properties by sale date
   - Add randomization within each month for variety
   - Create client-address relationships in database

5. **Notification**:
   - Send email to client about new properties
   - In case of repeated failures, send alert to CTO

### Cron Job Process

The daily cron job runs at midnight every day and:

1. Identifies clients due for processing based on their `send_day` field
2. Handles month-end by including clients with dates beyond the current month
3. Processes each client sequentially
4. Processes the retry queue after all scheduled clients

## Example API Usage

### Process a Client

```bash
curl -X POST https://api.trackimmo.com/api/process-client \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"client_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

### Check Retry Queue

```bash
curl -X POST https://api.trackimmo.com/api/process-retry-queue \
  -H "X-API-Key: your_api_key_here"
```
