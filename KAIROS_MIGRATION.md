# Kairos Clinic Migration Guide

This document describes the migration from the generic booking system to the Kairos-specific single-doctor clinic system.

## New Architecture

### Google Sheets Structure

**3 Tabs:**
1. **Appt_Index** - Source of truth for all appointments and availability
2. **Patients** - Patient information only
3. **Master_Schedule** - Read-only calendar view (derived from Appt_Index via VLOOKUP)

### Key Changes

1. **Single Lane**: Only "Dr-Chair" is schedulable
2. **Patient Management**: Separate Patients tab with upsert logic
3. **Slot Key Format**: `date_local|start_time_local|lane`
4. **Cancellation Policy**: Option 1 - Flip back to OPEN (clear patient fields)
5. **Verification**: For existing patients, requires (phone + DOB) OR (phone + email)

## New Functions

### `find_openings(date_start, date_end, appt_type=None, duration_min=None, limit=5)`
- Finds OPEN slots in Dr-Chair lane
- Filters by date range, appt_type, duration_min
- Returns: row_id, slot_key, date, start/end, appt_type, duration_min

### `upsert_patient(patient_payload) -> patient_id`
- Finds patient by phone_e164
- Creates if missing, updates if present
- Returns patient_id

### `book_appointment(opening_row_id, patient_id, appt_type, reason_for_visit, urgency_level, triage_red_flags, conversation_id=None)`
- Books an OPEN slot
- Generates appointment_id (A-xxxxxx)
- Updates display_card

### `cancel_appointment(appointment_id OR row_id, cancel_reason, conversation_id=None)`
- Option 1: Flips status back to OPEN
- Clears patient fields and appointment_id

### `reschedule_appointment(old_identifier, new_opening_row_id, cancel_reason, conversation_id=None)`
- Cancels old appointment
- Books new slot with same patient_id

### `get_day_view(date_local)`
- Returns all appointments for a day, sorted by time

### `find_patient_appointments_by_phone(phone_e164, date=None)`
- Finds appointments by patient phone
- Optional date filter

## Environment Variables

Add to `.env`:
```bash
PATIENTS_SHEET_NAME=Patients
APPT_INDEX_SHEET_NAME=Appt_Index
```

## Migration Steps

1. ✅ Created `services/kairos_sheets_client.py` - New client for 3-tab structure
2. ✅ Created `services/kairos_booking_tools.py` - New booking functions
3. ⏳ Update agent to use new functions
4. ⏳ Update verification to use (phone + DOB) OR (phone + email)
5. ⏳ Test with new Google Sheet structure

## Testing

Before deploying:
1. Set up Google Sheet with 3 tabs (Appt_Index, Patients, Master_Schedule)
2. Add some OPEN slots to Appt_Index
3. Test find_openings
4. Test upsert_patient (create and update)
5. Test book_appointment
6. Test cancel_appointment (verify it flips to OPEN)
7. Test reschedule_appointment
8. Test verification with phone + DOB
