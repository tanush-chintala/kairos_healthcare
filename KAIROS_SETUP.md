# Kairos Clinic Setup Guide

This guide explains how to set up your Google Sheet for the Kairos single-doctor clinic system.

## Google Sheets Structure

Your spreadsheet must have **3 tabs**:

### 1. Appt_Index (Source of Truth)
This is where the agent reads and writes all appointment data.

**Required Columns:**
- `row_id` - Unique identifier (e.g., IDX-000001)
- `slot_key` - Format: `date_local|start_time_local|lane` (e.g., "2026-01-27|09:00|Dr-Chair")
- `date_local` - Date in YYYY-MM-DD format
- `start_time_local` - Time in HH:MM format
- `end_time_local` - Time in HH:MM format
- `lane` - Always "Dr-Chair" (single doctor clinic)
- `operatory` - Optional
- `provider_name` - e.g., "Dr. Smith"
- `provider_role` - Always "dentist"
- `appt_type` - e.g., "Cleaning", "Filling", "LimitedExam"
- `duration_min` - Duration in minutes (30, 60, etc.)
- `status` - OPEN, HELD, BOOKED, CANCELLED, NO_SHOW, COMPLETED
- `appointment_id` - Set when BOOKED (e.g., A-000901)
- `patient_id` - Links to Patients tab (blank when OPEN)
- `reason_for_visit` - Reason for appointment
- `urgency_level` - ROUTINE, SOON, URGENT
- `triage_red_flags` - Y or N
- `booked_by` - AI or HUMAN
- `cancel_or_resched_reason` - Reason for cancellation/rescheduling
- `created_at_local` - ISO timestamp
- `last_updated_at_local` - ISO timestamp
- `conversation_id` - Optional conversation ID
- `display_card` - What Master_Schedule shows (auto-generated)

**Display Card Patterns:**
- OPEN: `[OPEN] {appt_type} ({duration_min}m)`
- BOOKED: `[BOOKED] {patient_id} | {appt_type} | {first_initial}. {last_name}`
- CANCELLED: `[CANCELLED] {appt_type} | {patient_id}`
- NO_SHOW: `[NO_SHOW] {appt_type} | {patient_id}`
- COMPLETED: `[DONE] {appt_type} | {patient_id}`

### 2. Patients (Patient Information)
One row per patient.

**Required Columns:**
- `patient_id` - Unique identifier (e.g., P-000003)
- `first_name` - Patient's first name
- `last_name` - Patient's last name
- `phone_e164` - Phone in E.164 format (e.g., +1234567890) - PRIMARY LOOKUP KEY
- `email` - Patient's email
- `dob` - Date of birth in YYYY-MM-DD format
- `patient_type` - NEW or EXISTING
- `consent_to_text` - Y or N
- `preferred_contact_method` - SMS, CALL, or EMAIL
- `insurance_provider` - Optional
- `insurance_member_id` - Optional
- `notes` - Optional notes
- `created_at_local` - ISO timestamp
- `last_updated_at_local` - ISO timestamp

### 3. Master_Schedule (Read-Only Calendar View)
This tab is **derived** from Appt_Index via VLOOKUP on `display_card`.
**The agent MUST NOT write to this tab.**

## Environment Variables

Add to your `.env` file:

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
# OR paste JSON directly:
# GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'

# Sheet Names (optional, defaults shown)
PATIENTS_SHEET_NAME=Patients
APPT_INDEX_SHEET_NAME=Appt_Index
```

## Key Concepts

### Slot Key Format
The `slot_key` uniquely identifies a time slot:
- Format: `date_local|start_time_local|lane`
- Example: `2026-01-27|09:00|Dr-Chair`
- Always uses "Dr-Chair" as the lane

### Cancellation Policy (Option 1)
When an appointment is cancelled:
1. Status changes from BOOKED → OPEN
2. Patient fields are cleared: `appointment_id`, `patient_id`, `reason_for_visit`, etc.
3. `display_card` is regenerated for OPEN status
4. The slot becomes available again

### Patient Lookup
- Primary key: `phone_e164` (E.164 format)
- Patients are upserted: found by phone, created if new, updated if existing
- Patient IDs are auto-generated: P-000001, P-000002, etc.

### Verification Requirements
For existing patients performing sensitive actions (cancel/reschedule):
- **Level 2**: Requires (phone + DOB) OR (phone + email)
- If verification fails 3 times, escalates to human

## Testing

1. Create a Google Sheet with the 3 tabs
2. Add some OPEN slots to Appt_Index
3. Test `find_openings` to see available slots
4. Test `upsert_patient` to create/update patients
5. Test `book_appointment` to book a slot
6. Test `cancel_appointment` to cancel (should flip back to OPEN)
7. Test `reschedule_appointment` to reschedule

## Notes

- Master_Schedule is read-only - never write to it
- All mutations happen in Appt_Index
- Single lane: only "Dr-Chair" is schedulable
- No overlapping bookings allowed for same start_time_local in Dr-Chair
