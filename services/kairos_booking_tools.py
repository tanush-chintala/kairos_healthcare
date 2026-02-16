"""Kairos clinic booking tools for single-doctor scheduling."""

import logging
from datetime import datetime, timedelta
from typing import Any

from services.kairos_sheets_client import KairosSheetsClient
from services.verification import ActionType, VerificationResult, verify_patient_identity

logger = logging.getLogger("kairos-booking-tools")

# Initialize sheets client (singleton)
_kairos_client: KairosSheetsClient | None = None


def get_kairos_client() -> KairosSheetsClient:
    """Get or create the Kairos sheets client."""
    global _kairos_client
    if _kairos_client is None:
        _kairos_client = KairosSheetsClient()
    return _kairos_client


def find_openings(
    date_start: str,
    date_end: str,
    appt_type: str | None = None,
    duration_min: int | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Find open appointment slots.

    Args:
        date_start: Start date in YYYY-MM-DD format
        date_end: End date in YYYY-MM-DD format (inclusive)
        appt_type: Filter by appointment type (optional)
        duration_min: Filter by duration in minutes (optional)
        limit: Maximum number of slots to return (default: 5)

    Returns:
        List of opening dictionaries with row_id, slot_key, date, start/end, appt_type, duration_min
    """
    try:
        client = get_kairos_client()
        all_rows = client.get_all_appt_rows()

        # Filter for OPEN slots in Dr-Chair lane
        date_start_normalized = str(date_start).strip()
        date_end_normalized = str(date_end).strip()
        
        open_slots = []
        for row in all_rows:
            row_status = str(row.get("status", "")).strip()
            row_lane = str(row.get("lane", "")).strip()
            row_date = str(row.get("date_local", "")).strip()
            
            if (row_status == "OPEN"
                and row_lane == "Dr-Chair"
                and row_date >= date_start_normalized
                and row_date <= date_end_normalized):
                open_slots.append(row)

        # Filter by appt_type if provided
        if appt_type:
            open_slots = [s for s in open_slots if str(s.get("appt_type", "")).strip() == str(appt_type).strip()]

        # Filter by duration_min if provided
        if duration_min:
            open_slots = [
                s for s in open_slots 
                if int(str(s.get("duration_min", 0)).strip() or 0) == duration_min
            ]

        # Sort by date then start time
        open_slots.sort(key=lambda x: (x.get("date_local", ""), x.get("start_time_local", "")))

        # Limit results
        open_slots = open_slots[:limit]

        # Return required fields
        result = []
        for slot in open_slots:
            result.append(
                {
                    "row_id": slot.get("row_id"),
                    "slot_key": slot.get("slot_key"),
                    "date_local": slot.get("date_local"),
                    "start_time_local": slot.get("start_time_local"),
                    "end_time_local": slot.get("end_time_local"),
                    "appt_type": slot.get("appt_type"),
                    "duration_min": slot.get("duration_min"),
                    "provider_name": slot.get("provider_name"),
                }
            )

        logger.info(f"Found {len(result)} open slots")
        return result

    except Exception as e:
        logger.error(f"Error finding openings: {e}")
        raise


def upsert_patient(patient_payload: dict[str, Any]) -> str:
    """Upsert a patient (find by phone_e164, create if missing, update if present).

    Args:
        patient_payload: Dictionary with patient fields:
            - first_name (required)
            - last_name (required)
            - phone_e164 (required, primary lookup key)
            - email (optional)
            - dob (optional)
            - consent_to_text (optional, Y/N)
            - preferred_contact_method (optional, SMS/CALL/EMAIL)
            - insurance_provider (optional)
            - insurance_member_id (optional)

    Returns:
        patient_id (existing or newly created)
    """
    try:
        client = get_kairos_client()
        phone_e164 = patient_payload.get("phone_e164", "").strip()

        if not phone_e164:
            raise ValueError("phone_e164 is required")

        # Find existing patient
        result = client.find_patient_by_phone(phone_e164)

        if result:
            row_number, existing_patient = result
            patient_id = existing_patient.get("patient_id")

            # Update fields if provided
            update_data = existing_patient.copy()
            for key, value in patient_payload.items():
                if value is not None and value != "":
                    update_data[key] = value

            # Preserve patient_type if not provided
            if "patient_type" not in patient_payload:
                update_data["patient_type"] = existing_patient.get("patient_type", "EXISTING")

            client.update_patient(row_number, update_data)
            logger.info(f"Updated patient {patient_id}")
            return patient_id
        else:
            # Create new patient
            new_patient = {
                "first_name": patient_payload.get("first_name", ""),
                "last_name": patient_payload.get("last_name", ""),
                "phone_e164": phone_e164,
                "email": patient_payload.get("email", ""),
                "dob": patient_payload.get("dob", ""),
                "patient_type": patient_payload.get("patient_type", "NEW"),
                "consent_to_text": patient_payload.get("consent_to_text", "N"),
                "preferred_contact_method": patient_payload.get("preferred_contact_method", ""),
                "insurance_provider": patient_payload.get("insurance_provider", ""),
                "insurance_member_id": patient_payload.get("insurance_member_id", ""),
                "notes": patient_payload.get("notes", ""),
            }

            patient_id = client.create_patient(new_patient)
            logger.info(f"Created new patient {patient_id}")
            return patient_id

    except Exception as e:
        logger.error(f"Error upserting patient: {e}")
        raise


def book_appointment(
    opening_row_id: str,
    patient_id: str,
    appt_type: str,
    reason_for_visit: str,
    urgency_level: str = "ROUTINE",
    triage_red_flags: str = "N",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Book an appointment.

    Args:
        opening_row_id: The row_id of the OPEN slot to book
        patient_id: Patient ID from upsert_patient
        appt_type: Appointment type (e.g., "Cleaning", "Filling", "LimitedExam")
        reason_for_visit: Reason for the visit
        urgency_level: ROUTINE, SOON, or URGENT (default: ROUTINE)
        triage_red_flags: Y or N (default: N)
        conversation_id: Optional conversation ID

    Returns:
        Confirmation dictionary with appointment details

    Raises:
        ValueError: If slot is not OPEN or not found
    """
    try:
        client = get_kairos_client()

        # Find the opening row
        result = client.find_row_by_row_id(opening_row_id)
        if not result:
            raise ValueError(f"Opening with row_id {opening_row_id} not found")

        row_number, row_data = result

        # Verify it's OPEN
        if row_data.get("status") != "OPEN":
            raise ValueError(
                f"Row {opening_row_id} is not OPEN (current status: {row_data.get('status')})"
            )

        # Verify it's Dr-Chair
        if row_data.get("lane") != "Dr-Chair":
            raise ValueError(f"Row {opening_row_id} is not in Dr-Chair lane")

        # Get patient data for display_card
        patient_result = client.find_patient_by_id(patient_id)
        patient_data = patient_result[1] if patient_result else None

        # Generate appointment_id
        all_rows = client.get_all_appt_rows()
        existing_appt_ids = [r.get("appointment_id", "") for r in all_rows if r.get("appointment_id")]
        max_num = 0
        for aid in existing_appt_ids:
            if aid.startswith("A-") and aid[2:].isdigit():
                max_num = max(max_num, int(aid[2:]))
        appointment_id = f"A-{max_num + 1:06d}"

        # Update row to BOOKED
        row_data["status"] = "BOOKED"
        row_data["appointment_id"] = appointment_id
        row_data["patient_id"] = patient_id
        row_data["appt_type"] = appt_type
        row_data["reason_for_visit"] = reason_for_visit
        row_data["urgency_level"] = urgency_level
        row_data["triage_red_flags"] = triage_red_flags
        row_data["booked_by"] = "AI"
        row_data["provider_role"] = "dentist"
        row_data["lane"] = "Dr-Chair"
        if conversation_id:
            row_data["conversation_id"] = conversation_id

        # Generate display_card
        row_data["display_card"] = client._generate_display_card(row_data, patient_data)

        client.update_appt_row(row_number, row_data)

        logger.info(f"Booked appointment {appointment_id} for patient {patient_id}")

        return {
            "appointment_id": appointment_id,
            "row_id": opening_row_id,
            "patient_id": patient_id,
            "date_local": row_data.get("date_local"),
            "start_time_local": row_data.get("start_time_local"),
            "end_time_local": row_data.get("end_time_local"),
            "appt_type": appt_type,
            "provider_name": row_data.get("provider_name"),
            "status": "BOOKED",
        }

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        raise


def cancel_appointment(
    appointment_id: str | None = None,
    row_id: str | None = None,
    cancel_reason: str = "",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Cancel an appointment using Option 1 policy (flip back to OPEN).

    Args:
        appointment_id: Appointment ID to cancel (optional if row_id provided)
        row_id: Row ID to cancel (optional if appointment_id provided)
        cancel_reason: Reason for cancellation
        conversation_id: Optional conversation ID

    Returns:
        Confirmation dictionary

    Raises:
        ValueError: If appointment not found or not BOOKED
    """
    try:
        client = get_kairos_client()

        # Find the row
        result = None
        if appointment_id:
            result = client.find_row_by_appointment_id(appointment_id)
        elif row_id:
            result = client.find_row_by_row_id(row_id)
        else:
            raise ValueError("Either appointment_id or row_id must be provided")

        if not result:
            identifier = appointment_id or row_id
            raise ValueError(f"Appointment {identifier} not found")

        row_number, row_data = result

        # Verify it's BOOKED
        if row_data.get("status") != "BOOKED":
            raise ValueError(
                f"Appointment is not BOOKED (current status: {row_data.get('status')})"
            )

        # Verify patient identity (Level 2 - sensitive action)
        if verification_result is None and patient_data:
            # Get patient data from appointment
            patient_id = row_data.get("patient_id")
            stored_patient_data = None
            if patient_id:
                patient_result = client.find_patient_by_id(patient_id)
                if patient_result:
                    _, stored_patient_data = patient_result

            verification_result = verify_patient_identity(
                ActionType.CANCEL_APPOINTMENT,
                patient_data,
                stored_patient_data=stored_patient_data,
            )

        if verification_result and not verification_result.verified:
            if verification_result.requires_escalation:
                raise ValueError(
                    verification_result.error_message or "For security, I'll transfer you to the front desk."
                )
            raise ValueError(
                verification_result.error_message or "Verification failed. Please provide the required information."
            )

        # Option 1: Flip back to OPEN by clearing patient fields
        row_data["status"] = "OPEN"
        row_data["cancel_or_resched_reason"] = cancel_reason
        if conversation_id:
            row_data["conversation_id"] = conversation_id

        # Clear booking fields
        row_data["appointment_id"] = ""
        row_data["patient_id"] = ""
        row_data["reason_for_visit"] = ""
        row_data["urgency_level"] = ""
        row_data["triage_red_flags"] = ""
        row_data["booked_by"] = ""

        # Regenerate display_card for OPEN status
        row_data["display_card"] = client._generate_display_card(row_data)

        client.update_appt_row(row_number, row_data)

        logger.info(f"Cancelled appointment {appointment_id or row_id}: {cancel_reason}")

        return {
            "status": "CANCELLED",
            "row_id": row_data.get("row_id"),
            "slot_key": row_data.get("slot_key"),
            "cancel_reason": cancel_reason,
        }

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        raise


def reschedule_appointment(
    old_identifier: str,
    new_opening_row_id: str,
    cancel_reason: str = "Rescheduled",
    conversation_id: str | None = None,
    patient_data: dict[str, Any] | None = None,
    verification_result: VerificationResult | None = None,
) -> dict[str, Any]:
    """Reschedule an appointment by canceling old and booking new.

    Args:
        old_identifier: Appointment ID or row_id of the appointment to reschedule
        new_opening_row_id: Row ID of the new OPEN slot to book
        cancel_reason: Reason for rescheduling (default: "Rescheduled")
        conversation_id: Optional conversation ID

    Returns:
        Dictionary with both old cancellation and new booking details

    Raises:
        ValueError: If old appointment not found or new opening not available
    """
    try:
        client = get_kairos_client()

        # Find old appointment
        old_result = None
        if old_identifier.startswith("A-"):
            old_result = client.find_row_by_appointment_id(old_identifier)
        else:
            old_result = client.find_row_by_row_id(old_identifier)

        if not old_result:
            raise ValueError(f"Old appointment {old_identifier} not found")

        old_row_number, old_row_data = old_result

        if old_row_data.get("status") != "BOOKED":
            raise ValueError(f"Old appointment is not BOOKED (status: {old_row_data.get('status')})")

        patient_id = old_row_data.get("patient_id")
        if not patient_id:
            raise ValueError("Old appointment has no patient_id")

        # Verify patient identity (Level 2 - sensitive action)
        if verification_result is None and patient_data:
            # Get patient data from appointment
            patient_result = client.find_patient_by_id(patient_id)
            stored_patient_data = None
            if patient_result:
                _, stored_patient_data = patient_result

            verification_result = verify_patient_identity(
                ActionType.RESCHEDULE_APPOINTMENT,
                patient_data,
                stored_patient_data=stored_patient_data,
            )

        if verification_result and not verification_result.verified:
            if verification_result.requires_escalation:
                raise ValueError(
                    verification_result.error_message or "For security, I'll transfer you to the front desk."
                )
            raise ValueError(
                verification_result.error_message or "Verification failed. Please provide the required information."
            )

        appt_type = old_row_data.get("appt_type", "")
        reason_for_visit = old_row_data.get("reason_for_visit", "")
        urgency_level = old_row_data.get("urgency_level", "ROUTINE")
        triage_red_flags = old_row_data.get("triage_red_flags", "N")

        # Cancel old appointment (verification already done above)
        cancel_info = cancel_appointment(
            row_id=old_row_data.get("row_id"),
            cancel_reason=cancel_reason,
            conversation_id=conversation_id,
            patient_data=patient_data,
            verification_result=verification_result,
        )

        # Book new appointment
        new_booking = book_appointment(
            opening_row_id=new_opening_row_id,
            patient_id=patient_id,
            appt_type=appt_type,
            reason_for_visit=reason_for_visit,
            urgency_level=urgency_level,
            triage_red_flags=triage_red_flags,
            conversation_id=conversation_id,
        )

        logger.info(
            f"Rescheduled from {old_identifier} to {new_booking['appointment_id']}"
        )

        return {
            "old_appointment": cancel_info,
            "new_appointment": new_booking,
            "status": "RESCHEDULED",
        }

    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        raise


def get_day_view(date_local: str) -> list[dict[str, Any]]:
    """Get all appointments for a specific day.

    Args:
        date_local: Date in YYYY-MM-DD format

    Returns:
        List of all appointment index rows for that day, sorted by start_time_local
    """
    try:
        client = get_kairos_client()
        all_rows = client.get_all_appt_rows()

        # Filter by date
        day_rows = [row for row in all_rows if row.get("date_local") == date_local]

        # Sort by start_time_local
        day_rows.sort(key=lambda x: x.get("start_time_local", ""))

        logger.info(f"Found {len(day_rows)} appointments for {date_local}")
        return day_rows

    except Exception as e:
        logger.error(f"Error getting day view: {e}")
        raise


def find_patient_appointments_by_phone(
    phone_e164: str,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Find appointments by patient phone number.

    Args:
        phone_e164: Patient phone number
        date: Optional date filter in YYYY-MM-DD format

    Returns:
        List of booked appointments for the patient
    """
    try:
        client = get_kairos_client()

        # Find patient
        result = client.find_patient_by_phone(phone_e164)
        if not result:
            return []

        _, patient_data = result
        patient_id = patient_data.get("patient_id")

        # Find appointments
        all_rows = client.get_all_appt_rows()
        appointments = [
            row
            for row in all_rows
            if row.get("patient_id") == patient_id
            and row.get("status") == "BOOKED"
        ]

        # Filter by date if provided
        if date:
            appointments = [a for a in appointments if a.get("date_local") == date]

        # Sort by date and time
        appointments.sort(key=lambda x: (x.get("date_local", ""), x.get("start_time_local", "")))

        logger.info(f"Found {len(appointments)} appointments for patient {patient_id}")
        return appointments

    except Exception as e:
        logger.error(f"Error finding patient appointments: {e}")
        raise
