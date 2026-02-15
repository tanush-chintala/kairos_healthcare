"""Booking tools for dental appointment scheduling via Google Sheets."""

import logging
from datetime import datetime
from typing import Any

from services.sheets_client import SheetsClient
from services.verification import (
    ActionType,
    VerificationResult,
    verify_patient_identity,
)

logger = logging.getLogger("booking-tools")

# Initialize sheets client (will be created on first use)
_sheets_client: SheetsClient | None = None


def get_sheets_client() -> SheetsClient:
    """Get or create the sheets client."""
    global _sheets_client
    if _sheets_client is None:
        _sheets_client = SheetsClient()
    return _sheets_client


def find_open_slots(
    appt_type: str | None = None,
    date: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Find open appointment slots.

    Args:
        appt_type: Filter by appointment type (optional)
        date: Filter by date in YYYY-MM-DD format (optional)
        limit: Maximum number of slots to return (default: 3)

    Returns:
        List of slot dictionaries with: slot_id, appt_type, provider_name,
        start_datetime_local, end_datetime_local
    """
    try:
        client = get_sheets_client()
        all_rows = client.get_all_rows()

        # Filter for OPEN slots
        open_slots = [row for row in all_rows if row.get("status") == "OPEN"]

        # Filter by appt_type if provided
        if appt_type:
            open_slots = [s for s in open_slots if s.get("appt_type") == appt_type]

        # Filter by date if provided
        if date:
            open_slots = [
                s
                for s in open_slots
                if s.get("start_datetime_local", "").startswith(date)
            ]

        # Sort by start_datetime_local
        open_slots.sort(key=lambda x: x.get("start_datetime_local", ""))

        # Limit results
        open_slots = open_slots[:limit]

        # Return only required fields
        result = []
        for slot in open_slots:
            result.append(
                {
                    "slot_id": slot.get("slot_id"),
                    "appt_type": slot.get("appt_type"),
                    "provider_name": slot.get("provider_name"),
                    "start_datetime_local": slot.get("start_datetime_local"),
                    "end_datetime_local": slot.get("end_datetime_local"),
                }
            )

        logger.info(f"Found {len(result)} open slots")
        return result

    except Exception as e:
        logger.error(f"Error finding open slots: {e}")
        raise


def book_slot(
    slot_id: str,
    patient: dict[str, Any],
    reason_for_visit: str,
    urgency_level: str = "ROUTINE",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Book an appointment slot.

    Args:
        slot_id: The slot ID to book
        patient: Dictionary with patient info (first_name, last_name, phone, email, type)
        reason_for_visit: Reason for the visit
        urgency_level: Urgency level (default: "ROUTINE")
        conversation_id: Optional conversation ID

    Returns:
        Confirmation summary dictionary

    Raises:
        ValueError: If slot is not OPEN or not found
    """
    try:
        client = get_sheets_client()

        # Re-read the row to avoid race conditions
        result = client.find_row_by_slot_id(slot_id)
        if not result:
            raise ValueError(
                f"Slot {slot_id} not found in the system. "
                "You must use a slot_id that was returned from find_open_slots. "
                "Do not make up or invent slot IDs."
            )

        row_number, slot_data = result

        # Check if slot is OPEN
        if slot_data.get("status") != "OPEN":
            current_status = slot_data.get("status", "UNKNOWN")
            raise ValueError(
                f"Slot {slot_id} cannot be booked because it is {current_status}, not OPEN. "
                "The slot may have already been booked by someone else. "
                "Please use find_open_slots to find available slots."
            )

        # Update slot with booking information
        slot_data["status"] = "BOOKED"
        slot_data["patient_type"] = patient.get("type", "NEW")
        slot_data["patient_first_name"] = patient.get("first_name", "")
        slot_data["patient_last_name"] = patient.get("last_name", "")
        slot_data["patient_phone"] = patient.get("phone", "")
        slot_data["patient_email"] = patient.get("email", "")
        slot_data["patient_date_of_birth"] = patient.get("date_of_birth", "")
        slot_data["reason_for_visit"] = reason_for_visit
        slot_data["urgency_level"] = urgency_level
        slot_data["eligibility_status"] = "UNVERIFIED"
        slot_data["confirmation_status"] = "UNCONFIRMED"
        slot_data["created_by"] = "AI"
        slot_data["last_updated_at"] = datetime.now().isoformat()
        if conversation_id:
            slot_data["conversation_id"] = conversation_id

        # Write back to sheet
        client.update_row(row_number, slot_data)

        logger.info(f"Booked slot {slot_id} for {patient.get('first_name')} {patient.get('last_name')}")

        # Return confirmation summary
        return {
            "slot_id": slot_id,
            "status": "BOOKED",
            "patient_name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
            "provider_name": slot_data.get("provider_name"),
            "start_datetime_local": slot_data.get("start_datetime_local"),
            "end_datetime_local": slot_data.get("end_datetime_local"),
            "appt_type": slot_data.get("appt_type"),
            "confirmation_status": "UNCONFIRMED",
        }

    except Exception as e:
        logger.error(f"Error booking slot {slot_id}: {e}")
        raise


def cancel_slot(
    slot_id: str,
    reason: str,
    patient_data: dict[str, Any] | None = None,
    verification_result: VerificationResult | None = None,
) -> dict[str, Any]:
    """Cancel an appointment slot.

    Args:
        slot_id: The slot ID to cancel
        reason: Reason for cancellation
        patient_data: Patient information for verification (optional if verification_result provided)
        verification_result: Pre-verified result (optional, will verify if not provided)

    Returns:
        Confirmation dictionary

    Raises:
        ValueError: If slot is not BOOKED, not found, or verification fails
    """
    try:
        client = get_sheets_client()

        # Re-read the row to avoid race conditions
        result = client.find_row_by_slot_id(slot_id)
        if not result:
            raise ValueError(
                f"Slot {slot_id} not found in the system. "
                "You must use a valid slot_id. Do not make up or invent slot IDs."
            )

        row_number, slot_data = result

        # Check if slot is BOOKED
        if slot_data.get("status") != "BOOKED":
            current_status = slot_data.get("status", "UNKNOWN")
            raise ValueError(
                f"Slot {slot_id} cannot be cancelled because it is {current_status}, not BOOKED. "
                "Only booked appointments can be cancelled."
            )

        # Verify patient identity (Level 2 - sensitive action)
        if verification_result is None and patient_data:
            verification_result = verify_patient_identity(
                ActionType.CANCEL_APPOINTMENT,
                patient_data,
                stored_patient_data=slot_data,
            )

        if verification_result and not verification_result.verified:
            if verification_result.requires_escalation:
                raise ValueError(verification_result.error_message or "For security, I'll transfer you to the front desk.")
            raise ValueError(verification_result.error_message or "Verification failed. Please provide the required information.")

        # Update slot
        slot_data["status"] = "CANCELLED"
        slot_data["cancel_or_resched_reason"] = reason
        slot_data["last_updated_at"] = datetime.now().isoformat()

        # Write back to sheet
        client.update_row(row_number, slot_data)

        logger.info(f"Cancelled slot {slot_id}: {reason}")

        return {
            "slot_id": slot_id,
            "status": "CANCELLED",
            "reason": reason,
        }

    except Exception as e:
        logger.error(f"Error cancelling slot {slot_id}: {e}")
        raise


def find_patient_appointments(
    patient_first_name: str | None = None,
    patient_last_name: str | None = None,
    patient_phone: str | None = None,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Find appointments by patient information.
    
    Use this when a patient calls to cancel or reschedule and you need to find
    their appointment. Patients don't know their slot_id, so use their name,
    phone number, or appointment date to look it up.
    
    Args:
        patient_first_name: Patient's first name (optional)
        patient_last_name: Patient's last name (optional)
        patient_phone: Patient's phone number (optional)
        date: Filter by appointment date in YYYY-MM-DD format (optional)
    
    Returns:
        List of appointment dictionaries with slot_id, patient info, and appointment details.
        Returns empty list if no appointments found.
    """
    try:
        client = get_sheets_client()
        
        if not any([patient_first_name, patient_last_name, patient_phone]):
            raise ValueError(
                "At least one of patient_first_name, patient_last_name, or patient_phone must be provided"
            )
        
        matches = client.find_appointments_by_patient(
            patient_first_name=patient_first_name,
            patient_last_name=patient_last_name,
            patient_phone=patient_phone,
            date=date,
            status="BOOKED",
        )
        
        # Convert to list of dicts with relevant info
        result = []
        for row_number, slot_data in matches:
            result.append({
                "slot_id": slot_data.get("slot_id"),
                "patient_first_name": slot_data.get("patient_first_name"),
                "patient_last_name": slot_data.get("patient_last_name"),
                "patient_phone": slot_data.get("patient_phone"),
                "provider_name": slot_data.get("provider_name"),
                "appt_type": slot_data.get("appt_type"),
                "start_datetime_local": slot_data.get("start_datetime_local"),
                "end_datetime_local": slot_data.get("end_datetime_local"),
                "status": slot_data.get("status"),
            })
        
        logger.info(f"Found {len(result)} appointments for patient")
        return result
    
    except Exception as e:
        logger.error(f"Error finding patient appointments: {e}")
        raise


def reschedule_slot(
    old_slot_id: str,
    new_slot_id: str,
    reason: str,
    patient: dict[str, Any] | None = None,
    patient_data: dict[str, Any] | None = None,
    verification_result: VerificationResult | None = None,
) -> dict[str, Any]:
    """Reschedule an appointment by booking a new slot and cancelling the old one.

    Args:
        old_slot_id: The currently booked slot ID
        new_slot_id: The new slot ID to book
        reason: Reason for rescheduling
        patient: Patient information dictionary

    Returns:
        Confirmation dictionary with both old and new slot info

    Raises:
        ValueError: If booking new slot fails or old slot cancellation fails
    """
    try:
        # Get patient info from old slot if not provided
        if not patient:
            client = get_sheets_client()
            old_result = client.find_row_by_slot_id(old_slot_id)
            if old_result:
                _, old_slot_data = old_result
                patient = {
                    "first_name": old_slot_data.get("patient_first_name", ""),
                    "last_name": old_slot_data.get("patient_last_name", ""),
                    "phone": old_slot_data.get("patient_phone", ""),
                    "email": old_slot_data.get("patient_email", ""),
                    "type": old_slot_data.get("patient_type", "EXISTING"),
                }

        # Book new slot first
        new_booking = book_slot(
            slot_id=new_slot_id,
            patient=patient,
            reason_for_visit="Rescheduled appointment",
            urgency_level="ROUTINE",
        )

        # Cancel old slot (verification already done above)
        cancel_info = cancel_slot(
            old_slot_id,
            reason,
            patient_data=patient_data,
            verification_result=verification_result,
        )

        logger.info(f"Rescheduled from {old_slot_id} to {new_slot_id}")

        return {
            "old_slot": cancel_info,
            "new_slot": new_booking,
            "status": "RESCHEDULED",
        }

    except Exception as e:
        logger.error(f"Error rescheduling slot: {e}")
        # If new booking succeeded but old cancellation failed, we have a problem
        # For now, just raise the error
        raise
