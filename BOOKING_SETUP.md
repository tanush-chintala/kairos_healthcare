# Dental Appointment Booking System Setup

This guide explains how to set up the Google Sheets-based appointment booking system for the LiveKit dental assistant agent.

## Overview

The booking system allows the agent to:
- Find available appointment slots
- Book appointments
- Cancel appointments
- Reschedule appointments

All data is stored in a Google Sheet tab called "Slots".

## Prerequisites

1. **Google Cloud Project** with Sheets API enabled
2. **Service Account** with access to your Google Sheet
3. **Google Sheet** with the "Slots" tab

## Setup Steps

### 1. Create Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin** → **Service Accounts**
5. Click **Create Service Account**
6. Give it a name (e.g., "dental-booking-agent")
7. Grant it **Editor** role (or create a custom role with Sheets read/write)
8. Click **Done**
9. Click on the service account → **Keys** → **Add Key** → **Create new key**
10. Choose **JSON** format
11. Download the JSON file

### 2. Create Google Sheet

1. Create a new Google Sheet
2. Name the first tab "Slots" (exactly)
3. Add these column headers in row 1 (in this exact order):

```
slot_id
clinic_id
location_name
operatory
provider_name
provider_role
appt_type
planned_duration_min
start_datetime_local
end_datetime_local
status
patient_type
patient_first_name
patient_last_name
patient_phone
patient_email
reason_for_visit
urgency_level
eligibility_status
confirmation_status
cancel_or_resched_reason
created_by
last_updated_at
conversation_id
```

4. Share the sheet with the service account email (from step 1)
   - Give it **Editor** permissions

### 3. Get Sheet ID

1. Open your Google Sheet
2. Look at the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`
3. Copy the `SHEET_ID_HERE` part

### 4. Set Environment Variables

Add these to your `.env` file:

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_sheet_id_here
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
# OR paste the JSON content directly:
# GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
SLOTS_SHEET_NAME=Slots
```

**Option A: JSON File Path**
```bash
GOOGLE_SERVICE_ACCOUNT_JSON=/Users/yourname/path/to/service-account.json
```

**Option B: JSON Content (Recommended for production)**
```bash
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"my-project",...}'
```

### 5. Install Dependencies

```bash
uv pip install -r requirements-booking.txt
```

Or install manually:
```bash
uv pip install gspread google-auth google-auth-oauthlib google-auth-httplib2
```

## Sheet Schema

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `slot_id` | string | Unique identifier for the slot |
| `status` | string | Must be "OPEN", "BOOKED", or "CANCELLED" |
| `start_datetime_local` | string | ISO format: "2024-01-15T10:00:00" |
| `end_datetime_local` | string | ISO format: "2024-01-15T10:30:00" |
| `appt_type` | string | e.g., "cleaning", "exam", "consultation" |
| `provider_name` | string | Doctor/dentist name |

### Patient Fields (filled when booking)

| Column | Description |
|--------|-------------|
| `patient_first_name` | Patient's first name |
| `patient_last_name` | Patient's last name |
| `patient_phone` | Phone number |
| `patient_email` | Email address |
| `patient_type` | "NEW" or "EXISTING" |
| `reason_for_visit` | Why they're booking |
| `urgency_level` | "ROUTINE", "URGENT", or "EMERGENCY" |

### System Fields (auto-filled)

| Column | Description |
|--------|-------------|
| `eligibility_status` | Set to "UNVERIFIED" when booking |
| `confirmation_status` | Set to "UNCONFIRMED" when booking |
| `created_by` | Set to "AI" when booking |
| `last_updated_at` | Timestamp of last update |
| `cancel_or_resched_reason` | Reason when cancelling/rescheduling |

## Example Data

Here's an example row for an OPEN slot:

```
slot_id: SLOT-001
clinic_id: CLINIC-001
location_name: Main Office
operatory: Operatory 1
provider_name: Dr. Smith
provider_role: Dentist
appt_type: cleaning
planned_duration_min: 30
start_datetime_local: 2024-01-15T10:00:00
end_datetime_local: 2024-01-15T10:30:00
status: OPEN
patient_type: (empty)
patient_first_name: (empty)
patient_last_name: (empty)
patient_phone: (empty)
patient_email: (empty)
reason_for_visit: (empty)
urgency_level: (empty)
eligibility_status: (empty)
confirmation_status: (empty)
cancel_or_resched_reason: (empty)
created_by: (empty)
last_updated_at: (empty)
conversation_id: (empty)
```

## Testing

### Test Locally

1. Make sure your `.env` file has the Google Sheets credentials
2. Add some test rows to your "Slots" sheet with `status="OPEN"`
3. Run the agent:
   ```bash
   uv run examples/voice_agents/basic_agent.py console
   ```
4. Try saying:
   - "I'd like to book an appointment"
   - "Find available slots for a cleaning"
   - "Show me appointments on January 15th"

### Verify Tools Work

The agent has these tools available:
- `find_open_slots` - Find available appointments
- `book_slot` - Book an appointment
- `cancel_slot` - Cancel an appointment
- `reschedule_slot` - Reschedule an appointment

## Troubleshooting

### "GOOGLE_SHEETS_SPREADSHEET_ID not set"
- Make sure `.env` file has `GOOGLE_SHEETS_SPREADSHEET_ID`

### "GOOGLE_SERVICE_ACCOUNT_JSON not set"
- Make sure `.env` file has `GOOGLE_SERVICE_ACCOUNT_JSON`
- If using file path, make sure the file exists
- If using JSON content, make sure it's valid JSON

### "Permission denied" or "Access denied"
- Make sure the service account email has **Editor** access to the sheet
- Check that the service account JSON is correct

### "Sheet 'Slots' not found"
- Make sure the tab is named exactly "Slots" (case-sensitive)
- Or set `SLOTS_SHEET_NAME` in `.env` to match your tab name

### "Slot not found" or "Slot is not OPEN"
- Make sure you're using the correct `slot_id`
- Check that the slot's `status` column is "OPEN" (not "open" or "Open")

## Code Structure

- `services/sheets_client.py` - Google Sheets client wrapper
- `services/booking_tools.py` - Booking functions (find, book, cancel, reschedule)
- `examples/voice_agents/basic_agent.py` - LiveKit agent with booking tools integrated

## Notes

- The system automatically handles race conditions by re-reading rows before writing
- Only slots with `status="OPEN"` can be booked
- Only slots with `status="BOOKED"` can be cancelled
- Rescheduling books the new slot first, then cancels the old one
- All timestamps use ISO format: `YYYY-MM-DDTHH:MM:SS`
