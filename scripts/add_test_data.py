#!/usr/bin/env python3
"""Add comprehensive test data to Kairos Google Sheets (Appt_Index and Patients tabs)."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.kairos_sheets_client import KairosSheetsClient

load_dotenv()


def generate_test_patients() -> list[dict]:
    """Generate test patient data."""
    patients = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "phone_e164": "+15551234567",
            "email": "john.doe@example.com",
            "dob": "1985-03-15",
            "patient_type": "EXISTING",
            "consent_to_text": "Y",
            "preferred_contact_method": "SMS",
            "insurance_provider": "Blue Cross",
            "insurance_member_id": "BC123456789",
        },
        {
            "first_name": "Jane",
            "last_name": "Smith",
            "phone_e164": "+15551234568",
            "email": "jane.smith@example.com",
            "dob": "1992-07-22",
            "patient_type": "NEW",
            "consent_to_text": "Y",
            "preferred_contact_method": "SMS",
            "insurance_provider": "Aetna",
            "insurance_member_id": "AET987654321",
        },
        {
            "first_name": "Michael",
            "last_name": "Johnson",
            "phone_e164": "+15551234569",
            "email": "michael.j@example.com",
            "dob": "1978-11-08",
            "patient_type": "EXISTING",
            "consent_to_text": "N",
            "preferred_contact_method": "CALL",
            "insurance_provider": "Cigna",
            "insurance_member_id": "CIG456789123",
        },
        {
            "first_name": "Sarah",
            "last_name": "Williams",
            "phone_e164": "+15551234570",
            "email": "sarah.w@example.com",
            "dob": "1990-05-30",
            "patient_type": "EXISTING",
            "consent_to_text": "Y",
            "preferred_contact_method": "EMAIL",
            "insurance_provider": "United Healthcare",
            "insurance_member_id": "UHC789123456",
        },
        {
            "first_name": "David",
            "last_name": "Brown",
            "phone_e164": "+15551234571",
            "email": "david.brown@example.com",
            "dob": "1988-12-14",
            "patient_type": "NEW",
            "consent_to_text": "Y",
            "preferred_contact_method": "SMS",
            "insurance_provider": "Humana",
            "insurance_member_id": "HUM321654987",
        },
        {
            "first_name": "Emily",
            "last_name": "Davis",
            "phone_e164": "+15551234572",
            "email": "emily.davis@example.com",
            "dob": "1995-02-18",
            "patient_type": "EXISTING",
            "consent_to_text": "Y",
            "preferred_contact_method": "SMS",
            "insurance_provider": "Medicaid",
            "insurance_member_id": "MED147258369",
        },
        {
            "first_name": "Robert",
            "last_name": "Miller",
            "phone_e164": "+15551234573",
            "email": "robert.m@example.com",
            "dob": "1982-09-25",
            "patient_type": "EXISTING",
            "consent_to_text": "N",
            "preferred_contact_method": "CALL",
            "insurance_provider": "Blue Shield",
            "insurance_member_id": "BS258369147",
        },
        {
            "first_name": "Lisa",
            "last_name": "Wilson",
            "phone_e164": "+15551234574",
            "email": "lisa.wilson@example.com",
            "dob": "1991-06-12",
            "patient_type": "NEW",
            "consent_to_text": "Y",
            "preferred_contact_method": "SMS",
            "insurance_provider": "Kaiser",
            "insurance_member_id": "KAI369147258",
        },
    ]
    return patients


def generate_test_appointments(
    start_date: datetime, provider_name: str = "Dr. Smith"
) -> list[dict]:
    """Generate 3-4 test appointment slots for a single day."""
    appointments = []
    
    appt_types = ["Cleaning", "LimitedExam", "Filling", "Consultation"]
    duration_map = {
        "Cleaning": 30,
        "LimitedExam": 30,
        "Filling": 60,
        "Consultation": 60,
    }
    
    # Time slots for one day: 9:00, 10:30, 2:00, 3:30
    time_slots = ["09:00", "10:30", "14:00", "15:30"]
    
    date_str = start_date.strftime("%Y-%m-%d")
    row_id_counter = 1
    
    # Generate 3-4 slots
    for i, start_time in enumerate(time_slots[:4]):  # Just 4 slots max
        appt_type = appt_types[i % len(appt_types)]
        duration = duration_map[appt_type]
        
        # Parse start time and calculate end time
        start_hour, start_min = map(int, start_time.split(":"))
        start_datetime = start_date.replace(hour=start_hour, minute=start_min)
        end_datetime = start_datetime + timedelta(minutes=duration)
        end_time = end_datetime.strftime("%H:%M")
        
        # Create slot_key
        slot_key = f"{date_str}|{start_time}|Dr-Chair"
        
        # Generate row_id
        row_id = f"IDX-{row_id_counter:04d}"
        
        # Mix of OPEN and BOOKED (simple)
        if i < 2:  # First 2 are OPEN
            status = "OPEN"
            appointment_id = ""
            patient_id = ""
            reason_for_visit = ""
            urgency_level = ""
            triage_red_flags = ""
            booked_by = ""
            display_card = f"[OPEN] {appt_type} ({duration}m)"
        else:  # Last 2 are BOOKED
            status = "BOOKED"
            appointment_id = f"A-{900000 + row_id_counter:06d}"
            patient_id = f"P-{i:04d}"  # Simple patient IDs
            reason_for_visit = "Routine checkup" if appt_type == "Cleaning" else "Consultation"
            urgency_level = "ROUTINE"
            triage_red_flags = "N"
            booked_by = "AI"
            display_card = f"[BOOKED] {patient_id} | {appt_type}"
        
        appointment = {
            "row_id": row_id,
            "slot_key": slot_key,
            "date_local": date_str,
            "start_time_local": start_time,
            "end_time_local": end_time,
            "lane": "Dr-Chair",
            "operatory": "Operatory 1",
            "provider_name": provider_name,
            "provider_role": "dentist",
            "appt_type": appt_type,
            "duration_min": str(duration),
            "status": status,
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "reason_for_visit": reason_for_visit,
            "urgency_level": urgency_level,
            "triage_red_flags": triage_red_flags,
            "booked_by": booked_by,
            "cancel_or_resched_reason": "",
            "created_at_local": datetime.now().isoformat(),
            "last_updated_at_local": datetime.now().isoformat(),
            "conversation_id": "",
            "display_card": display_card,
        }
        
        appointments.append(appointment)
        row_id_counter += 1
    
    return appointments


def main():
    """Add test data to both Patients and Appt_Index tabs."""
    print("=" * 70)
    print("  ADDING TEST DATA TO KAIROS SPREADSHEET")
    print("=" * 70)
    
    try:
        client = KairosSheetsClient()
        print("\n✅ Connected to Google Sheets")
        
        # Add test patients
        print("\n" + "-" * 70)
        print("Adding test patients to Patients tab...")
        print("-" * 70)
        
        patients = generate_test_patients()
        print(f"Generated {len(patients)} test patients")
        
        patients_added = 0
        for patient in patients:
            try:
                # Use upsert to avoid duplicates
                patient_id = client.upsert_patient_row(patient)
                patients_added += 1
                print(f"  ✅ {patient_id}: {patient['first_name']} {patient['last_name']} ({patient['phone_e164']})")
            except Exception as e:
                print(f"  ⚠️  Error adding {patient['first_name']} {patient['last_name']}: {e}")
        
        print(f"\n✅ Successfully added/updated {patients_added} patients")
        
        # Add test appointments
        print("\n" + "-" * 70)
        print("Adding test appointments to Appt_Index tab...")
        print("-" * 70)
        
        # Start from tomorrow
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        appointments = generate_test_appointments(start_date, provider_name="Dr. Smith")
        
        print(f"Generated {len(appointments)} test appointment slots")
        print(f"Date: {start_date.strftime('%Y-%m-%d')} ({start_date.strftime('%A')})")
        
        # Count statuses
        status_counts = {}
        for appt in appointments:
            status = appt["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\nStatus breakdown:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        print(f"\nSlots:")
        for appt in appointments:
            print(f"  {appt['start_time_local']} - {appt['end_time_local']}: {appt['status']} - {appt['appt_type']}")
        
        appointments_added = 0
        for appointment in appointments:
            try:
                client.append_appt_row(appointment)
                appointments_added += 1
            except Exception as e:
                print(f"  ⚠️  Error adding {appointment['row_id']}: {e}")
        
        print(f"\n✅ Successfully added {appointments_added} appointment slots")
        
        print("\n" + "=" * 70)
        print("  TEST DATA ADDITION COMPLETE")
        print("=" * 70)
        print(f"\n✅ Added {patients_added} patients and {appointments_added} appointment slots")
        print("\nYou can now test the agent with this data!")
        print("\nTo test, run:")
        print("  uv run python test_kairos_agent.py")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
