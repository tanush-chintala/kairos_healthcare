# Kairos Voice Agent Testing Guide

This guide explains how to test your Kairos voice agent.

## Quick Test Scripts

### 0. Add Test Data to Spreadsheet (Do This First!)

Before testing, add comprehensive test data to your Google Sheet:

```bash
uv run python scripts/add_test_data.py
```

This script will:
- ✅ Add 8 test patients to the Patients tab
- ✅ Add ~50-70 appointment slots to the Appt_Index tab (14 days, Mon-Fri)
- ✅ Mix of OPEN, BOOKED, and HELD statuses
- ✅ Various appointment types (Cleaning, Exam, Filling, etc.)

**Note:** This will add real data to your spreadsheet. You can run it multiple times - it uses `upsert` for patients to avoid duplicates.

### 1. Test Booking Functions (Recommended First)

Test all the booking functions without running the full agent:

```bash
uv run python test_kairos_agent.py
```

This script will:
- ✅ Test Google Sheets connection
- ✅ Find available openings
- ✅ Create/update a test patient
- ✅ Book an appointment
- ✅ Find patient appointments
- ✅ Get day view
- ✅ Cancel an appointment

**Note:** This will create real test data in your Google Sheet. You may want to clean it up afterward.

### 2. Test Voice Agent Interactively (Console Mode)

Test the agent with text input (simulates voice conversation):

```bash
uv run python test_voice_agent_interactive.py
```

Or directly:

```bash
uv run examples/voice_agents/basic_agent.py console
```

In console mode, you can:
- Type messages as if you're speaking to the agent
- Test the agent's responses and tool calls
- See what the agent would say in a real conversation

**Example conversation:**
```
You: I need to book an appointment
Agent: I'd be happy to help you book an appointment. What type of appointment do you need?
You: A cleaning
Agent: When would you like to schedule this cleaning?
...
```

### 3. Test Voice Agent Server (Full Voice Mode)

Start the agent server for actual voice calls:

```bash
uv run examples/voice_agents/basic_agent.py dev
```

This starts the agent server and waits for a client to connect. You'll need:
- A LiveKit client application
- Or use LiveKit's web interface
- Or connect via phone/SIP

## Testing Checklist

Before testing with real patients, verify:

- [ ] Google Sheets connection works
- [ ] Service account has access to the spreadsheet
- [ ] Appt_Index tab has correct columns
- [ ] Patients tab has correct columns
- [ ] Can find openings
- [ ] Can create/update patients
- [ ] Can book appointments
- [ ] Can find patient appointments
- [ ] Can cancel appointments
- [ ] Agent responds correctly in console mode

## Common Issues

### "ModuleNotFoundError: No module named 'gspread'"
```bash
uv pip install -r requirements-booking.txt
```

### "Permission denied" or "Access denied"
- Make sure the service account email is shared with the spreadsheet
- Service account email: `dental-booking-agent@kairos-healthcare.iam.gserviceaccount.com`
- Give it "Editor" access

### "Spreadsheet not found"
- Check `GOOGLE_SHEETS_SPREADSHEET_ID` in `.env`
- Should be: `1O6xfGcsG9YiFlqz8EEKgNd3ZjwI5uXOJt5QX0B41BxM`

### "No openings found"
- Add some OPEN slots to the Appt_Index tab
- Make sure `status` column is set to "OPEN"
- Make sure `lane` is "Dr-Chair"

## Sample Test Data

Instead of manually adding test data, use the automated script:

```bash
uv run python scripts/add_test_data.py
```

This will add:
- 8 test patients with complete information
- ~50-70 appointment slots across 14 business days
- Mix of OPEN (50%), BOOKED (35%), and HELD (15%) statuses
- Various appointment types: Cleaning, LimitedExam, Filling, RootCanal, Extraction, Consultation, Crown, Whitening

Or manually add to Appt_Index:

| row_id | slot_key | date_local | start_time_local | end_time_local | lane | status | appt_type | duration_min |
|--------|----------|------------|------------------|----------------|------|--------|-----------|--------------|
| IDX-0001 | 2026-02-10\|09:00\|Dr-Chair | 2026-02-10 | 09:00 | 09:30 | Dr-Chair | OPEN | Cleaning | 30 |

## Next Steps

After testing:
1. Clean up test data from your spreadsheet
2. Add real appointment slots
3. Test with actual phone calls
4. Monitor agent behavior and adjust instructions if needed
