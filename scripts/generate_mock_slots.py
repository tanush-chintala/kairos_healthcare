"""Generate mock appointment slots for testing the dental booking agent."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.sheets_client import SheetsClient

load_dotenv()


def get_next_weekday(weekday: int) -> datetime:
    """Get the next occurrence of a weekday (0=Monday, 6=Sunday)."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def generate_mock_slots() -> list[dict]:
    """Generate mock appointment slots for Monday-Friday of next week."""
    slots = []
    
    # Providers and appointment types
    providers = [
        ("Dr. Smith", "Dentist"),
        ("Dr. Johnson", "Dentist"),
        ("Dr. Williams", "Orthodontist"),
        ("Dr. Brown", "Dentist"),
    ]
    
    appt_types = ["cleaning", "exam", "consultation", "filling", "root_canal", "extraction"]
    
    # Fake patients for booking some slots
    fake_patients = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "555-0101",
            "email": "john.doe@email.com",
            "type": "EXISTING",
            "date_of_birth": "1985-03-15",
        },
        {
            "first_name": "Jane",
            "last_name": "Smith",
            "phone": "555-0102",
            "email": "jane.smith@email.com",
            "type": "NEW",
            "date_of_birth": "1992-07-22",
        },
        {
            "first_name": "Michael",
            "last_name": "Johnson",
            "phone": "555-0103",
            "email": "michael.j@email.com",
            "type": "EXISTING",
            "date_of_birth": "1978-11-08",
        },
        {
            "first_name": "Sarah",
            "last_name": "Williams",
            "phone": "555-0104",
            "email": "sarah.w@email.com",
            "type": "EXISTING",
            "date_of_birth": "1990-05-30",
        },
        {
            "first_name": "David",
            "last_name": "Brown",
            "phone": "555-0105",
            "email": "david.brown@email.com",
            "type": "NEW",
            "date_of_birth": "1988-12-14",
        },
    ]
    
    reasons_for_visit = [
        "Routine cleaning",
        "Annual checkup",
        "Tooth pain",
        "Follow-up consultation",
        "Cavity filling",
        "Teeth whitening consultation",
    ]
    
    # Time slots (9 AM to 5 PM, 30-minute intervals)
    time_slots = []
    for hour in range(9, 17):
        for minute in [0, 30]:
            time_slots.append(f"{hour:02d}:{minute:02d}:00")
    
    slot_id_counter = 1
    patient_idx = 0
    
    # Generate slots for Monday (0) through Friday (4)
    for weekday in range(5):  # Monday to Friday
        date = get_next_weekday(weekday)
        date_str = date.strftime("%Y-%m-%d")
        
        # Generate 2-3 slots per day
        slots_per_day = 2 if weekday < 3 else 3  # More slots on Wed-Fri
        
        for i in range(slots_per_day):
            # Pick a random time slot (using index to vary)
            time_idx = (weekday * 3 + i) % len(time_slots)
            time_str = time_slots[time_idx]
            
            # Pick provider and appointment type
            provider_idx = (weekday + i) % len(providers)
            provider_name, provider_role = providers[provider_idx]
            appt_type = appt_types[(weekday * 2 + i) % len(appt_types)]
            
            # Duration based on appointment type
            duration_map = {
                "cleaning": 30,
                "exam": 45,
                "consultation": 60,
                "filling": 60,
                "root_canal": 90,
                "extraction": 45,
            }
            duration = duration_map.get(appt_type, 30)
            
            start_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            end_datetime = start_datetime + timedelta(minutes=duration)
            
            # Book approximately 40% of slots (every 2-3 slots)
            is_booked = (slot_id_counter % 3 == 0) or (slot_id_counter % 5 == 0)
            
            if is_booked and patient_idx < len(fake_patients):
                patient = fake_patients[patient_idx]
                patient_idx += 1
                status = "BOOKED"
                reason = reasons_for_visit[(slot_id_counter - 1) % len(reasons_for_visit)]
            else:
                patient = {
                    "first_name": "",
                    "last_name": "",
                    "phone": "",
                    "email": "",
                    "type": "",
                    "date_of_birth": "",
                }
                status = "OPEN"
                reason = ""
            
            slot = {
                "slot_id": f"SLOT-{slot_id_counter:04d}",
                "clinic_id": "test-clinic",
                "location_name": "Main Office",
                "operatory": f"Op {(i % 3) + 1}",
                "provider_name": provider_name,
                "provider_role": provider_role,
                "appt_type": appt_type,
                "planned_duration_min": str(duration),
                "start_datetime_local": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "end_datetime_local": end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "patient_type": patient["type"],
                "patient_first_name": patient["first_name"],
                "patient_last_name": patient["last_name"],
                "patient_phone": patient["phone"],
                "patient_email": patient["email"],
                "patient_date_of_birth": patient.get("date_of_birth", ""),
                "reason_for_visit": reason,
                "urgency_level": "ROUTINE" if status == "BOOKED" else "",
                "eligibility_status": "VERIFIED" if status == "BOOKED" else "",
                "confirmation_status": "CONFIRMED" if status == "BOOKED" else "",
                "cancel_or_resched_reason": "",
                "created_by": "mock_generator",
                "last_updated_at": datetime.now().isoformat(),
                "conversation_id": "",
            }
            
            slots.append(slot)
            slot_id_counter += 1
    
    return slots


def main():
    """Generate and add mock slots to the Google Sheet."""
    print("Generating mock appointment slots...")
    print("=" * 60)
    
    try:
        client = SheetsClient()
        slots = generate_mock_slots()
        
        print(f"\nGenerated {len(slots)} mock slots")
        print("\nSample slots:")
        for slot in slots[:5]:
            print(
                f"  {slot['slot_id']}: {slot['appt_type']} with {slot['provider_name']} "
                f"on {slot['start_datetime_local']}"
            )
        
        print(f"\nAdding {len(slots)} slots to Google Sheet...")
        
        # Add slots one by one
        added = 0
        for slot in slots:
            try:
                client.append_row(slot)
                added += 1
            except Exception as e:
                print(f"  ⚠️  Error adding {slot['slot_id']}: {e}")
        
        print(f"\n✅ Successfully added {added} slots to the sheet!")
        print(f"\nSlots are for: {get_next_weekday(0).strftime('%A, %B %d')} through {get_next_weekday(4).strftime('%A, %B %d')}")
        print("\nYou can now test the agent with these slots!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
