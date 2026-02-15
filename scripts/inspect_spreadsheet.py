#!/usr/bin/env python3
"""Inspect the Kairos spreadsheet to diagnose Master_Schedule issues."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.kairos_sheets_client import KairosSheetsClient

load_dotenv()


def inspect_spreadsheet():
    """Inspect the spreadsheet structure and data."""
    print("=" * 70)
    print("  SPREADSHEET INSPECTION")
    print("=" * 70)
    
    try:
        client = KairosSheetsClient()
        print("\n✅ Connected to Google Sheets")
        print(f"   Spreadsheet ID: {client.spreadsheet.id}")
        print(f"   Spreadsheet Title: {client.spreadsheet.title}")
        
        # Check Appt_Index
        print("\n" + "-" * 70)
        print("APPT_INDEX TAB")
        print("-" * 70)
        
        all_appts = client.get_all_appt_rows()
        print(f"Total rows in Appt_Index: {len(all_appts)}")
        
        if all_appts:
            print("\nFirst few appointments:")
            for i, appt in enumerate(all_appts[:5], 1):
                print(f"\n  {i}. Row ID: {appt.get('row_id', 'N/A')}")
                print(f"     Date: {appt.get('date_local', 'N/A')}")
                print(f"     Time: {appt.get('start_time_local', 'N/A')} - {appt.get('end_time_local', 'N/A')}")
                print(f"     Status: {appt.get('status', 'N/A')}")
                print(f"     Type: {appt.get('appt_type', 'N/A')}")
                print(f"     Display Card: {appt.get('display_card', 'N/A')}")
        else:
            print("  ⚠️  No appointments found in Appt_Index")
        
        # Check Master_Schedule
        print("\n" + "-" * 70)
        print("MASTER_SCHEDULE TAB")
        print("-" * 70)
        
        try:
            # Try to get all values from Master_Schedule
            master_values = client.master_schedule_worksheet.get_all_values()
            print(f"Total rows in Master_Schedule: {len(master_values)}")
            
            if len(master_values) > 0:
                print(f"\nHeaders: {master_values[0]}")
                
                if len(master_values) > 1:
                    print(f"\nData rows: {len(master_values) - 1}")
                    print("\nFirst few rows:")
                    for i, row in enumerate(master_values[1:6], 1):
                        print(f"  {i}. {row[:5]}...")  # Show first 5 columns
                else:
                    print("  ⚠️  Only header row exists - no data")
            else:
                print("  ⚠️  Master_Schedule tab is empty")
                
        except Exception as e:
            print(f"  ❌ Error reading Master_Schedule: {e}")
            import traceback
            traceback.print_exc()
        
        # Check if Master_Schedule needs population
        print("\n" + "-" * 70)
        print("ANALYSIS")
        print("-" * 70)
        
        if all_appts:
            master_values = client.master_schedule_worksheet.get_all_values()
            if len(master_values) <= 1:  # Only header or empty
                print("  ⚠️  Master_Schedule appears empty or only has headers")
                print("  💡 Master_Schedule should be populated from Appt_Index")
                print("\n  To populate Master_Schedule, run:")
                print("     client.populate_master_schedule_from_appt_index()")
            else:
                print(f"  ✅ Master_Schedule has {len(master_values) - 1} data rows")
                print(f"  ✅ Appt_Index has {len(all_appts)} rows")
                
                # Check if they match
                if len(master_values) - 1 != len(all_appts):
                    print(f"  ⚠️  Row count mismatch: Master_Schedule has {len(master_values) - 1} rows, Appt_Index has {len(all_appts)}")
                    print("  💡 Master_Schedule may need to be refreshed")
        else:
            print("  ⚠️  No appointments in Appt_Index to show in Master_Schedule")
        
        # Check Patients tab
        print("\n" + "-" * 70)
        print("PATIENTS TAB")
        print("-" * 70)
        
        try:
            all_patients = client.patients_worksheet.get_all_values()
            print(f"Total rows in Patients: {len(all_patients)}")
            if len(all_patients) > 1:
                print(f"  ✅ {len(all_patients) - 1} patients found")
            else:
                print("  ⚠️  Only header row - no patients")
        except Exception as e:
            print(f"  ❌ Error reading Patients: {e}")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    inspect_spreadsheet()
