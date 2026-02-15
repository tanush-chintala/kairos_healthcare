#!/usr/bin/env python3
"""Test script for Kairos voice agent and booking functions."""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from services.kairos_booking_tools import (
    book_appointment,
    cancel_appointment,
    find_openings,
    find_patient_appointments_by_phone,
    get_day_view,
    reschedule_appointment,
    upsert_patient,
)
from services.kairos_sheets_client import KairosSheetsClient


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_sheets_connection():
    """Test 1: Verify Google Sheets connection."""
    print_section("TEST 1: Google Sheets Connection")
    try:
        client = KairosSheetsClient()
        print("✅ Successfully connected to Google Sheets")
        print(f"   Spreadsheet ID: {client.spreadsheet.id}")
        print(f"   Appt_Index tab: {client.appt_index_worksheet.title}")
        print(f"   Patients tab: {client.patients_worksheet.title}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False


def test_find_openings():
    """Test 2: Find available openings."""
    print_section("TEST 2: Find Openings")
    try:
        # Search for openings in the next 7 days
        today = datetime.now()
        date_start = today.strftime("%Y-%m-%d")
        date_end = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        print(f"   Searching for openings from {date_start} to {date_end}...")
        openings = find_openings(
            date_start=date_start,
            date_end=date_end,
            limit=5,
        )

        if openings:
            print(f"   ✅ Found {len(openings)} openings:")
            for i, opening in enumerate(openings, 1):
                print(f"      {i}. {opening['row_id']}: {opening['date_local']} {opening['start_time_local']} - {opening['end_time_local']}")
                print(f"         Type: {opening['appt_type']}, Duration: {opening['duration_min']}m")
                print(f"         Provider: {opening['provider_name']}")
        else:
            print("   ⚠️  No openings found in the date range")
        return openings
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_upsert_patient():
    """Test 3: Upsert patient."""
    print_section("TEST 3: Upsert Patient")
    try:
        # Create a test patient
        test_phone = "+15551234567"
        patient_payload = {
            "first_name": "Test",
            "last_name": "Patient",
            "phone_e164": test_phone,
            "email": "test@example.com",
            "dob": "1990-01-01",
            "patient_type": "NEW",
        }

        print(f"   Creating/updating patient with phone: {test_phone}...")
        patient_id = upsert_patient(patient_payload)
        print(f"   ✅ Patient ID: {patient_id}")

        # Try updating the same patient
        print(f"   Updating same patient...")
        patient_payload["email"] = "updated@example.com"
        patient_id2 = upsert_patient(patient_payload)
        print(f"   ✅ Updated patient ID: {patient_id2} (should be same: {patient_id == patient_id2})")

        return patient_id
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_book_appointment(openings, patient_id):
    """Test 4: Book an appointment."""
    print_section("TEST 4: Book Appointment")
    if not openings:
        print("   ⚠️  Skipping - no openings available")
        return None

    try:
        # Use the first opening
        opening = openings[0]
        print(f"   Booking opening: {opening['row_id']}")
        print(f"   Date: {opening['date_local']} {opening['start_time_local']}")

        result = book_appointment(
            opening_row_id=opening["row_id"],
            patient_id=patient_id,
            appt_type="LimitedExam",
            reason_for_visit="Test appointment",
            urgency_level="ROUTINE",
            triage_red_flags="N",
            conversation_id="test-script",
        )

        print(f"   ✅ Appointment booked!")
        print(f"      Appointment ID: {result['appointment_id']}")
        print(f"      Patient ID: {result['patient_id']}")
        print(f"      Date: {result['date_local']} {result['start_time_local']}")
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_find_patient_appointments():
    """Test 5: Find patient appointments."""
    print_section("TEST 5: Find Patient Appointments")
    try:
        test_phone = "+15551234567"
        print(f"   Searching for appointments for phone: {test_phone}...")

        appointments = find_patient_appointments_by_phone(phone_e164=test_phone)

        if appointments:
            print(f"   ✅ Found {len(appointments)} appointment(s):")
            for i, appt in enumerate(appointments, 1):
                print(f"      {i}. Appointment ID: {appt.get('appointment_id')}")
                print(f"         Date: {appt.get('date_local')} {appt.get('start_time_local')}")
                print(f"         Type: {appt.get('appt_type')}")
        else:
            print("   ⚠️  No appointments found")
        return appointments
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_get_day_view():
    """Test 6: Get day view."""
    print_section("TEST 6: Get Day View")
    try:
        # Get tomorrow's date
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"   Getting appointments for: {tomorrow}...")

        day_appointments = get_day_view(tomorrow)

        if day_appointments:
            print(f"   ✅ Found {len(day_appointments)} appointment(s) for {tomorrow}:")
            for appt in day_appointments:
                status = appt.get("status", "UNKNOWN")
                appt_type = appt.get("appt_type", "")
                start_time = appt.get("start_time_local", "")
                print(f"      {status}: {appt_type} at {start_time}")
        else:
            print(f"   ⚠️  No appointments found for {tomorrow}")
        return day_appointments
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_cancel_appointment(appointment_id):
    """Test 7: Cancel appointment."""
    print_section("TEST 7: Cancel Appointment")
    if not appointment_id:
        print("   ⚠️  Skipping - no appointment to cancel")
        return

    try:
        print(f"   Cancelling appointment: {appointment_id}...")
        result = cancel_appointment(
            appointment_id=appointment_id,
            cancel_reason="Test cancellation",
            conversation_id="test-script",
        )
        print(f"   ✅ Appointment cancelled!")
        print(f"      Row ID: {result['row_id']}")
        print(f"      Status: {result['status']}")
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  KAIROS VOICE AGENT TEST SUITE")
    print("=" * 70)

    # Test 1: Connection
    if not test_sheets_connection():
        print("\n❌ Cannot proceed without Google Sheets connection")
        sys.exit(1)

    # Test 2: Find openings
    openings = test_find_openings()

    # Test 3: Upsert patient
    patient_id = test_upsert_patient()
    if not patient_id:
        print("\n⚠️  Cannot proceed without patient ID")
        sys.exit(1)

    # Test 4: Book appointment (only if openings available)
    appointment = None
    if openings:
        appointment = test_book_appointment(openings, patient_id)

    # Test 5: Find patient appointments
    test_find_patient_appointments()

    # Test 6: Get day view
    test_get_day_view()

    # Test 7: Cancel appointment (only if we booked one)
    if appointment:
        test_cancel_appointment(appointment.get("appointment_id"))

    print_section("TEST SUITE COMPLETE")
    print("\n✅ All tests completed!")
    print("\nTo test the voice agent interactively, run:")
    print("  uv run examples/voice_agents/basic_agent.py console")
    print("\nOr to start the agent server for voice calls:")
    print("  uv run examples/voice_agents/basic_agent.py dev")


if __name__ == "__main__":
    main()
