# TrackImmo API Testing Plan

## Project Context

TrackImmo is a real estate SaaS platform with three components:

- **Frontend** (React): Handles user interfaces, signups, payments, and settings
- **Backend** (Python/FastAPI): Handles scraping and data processing
- **Database** (Supabase): Single source of truth for all data

The system helps real estate professionals discover potential investment properties by automating the scraping, processing, and delivery of curated property listings based on their preferences.

## API Implementation Overview

The API implementation consists of:

1. **API Endpoints**:
   - `/api/process-client`: Processes a client to assign new properties
   - `/api/process-retry-queue`: Processes failed jobs that are due for retry

2. **Core Modules**:
   - `client_processor.py`: Contains logic for client processing
   - `email_sender.py`: Handles email notifications
   - `client_processing.py`: API endpoint implementation

3. **Database Integration**:
   - Uses Supabase as database
   - Includes a `processing_jobs` table for tracking retry jobs

4. **Cron Job**:
   - Daily script for automatic client processing
   - Handles month-end logic for clients with impossible dates

## Testing Tasks

### 1. API Endpoints Tests

#### 1.1 `/api/process-client` Endpoint

- [x] Authentication Tests
  - [x] Valid API Key Test (Input: valid key, Expected: 200 OK)
  - [x] Invalid API Key Test (Input: wrong key, Expected: 401 Unauthorized)
  - [x] Missing API Key Test (Input: no key, Expected: 401 Unauthorized)
- [x] Input Validation Tests
  - [x] Valid Client ID Test (Input: valid UUID, Expected: 200 OK)
  - [x] Invalid Client ID Format Test (Input: not a UUID, Expected: 422 Error)
  - [x] Missing Client ID Test (Input: empty JSON, Expected: 422 Error)
- [x] Response Format Tests
  - [x] Successful Response Test (Verify correct JSON structure)
  - [x] Error Response Test (Verify error details are included)

#### 1.2 `/api/process-retry-queue` Endpoint

- [x] Authentication Tests (Same as process-client tests)
- [x] Functionality Tests
  - [x] Processing Pending Jobs Test (Verify jobs are processed)
  - [x] No Pending Jobs Test (Verify empty result when no jobs)

### 2. Client Processor Module Tests

#### 2.1 `process_client_data` Function

- [x] Client Validation Tests
  - [x] Active Client Test (Input: active client, Expected: success)
  - [x] Inactive Client Test (Input: inactive client, Expected: ValueError)
  - [x] Non-existent Client Test (Input: unknown UUID, Expected: ValueError)
- [x] City Enrichment Tests
  - [x] Outdated Cities Test (Verify scraper is called)
  - [x] Up-to-date Cities Test (Verify scraper is not called)
  - [x] Missing INSEE Code Test (Verify code is fetched)
- [x] Property Assignment Tests
  - [x] Standard Assignment Test (Verify correct number assigned)
  - [x] Oldest Properties Priority Test (Verify prioritization with randomization)
  - [x] No Available Properties Test (Verify empty list when none available)
  - [x] Last Updated Field Test (Verify field is updated)

#### 2.2 `assign_properties_to_client` Function

- [x] Property Selection Tests
  - [x] City Filtering Test (Verify only properties from chosen cities)
  - [x] Property Type Filtering Test (Verify only chosen property types)
  - [x] Previously Assigned Exclusion Test (Verify no duplicates)
  - [x] Oldest-First Sorting Test (Verify sorting by sale_date)
  - [x] Month Randomization Test (Verify weighted randomization within months)

### 3. Email Notification Tests

#### 3.1 `send_client_notification` Function

- [x] Email Content Tests
  - [x] Subject Line Test (Verify property count in subject)
  - [x] Client Name Test (Verify name in greeting)
  - [x] Property Info Test (Verify property types mentioned)
- [x] Error Handling Tests
  - [x] Missing Email Test (Verify graceful handling)
  - [x] SMTP Error Test (Verify error is caught and logged)

#### 3.2 `send_error_notification` Function

- [x] Email Content Tests
  - [x] Client ID Test (Verify ID included in email)
  - [x] Error Details Test (Verify error message included)

### 4. Database Operations Tests

#### 4.1 Retry Queue Operations

- [x] `add_to_retry_queue` Tests
  - [x] New Job Creation Test (Verify correct DB record)
- [x] Retry Queue Processing Tests
  - [x] Due Jobs Test (Verify jobs due for retry are processed)
  - [x] Not Due Jobs Test (Verify future jobs are not processed)
  - [x] Exponential Backoff Test (Verify correct delay calculation)
  - [x] Max Retries Test (Verify failure after 3 attempts)

#### 4.2 Client Data Retrieval

- [x] `get_client_by_id` Tests
  - [x] Existing Client Test (Verify returns client data)
  - [x] Non-existent Client Test (Verify returns None)

#### 4.3 City Update Operations

- [x] `update_client_cities` Tests
  - [x] Outdated City Update Test (Verify city is updated)
  - [x] City Fields Update Test (Verify missing fields are populated)

### 5. Cron Job Tests

#### 5.1 Client Identification Logic

- [x] Day Matching Tests
  - [x] Matching Send Day Test (Verify correct clients returned)
  - [x] Non-matching Send Day Test (Verify excluded clients)
- [x] Month-End Edge Case Tests
  - [x] Last Day of Month Test (Verify clients with impossible dates)
  - [x] Multiple Days Beyond Month End Test (Verify correct inclusion)
  - [x] Non-Last Day Test (Verify no inclusion of impossible dates)

#### 5.2 Overall Execution Tests

- [x] Sequential Processing Test (Verify sequential processing)
- [x] Error Handling Test (Verify one client error doesn't stop others)
- [x] Retry Queue Processing Test (Verify retry queue processed after scheduled clients)

### 6. Integration Tests

#### 6.1 End-to-End Process Flow

- [x] Complete Client Processing Test (Verify entire flow works)
- [x] Failed Processing and Retry Test (Verify retry mechanism works)

#### 6.2 Cross-Module Integration

- [x] City Scraper Integration Test (Verify correct integration)
- [x] Property Scraper Integration Test (Verify correct integration)

## Implementation Notes

- All tests should use mocking extensively to isolate components
- Client processing should abort if city update fails
- Property assignment should prioritize oldest properties with some weighted randomization
- Email notifications should use simple text format
- No need for special leap year handling in month-end logic
