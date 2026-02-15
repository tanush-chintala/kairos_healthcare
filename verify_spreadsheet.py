"""Script to verify the Google Sheet structure matches Kairos requirements."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from services.kairos_sheets_client import APPT_INDEX_COLUMNS, PATIENTS_COLUMNS, KairosSheetsClient

load_dotenv()

def verify_spreadsheet():
    """Verify the spreadsheet has the correct structure."""
    try:
        client = KairosSheetsClient()
        
        print("=" * 70)
        print("VERIFYING SPREADSHEET STRUCTURE")
        print("=" * 70)
        
        # Check Appt_Index tab
        print("\n📋 Appt_Index Tab:")
        appt_headers = client.appt_index_worksheet.row_values(1)
        print(f"  Found {len(appt_headers)} columns")
        
        missing_appt = [col for col in APPT_INDEX_COLUMNS if col not in appt_headers]
        extra_appt = [col for col in appt_headers if col not in APPT_INDEX_COLUMNS]
        
        if missing_appt:
            print(f"  ⚠️  Missing columns: {missing_appt}")
        if extra_appt:
            print(f"  ℹ️  Extra columns (will be ignored): {extra_appt}")
        if not missing_appt and not extra_appt:
            print("  ✅ All required columns present!")
        
        # Check Patients tab
        print("\n👥 Patients Tab:")
        patients_headers = client.patients_worksheet.row_values(1)
        print(f"  Found {len(patients_headers)} columns")
        
        missing_patients = [col for col in PATIENTS_COLUMNS if col not in patients_headers]
        extra_patients = [col for col in patients_headers if col not in PATIENTS_COLUMNS]
        
        if missing_patients:
            print(f"  ⚠️  Missing columns: {missing_patients}")
        if extra_patients:
            print(f"  ℹ️  Extra columns (will be ignored): {extra_patients}")
        if not missing_patients and not extra_patients:
            print("  ✅ All required columns present!")
        
        # Check for Master_Schedule tab (should exist but be read-only)
        print("\n📅 Master_Schedule Tab:")
        try:
            master_schedule = client.spreadsheet.worksheet("Master_Schedule")
            print("  ✅ Master_Schedule tab exists (read-only)")
        except Exception as e:
            print(f"  ⚠️  Master_Schedule tab not found: {e}")
        
        # Count rows
        print("\n📊 Data Summary:")
        appt_rows = len(client.appt_index_worksheet.get_all_values()) - 1  # Exclude header
        patient_rows = len(client.patients_worksheet.get_all_values()) - 1  # Exclude header
        print(f"  Appt_Index: {appt_rows} rows (excluding header)")
        print(f"  Patients: {patient_rows} rows (excluding header)")
        
        print("\n" + "=" * 70)
        print("VERIFICATION COMPLETE")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error verifying spreadsheet: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_spreadsheet()
