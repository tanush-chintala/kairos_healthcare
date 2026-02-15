"""Google Sheets client for reading/writing appointment slots."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger("sheets-client")

# Column names in the Slots sheet
COLUMNS = [
    "slot_id",
    "clinic_id",
    "location_name",
    "operatory",
    "provider_name",
    "provider_role",
    "appt_type",
    "planned_duration_min",
    "start_datetime_local",
    "end_datetime_local",
    "status",
    "patient_type",
    "patient_first_name",
    "patient_last_name",
    "patient_phone",
    "patient_email",
    "patient_date_of_birth",
    "reason_for_visit",
    "urgency_level",
    "eligibility_status",
    "confirmation_status",
    "cancel_or_resched_reason",
    "created_by",
    "last_updated_at",
    "conversation_id",
]


class SheetsClient:
    """Client for interacting with Google Sheets appointment slots."""

    def __init__(self):
        """Initialize Google Sheets client."""
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        sheet_name = os.getenv("SLOTS_SHEET_NAME", "Slots")

        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID environment variable not set")
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")

        # Parse service account JSON
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError:
            # Try as file path
            if os.path.exists(service_account_json):
                with open(service_account_json, "r") as f:
                    service_account_info = json.load(f)
            else:
                raise ValueError(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON or file path")

        # Authenticate
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
        client = gspread.authorize(creds)

        # Open spreadsheet and worksheet
        self.spreadsheet = client.open_by_key(spreadsheet_id)
        self.worksheet = self.spreadsheet.worksheet(sheet_name)
        self._ensure_headers()

    def _ensure_headers(self) -> None:
        """Ensure the sheet has the correct headers.
        
        This method safely updates headers without deleting data.
        It only adds missing columns, preserving all existing data.
        """
        headers = self.worksheet.row_values(1)
        
        # If headers match exactly, nothing to do
        if headers == COLUMNS:
            return
        
        # If sheet is empty (no headers), add headers
        if not headers or len(headers) == 0:
            self.worksheet.append_row(COLUMNS)
            return
        
        # If headers don't match, we need to update them carefully
        # Check if we just need to add missing columns (safer approach)
        missing_columns = [col for col in COLUMNS if col not in headers]
        
        if missing_columns:
            # Add missing columns to the header row
            # Get the last column index
            last_col_letter = chr(64 + len(headers))  # Convert to column letter
            new_headers = headers + missing_columns
            
            # Update only the header row (row 1)
            # Calculate range for header update
            header_range = f"A1:{chr(64 + len(new_headers))}1"
            self.worksheet.update(header_range, [new_headers])
            
            logger.info(f"Added missing columns to headers: {missing_columns}")
        
        # If columns are in wrong order or extra columns exist, log warning but don't delete
        # The system will work with existing headers, just may have extra columns
        if set(headers) != set(COLUMNS):
            logger.warning(
                f"Header mismatch detected. Expected: {COLUMNS}, "
                f"Found: {headers}. Missing columns added, but order may differ."
            )

    def _row_to_dict(self, row: list[str]) -> dict[str, Any]:
        """Convert a row to a dictionary using column names."""
        return {col: row[i] if i < len(row) else "" for i, col in enumerate(COLUMNS)}

    def _dict_to_row(self, data: dict[str, Any]) -> list[str]:
        """Convert a dictionary to a row list."""
        return [str(data.get(col, "")) for col in COLUMNS]

    def find_row_by_slot_id(self, slot_id: str) -> tuple[int, dict[str, Any]] | None:
        """Find a row by slot_id. Returns (row_number, row_dict) or None."""
        all_values = self.worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):  # Skip header row
            row_dict = self._row_to_dict(row)
            if row_dict.get("slot_id") == slot_id:
                return (i, row_dict)
        return None

    def find_appointments_by_patient(
        self,
        patient_first_name: str | None = None,
        patient_last_name: str | None = None,
        patient_phone: str | None = None,
        date: str | None = None,
        status: str = "BOOKED",
    ) -> list[tuple[int, dict[str, Any]]]:
        """Find appointments by patient information.
        
        Args:
            patient_first_name: Patient's first name (optional)
            patient_last_name: Patient's last name (optional)
            patient_phone: Patient's phone number (optional)
            date: Filter by date in YYYY-MM-DD format (optional)
            status: Filter by status (default: "BOOKED" to find active appointments)
        
        Returns:
            List of (row_number, row_dict) tuples matching the criteria
        """
        all_values = self.worksheet.get_all_values()
        matches = []
        
        for i, row in enumerate(all_values[1:], start=2):  # Skip header row
            row_dict = self._row_to_dict(row)
            
            # Filter by status
            if row_dict.get("status") != status:
                continue
            
            # Filter by patient name (case-insensitive, partial match)
            if patient_first_name:
                if patient_first_name.lower() not in row_dict.get("patient_first_name", "").lower():
                    continue
            if patient_last_name:
                if patient_last_name.lower() not in row_dict.get("patient_last_name", "").lower():
                    continue
            
            # Filter by phone (normalize for comparison)
            if patient_phone:
                # Remove common formatting characters
                normalized_phone = "".join(c for c in patient_phone if c.isdigit())
                row_phone = "".join(c for c in row_dict.get("patient_phone", "") if c.isdigit())
                if normalized_phone and row_phone and normalized_phone not in row_phone and row_phone not in normalized_phone:
                    continue
            
            # Filter by date if provided
            if date:
                if not row_dict.get("start_datetime_local", "").startswith(date):
                    continue
            
            matches.append((i, row_dict))
        
        return matches

    def get_all_rows(self) -> list[dict[str, Any]]:
        """Get all rows as dictionaries (excluding header)."""
        all_values = self.worksheet.get_all_values()
        return [self._row_to_dict(row) for row in all_values[1:]]  # Skip header

    def update_row(self, row_number: int, data: dict[str, Any]) -> None:
        """Update a row with new data."""
        row_data = self._dict_to_row(data)
        self.worksheet.update(f"A{row_number}:{chr(64 + len(COLUMNS))}{row_number}", [row_data])

    def append_row(self, data: dict[str, Any]) -> None:
        """Append a new row to the sheet."""
        row_data = self._dict_to_row(data)
        self.worksheet.append_row(row_data)
