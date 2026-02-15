#!/usr/bin/env python3
"""Populate Master_Schedule from Appt_Index."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.kairos_sheets_client import KairosSheetsClient

load_dotenv()


def main():
    """Populate Master_Schedule from Appt_Index."""
    print("=" * 70)
    print("  POPULATING MASTER_SCHEDULE FROM APPT_INDEX")
    print("=" * 70)
    
    try:
        client = KairosSheetsClient()
        print("\n✅ Connected to Google Sheets")
        
        # Check Appt_Index first
        all_appts = client.get_all_appt_rows()
        print(f"\nFound {len(all_appts)} appointments in Appt_Index")
        
        if not all_appts:
            print("  ⚠️  No appointments found in Appt_Index")
            print("  💡 Add some appointments first using: uv run python scripts/add_test_data.py")
            return
        
        # Show sample appointments
        print("\nSample appointments:")
        for appt in all_appts[:3]:
            print(f"  - {appt.get('date_local')} {appt.get('start_time_local')}: {appt.get('status')} - {appt.get('appt_type')}")
        
        # Populate Master_Schedule
        print("\n" + "-" * 70)
        print("Populating Master_Schedule...")
        print("-" * 70)
        
        client.populate_master_schedule_from_appt_index()
        
        print("✅ Successfully populated Master_Schedule!")
        print(f"   Added {len(all_appts)} entries to Master_Schedule")
        
        # Verify
        master_values = client.master_schedule_worksheet.get_all_values()
        print(f"\n✅ Master_Schedule now has {len(master_values)} rows (including header)")
        
        if len(master_values) > 1:
            print("\nFirst few entries in Master_Schedule:")
            for i, row in enumerate(master_values[1:4], 1):
                date = row[0] if len(row) > 0 else "N/A"
                time = row[1] if len(row) > 1 else "N/A"
                status = row[7] if len(row) > 7 else "N/A"
                display = row[10] if len(row) > 10 else "N/A"
                print(f"  {i}. {date} {time} - {status} - {display}")
        
        print("\n" + "=" * 70)
        print("✅ DONE! Master_Schedule should now be visible in your spreadsheet.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
