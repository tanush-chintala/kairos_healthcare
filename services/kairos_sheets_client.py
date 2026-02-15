"""Google Sheets client for Kairos single-doctor clinic scheduling."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger("kairos-sheets-client")

# Column definitions for each tab
PATIENTS_COLUMNS = [
    "patient_id",
    "first_name",
    "last_name",
    "phone_e164",
    "email",
    "dob",
    "patient_type",
    "consent_to_text",
    "preferred_contact_method",
    "insurance_provider",
    "insurance_member_id",
    "notes",
    "created_at_local",
    "last_updated_at_local",
]

APPT_INDEX_COLUMNS = [
    "row_id",
    "slot_key",
    "date_local",
    "start_time_local",
    "end_time_local",
    "lane",
    "operatory",
    "provider_name",
    "provider_role",
    "appt_type",
    "duration_min",
    "status",
    "appointment_id",
    "patient_id",
    "reason_for_visit",
    "urgency_level",
    "triage_red_flags",
    "booked_by",
    "cancel_or_resched_reason",
    "created_at_local",
    "last_updated_at_local",
    "conversation_id",
    "display_card",
]

# Master_Schedule columns (calendar view derived from Appt_Index)
MASTER_SCHEDULE_COLUMNS = [
    "date_local",
    "start_time_local",
    "end_time_local",
    "lane",
    "provider_name",
    "appt_type",
    "duration_min",
    "status",
    "appointment_id",
    "patient_id",
    "display_card",
    "row_id",  # Link back to Appt_Index
]


class KairosSheetsClient:
    """Client for interacting with Kairos clinic Google Sheets."""

    def __init__(self):
        """Initialize Google Sheets client."""
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        patients_sheet_name = os.getenv("PATIENTS_SHEET_NAME", "Patients")
        appt_index_sheet_name = os.getenv("APPT_INDEX_SHEET_NAME", "Appt_Index")

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
                raise ValueError(
                    f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON or file path"
                )

        # Authenticate
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
        client = gspread.authorize(creds)

        # Open spreadsheet and worksheets
        self.spreadsheet = client.open_by_key(spreadsheet_id)
        self.patients_worksheet = self.spreadsheet.worksheet(patients_sheet_name)
        self.appt_index_worksheet = self.spreadsheet.worksheet(appt_index_sheet_name)
        
        # Master_Schedule is optional (read-only, but we can populate it for testing)
        master_schedule_name = os.getenv("MASTER_SCHEDULE_SHEET_NAME", "Master_Schedule")
        try:
            self.master_schedule_worksheet = self.spreadsheet.worksheet(master_schedule_name)
        except gspread.exceptions.WorksheetNotFound:
            # Create it if it doesn't exist
            self.master_schedule_worksheet = self.spreadsheet.add_worksheet(
                title=master_schedule_name, rows=1000, cols=20
            )

        # Ensure headers exist
        self._ensure_headers(self.patients_worksheet, PATIENTS_COLUMNS)
        self._ensure_headers(self.appt_index_worksheet, APPT_INDEX_COLUMNS)
        self._ensure_headers(self.master_schedule_worksheet, MASTER_SCHEDULE_COLUMNS)

        logger.info(
            f"Connected to Kairos Sheets: {patients_sheet_name}, {appt_index_sheet_name}"
        )

    def _ensure_headers(self, worksheet: gspread.worksheet.Worksheet, columns: list[str]) -> None:
        """Ensure the sheet has the correct headers without deleting data."""
        headers = worksheet.row_values(1)

        # If headers match exactly, nothing to do
        if headers == columns:
            return

        # If sheet is empty (no headers), add headers
        if not headers or len(headers) == 0:
            worksheet.append_row(columns)
            return

        # Add missing columns to the header row
        missing_columns = [col for col in columns if col not in headers]

        if missing_columns:
            new_headers = headers + missing_columns
            header_range = f"A1:{chr(64 + len(new_headers))}1"
            worksheet.update(header_range, [new_headers])
            logger.info(f"Added missing columns to headers: {missing_columns}")

        if set(headers) != set(columns):
            logger.warning(
                f"Header mismatch detected. Expected: {columns}, "
                f"Found: {headers}. Missing columns added, but order may differ."
            )

    def _row_to_dict(self, row: list[str], columns: list[str]) -> dict[str, Any]:
        """Convert a row to a dictionary using column names."""
        return {col: row[i] if i < len(row) else "" for i, col in enumerate(columns)}

    def _dict_to_row(self, data: dict[str, Any], columns: list[str]) -> list[str]:
        """Convert a dictionary to a row list."""
        return [str(data.get(col, "")) for col in columns]

    # ========== PATIENT OPERATIONS ==========

    def find_patient_by_phone(self, phone_e164: str) -> tuple[int, dict[str, Any]] | None:
        """Find a patient by phone_e164. Returns (row_number, patient_dict) or None."""
        all_values = self.patients_worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):  # Skip header row
            patient_dict = self._row_to_dict(row, PATIENTS_COLUMNS)
            # Normalize phone for comparison
            stored_phone = "".join(c for c in patient_dict.get("phone_e164", "") if c.isdigit())
            search_phone = "".join(c for c in phone_e164 if c.isdigit())
            if stored_phone == search_phone:
                return (i, patient_dict)
        return None

    def find_patient_by_id(self, patient_id: str) -> tuple[int, dict[str, Any]] | None:
        """Find a patient by patient_id. Returns (row_number, patient_dict) or None."""
        all_values = self.patients_worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            patient_dict = self._row_to_dict(row, PATIENTS_COLUMNS)
            if patient_dict.get("patient_id") == patient_id:
                return (i, patient_dict)
        return None

    def get_all_patients(self) -> list[dict[str, Any]]:
        """Get all patients."""
        all_values = self.patients_worksheet.get_all_values()
        return [self._row_to_dict(row, PATIENTS_COLUMNS) for row in all_values[1:]]

    def create_patient(self, patient_data: dict[str, Any]) -> str:
        """Create a new patient and return patient_id."""
        # Generate patient_id
        all_patients = self.get_all_patients()
        existing_ids = [p.get("patient_id", "") for p in all_patients if p.get("patient_id")]
        max_num = 0
        for pid in existing_ids:
            if pid.startswith("P-") and pid[2:].isdigit():
                max_num = max(max_num, int(pid[2:]))
        new_patient_id = f"P-{max_num + 1:06d}"

        now = datetime.now().isoformat()
        patient_data["patient_id"] = new_patient_id
        patient_data["created_at_local"] = now
        patient_data["last_updated_at_local"] = now

        row_data = self._dict_to_row(patient_data, PATIENTS_COLUMNS)
        self.patients_worksheet.append_row(row_data)

        logger.info(f"Created patient {new_patient_id}")
        return new_patient_id

    def update_patient(self, row_number: int, patient_data: dict[str, Any]) -> None:
        """Update a patient row."""
        patient_data["last_updated_at_local"] = datetime.now().isoformat()
        row_data = self._dict_to_row(patient_data, PATIENTS_COLUMNS)
        self.patients_worksheet.update(f"A{row_number}:{chr(64 + len(PATIENTS_COLUMNS))}{row_number}", [row_data])

    # ========== APPOINTMENT INDEX OPERATIONS ==========

    def find_row_by_row_id(self, row_id: str) -> tuple[int, dict[str, Any]] | None:
        """Find a row by row_id. Returns (row_number, row_dict) or None."""
        all_values = self.appt_index_worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            row_dict = self._row_to_dict(row, APPT_INDEX_COLUMNS)
            if row_dict.get("row_id") == row_id:
                return (i, row_dict)
        return None

    def find_row_by_appointment_id(self, appointment_id: str) -> tuple[int, dict[str, Any]] | None:
        """Find a row by appointment_id. Returns (row_number, row_dict) or None."""
        all_values = self.appt_index_worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            row_dict = self._row_to_dict(row, APPT_INDEX_COLUMNS)
            if row_dict.get("appointment_id") == appointment_id:
                return (i, row_dict)
        return None

    def find_rows_by_slot_key(self, slot_key: str) -> tuple[int, dict[str, Any]] | None:
        """Find a row by slot_key. Returns (row_number, row_dict) or None."""
        all_values = self.appt_index_worksheet.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            row_dict = self._row_to_dict(row, APPT_INDEX_COLUMNS)
            if row_dict.get("slot_key") == slot_key:
                return (i, row_dict)
        return None

    def get_all_appt_rows(self) -> list[dict[str, Any]]:
        """Get all appointment index rows."""
        all_values = self.appt_index_worksheet.get_all_values()
        return [self._row_to_dict(row, APPT_INDEX_COLUMNS) for row in all_values[1:]]

    def update_appt_row(self, row_number: int, row_data: dict[str, Any]) -> None:
        """Update an appointment index row."""
        row_data["last_updated_at_local"] = datetime.now().isoformat()
        row_list = self._dict_to_row(row_data, APPT_INDEX_COLUMNS)
        self.appt_index_worksheet.update(
            f"A{row_number}:{chr(64 + len(APPT_INDEX_COLUMNS))}{row_number}", [row_list]
        )

    def append_appt_row(self, row_data: dict[str, Any]) -> None:
        """Append a new appointment index row."""
        now = datetime.now().isoformat()
        if not row_data.get("created_at_local"):
            row_data["created_at_local"] = now
        row_data["last_updated_at_local"] = now

        # Generate row_id if not provided
        if not row_data.get("row_id"):
            all_rows = self.get_all_appt_rows()
            existing_ids = [r.get("row_id", "") for r in all_rows if r.get("row_id")]
            max_num = 0
            for rid in existing_ids:
                if rid.startswith("IDX-") and rid[4:].isdigit():
                    max_num = max(max_num, int(rid[4:]))
            row_data["row_id"] = f"IDX-{max_num + 1:06d}"

        # Generate appointment_id if booking
        if row_data.get("status") == "BOOKED" and not row_data.get("appointment_id"):
            all_rows = self.get_all_appt_rows()
            existing_appt_ids = [
                r.get("appointment_id", "") for r in all_rows if r.get("appointment_id")
            ]
            max_num = 0
            for aid in existing_appt_ids:
                if aid.startswith("A-") and aid[2:].isdigit():
                    max_num = max(max_num, int(aid[2:]))
            row_data["appointment_id"] = f"A-{max_num + 1:06d}"

        row_list = self._dict_to_row(row_data, APPT_INDEX_COLUMNS)
        self.appt_index_worksheet.append_row(row_list)

    def _generate_display_card(self, row_data: dict[str, Any], patient_data: dict[str, Any] | None = None) -> str:
        """Generate display_card based on status and row data."""
        status = row_data.get("status", "OPEN")
        appt_type = row_data.get("appt_type", "")
        duration_min = row_data.get("duration_min", "")
        patient_id = row_data.get("patient_id", "")

        if status == "OPEN":
            return f"[OPEN] {appt_type} ({duration_min}m)"

        if status == "BOOKED":
            if patient_data:
                first_initial = patient_data.get("first_name", "")[0] if patient_data.get("first_name") else ""
                last_name = patient_data.get("last_name", "")
                return f"[BOOKED] {patient_id} | {appt_type} | {first_initial}. {last_name}"
            return f"[BOOKED] {patient_id} | {appt_type}"

        if status == "CANCELLED":
            return f"[CANCELLED] {appt_type} | {patient_id}"

        if status == "NO_SHOW":
            return f"[NO_SHOW] {appt_type} | {patient_id}"

        if status == "COMPLETED":
            return f"[DONE] {appt_type} | {patient_id}"

        return f"[{status}] {appt_type}"

    # ========== MASTER SCHEDULE OPERATIONS ==========

    def populate_master_schedule_from_appt_index(self) -> None:
        """Populate Master_Schedule from Appt_Index (for testing/setup)."""
        # Get all appointments from Appt_Index
        all_appts = self.get_all_appt_rows()
        
        # Clear existing data (keep headers)
        # Get current row count
        current_rows = len(self.master_schedule_worksheet.get_all_values())
        if current_rows > 1:  # More than just header
            # Delete all rows except header (row 1)
            self.master_schedule_worksheet.delete_rows(2, current_rows + 1)
        
        # Build master schedule rows
        master_rows = []
        for appt in all_appts:
            # Skip rows without date (empty rows)
            if not appt.get("date_local"):
                continue
                
            master_row = {
                "date_local": appt.get("date_local", ""),
                "start_time_local": appt.get("start_time_local", ""),
                "end_time_local": appt.get("end_time_local", ""),
                "lane": appt.get("lane", ""),
                "provider_name": appt.get("provider_name", ""),
                "appt_type": appt.get("appt_type", ""),
                "duration_min": appt.get("duration_min", ""),
                "status": appt.get("status", ""),
                "appointment_id": appt.get("appointment_id", ""),
                "patient_id": appt.get("patient_id", ""),
                "display_card": appt.get("display_card", ""),
                "row_id": appt.get("row_id", ""),
            }
            master_rows.append(master_row)
        
        # Sort by date and time
        master_rows.sort(key=lambda x: (x.get("date_local", ""), x.get("start_time_local", "")))
        
        # Append rows
        if master_rows:
            row_lists = [self._dict_to_row(row, MASTER_SCHEDULE_COLUMNS) for row in master_rows]
            self.master_schedule_worksheet.append_rows(row_lists)
        
        logger.info(f"Populated Master_Schedule with {len(master_rows)} entries")
