"""Update existing booked appointments with date of birth for fake patients."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.sheets_client import SheetsClient

load_dotenv()

# Map of patient names to DOBs
PATIENT_DOBS = {
    ("John", "Doe"): "1985-03-15",
    ("Jane", "Smith"): "1992-07-22",
    ("Michael", "Johnson"): "1978-11-08",
    ("Sarah", "Williams"): "1990-05-30",
    ("David", "Brown"): "1988-12-14",
    # Add any other existing patients
    ("Tanush", "Chintala"): "1995-01-01",  # Example for existing test patient
}


def main():
    """Update existing booked slots with DOBs."""
    print("Updating existing booked appointments with DOBs...")
    print("=" * 60)

    try:
        client = SheetsClient()
        all_rows = client.get_all_rows()

        # Find booked slots without DOB
        booked_slots = [
            (i, row)
            for i, row in enumerate(all_rows, start=2)  # Start at row 2 (after header)
            if row.get("status") == "BOOKED"
            and not row.get("patient_date_of_birth")
            and row.get("patient_first_name")
            and row.get("patient_last_name")
        ]

        if not booked_slots:
            print("✅ No booked slots need updating (all have DOBs or no patient info)")
            return

        print(f"\nFound {len(booked_slots)} booked slots to update")

        updated = 0
        for row_number, slot_data in booked_slots:
            first_name = slot_data.get("patient_first_name", "").strip()
            last_name = slot_data.get("patient_last_name", "").strip()

            # Look up DOB
            dob = PATIENT_DOBS.get((first_name, last_name))
            if dob:
                slot_data["patient_date_of_birth"] = dob
                client.update_row(row_number, slot_data)
                updated += 1
                print(
                    f"  ✅ Updated {slot_data.get('slot_id')}: {first_name} {last_name} -> DOB: {dob}"
                )
            else:
                print(
                    f"  ⚠️  No DOB found for {first_name} {last_name} (slot {slot_data.get('slot_id')})"
                )

        print(f"\n✅ Successfully updated {updated} appointments with DOBs!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
