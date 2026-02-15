# Dispatch Layer and Database Services

This directory contains the dispatch layer and database services for multi-tenant clinic configurations.

## Components

### `database.py`
SQLite database operations for clinic configurations. Provides CRUD functions for managing clinic data.

### `config.py`
Configuration management for environment variables and service settings.

### `webhook_service.py`
FastAPI webhook service that receives incoming calls, looks up clinic configurations, and dispatches LiveKit agent jobs with metadata.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements-webhook.txt
   ```

2. **Initialize database:**
   ```bash
   python scripts/init_db.py
   ```

3. **Set environment variables:**
   ```bash
   export LIVEKIT_URL="wss://your-project.livekit.cloud"
   export LIVEKIT_API_KEY="your_api_key"
   export LIVEKIT_API_SECRET="your_api_secret"
   export AGENT_NAME="dental-assistant"
   export DATABASE_PATH="./data/clinic_configs.db"
   ```

4. **Run webhook service:**
   ```bash
   python -m services.webhook_service
   # Or with uvicorn directly:
   uvicorn services.webhook_service:app --host 0.0.0.0 --port 8000
   ```

## Usage

### Adding a Clinic

```python
from services.database import get_db

db = get_db()
db.create_clinic_config(
    clinic_id="sunshine-clinic",
    office_name="Sunshine Dental Clinic",
    greeting="Welcome to Sunshine Dental Clinic. How may I help you today?",
    phone_number="+1-555-SUNSHINE",
)
```

### Webhook Endpoint

POST `/webhook/incoming-call`

Request body:
```json
{
  "to_number": "+1-555-SUNSHINE",
  "from_number": "+1-555-123-4567",
  "clinic_id": "sunshine-clinic"  // optional, will lookup by phone if not provided
}
```

Response:
```json
{
  "dispatch_id": "dispatch_123",
  "room_name": "clinic-sunshine-clinic-abc123",
  "clinic_id": "sunshine-clinic",
  "office_name": "Sunshine Dental Clinic"
}
```

### Testing

```bash
# Test webhook endpoint
python scripts/test_dispatch.py

# Test with custom URL
python scripts/test_dispatch.py --url http://localhost:8000
```

## Architecture

```
Phone Call → FastAPI Webhook → SQLite DB Lookup → LiveKit Dispatch API → Agent (reads metadata)
```

The agent reads metadata from `ctx.job.metadata` and uses it to personalize greetings and behavior per clinic.
