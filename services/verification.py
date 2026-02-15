"""Identity verification system for patient actions."""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("verification")


class VerificationLevel(Enum):
    """Verification levels for patient actions."""
    LEVEL_0 = 0  # New patient - no verification needed
    LEVEL_1 = 1  # Existing patient, low-risk - name + DOB OR name + phone
    LEVEL_2 = 2  # Existing patient, sensitive - name + DOB + phone OR OTP
    LEVEL_3 = 3  # Suspicious/high-risk - escalate to human


class ActionType(Enum):
    """Types of actions patients can take."""
    BOOK_NEW = "book_new"  # Level 0
    LOOKUP_APPOINTMENT = "lookup_appointment"  # Level 1
    CANCEL_APPOINTMENT = "cancel_appointment"  # Level 2
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"  # Level 2


def get_verification_level(action: ActionType) -> VerificationLevel:
    """Get the required verification level for an action."""
    mapping = {
        ActionType.BOOK_NEW: VerificationLevel.LEVEL_0,
        ActionType.LOOKUP_APPOINTMENT: VerificationLevel.LEVEL_1,
        ActionType.CANCEL_APPOINTMENT: VerificationLevel.LEVEL_2,
        ActionType.RESCHEDULE_APPOINTMENT: VerificationLevel.LEVEL_2,
    }
    return mapping.get(action, VerificationLevel.LEVEL_2)


class VerificationResult:
    """Result of a verification attempt."""

    def __init__(
        self,
        verified: bool,
        level: VerificationLevel,
        missing_fields: list[str] | None = None,
        error_message: str | None = None,
        requires_otp: bool = False,
        requires_escalation: bool = False,
    ):
        self.verified = verified
        self.level = level
        self.missing_fields = missing_fields or []
        self.error_message = error_message
        self.requires_otp = requires_otp
        self.requires_escalation = requires_escalation

    def __bool__(self) -> bool:
        return self.verified


def verify_patient_identity(
    action: ActionType,
    patient_data: dict[str, Any],
    stored_patient_data: dict[str, Any] | None = None,
    failed_attempts: int = 0,
) -> VerificationResult:
    """Verify patient identity based on action type and provided data.

    Args:
        action: The action the patient wants to perform
        patient_data: Patient information provided (name, phone, DOB, etc.)
        stored_patient_data: Stored patient data from the system (for comparison)
        failed_attempts: Number of previous failed verification attempts

    Returns:
        VerificationResult indicating if verification passed and what's needed
    """
    level = get_verification_level(action)

    # Level 3: Escalate if too many failed attempts
    if failed_attempts >= 3:
        logger.warning(f"Too many failed verification attempts ({failed_attempts}), escalating")
        return VerificationResult(
            verified=False,
            level=VerificationLevel.LEVEL_3,
            requires_escalation=True,
            error_message="For security, I'll transfer you to the front desk.",
        )

    # Level 0: New patient booking - no verification needed
    if level == VerificationLevel.LEVEL_0:
        return VerificationResult(verified=True, level=level)

    # Level 1: Low-risk action - name + DOB OR name + phone
    if level == VerificationLevel.LEVEL_1:
        first_name = patient_data.get("first_name", "").strip()
        last_name = patient_data.get("last_name", "").strip()
        phone = patient_data.get("phone", "").strip()
        dob = patient_data.get("date_of_birth", "").strip()

        # Check if we have name + DOB
        if first_name and last_name and dob:
            if stored_patient_data:
                # Verify against stored data
                stored_first = stored_patient_data.get("patient_first_name", "").strip()
                stored_last = stored_patient_data.get("patient_last_name", "").strip()
                stored_dob = stored_patient_data.get("patient_date_of_birth", "").strip()

                if (
                    first_name.lower() == stored_first.lower()
                    and last_name.lower() == stored_last.lower()
                    and dob == stored_dob
                ):
                    return VerificationResult(verified=True, level=level)
                else:
                    return VerificationResult(
                        verified=False,
                        level=level,
                        error_message="The information provided doesn't match our records.",
                    )

            # If no stored data to compare, accept it (first time lookup)
            return VerificationResult(verified=True, level=level)

        # Check if we have name + phone
        if first_name and last_name and phone:
            if stored_patient_data:
                # Verify against stored data
                stored_first = stored_patient_data.get("patient_first_name", "").strip()
                stored_last = stored_patient_data.get("patient_last_name", "").strip()
                stored_phone = stored_patient_data.get("patient_phone", "").strip()

                # Normalize phone numbers for comparison
                normalized_phone = "".join(c for c in phone if c.isdigit())
                normalized_stored = "".join(c for c in stored_phone if c.isdigit())

                if (
                    first_name.lower() == stored_first.lower()
                    and last_name.lower() == stored_last.lower()
                    and normalized_phone == normalized_stored
                ):
                    return VerificationResult(verified=True, level=level)
                else:
                    return VerificationResult(
                        verified=False,
                        level=level,
                        error_message="The information provided doesn't match our records.",
                    )

            # If no stored data to compare, accept it (first time lookup)
            return VerificationResult(verified=True, level=level)

        # Missing required fields
        missing = []
        if not first_name:
            missing.append("first name")
        if not last_name:
            missing.append("last name")
        if not dob and not phone:
            missing.append("date of birth or phone number")

        return VerificationResult(
            verified=False,
            level=level,
            missing_fields=missing,
            error_message=f"Please provide your {' and '.join(missing)} to verify your identity.",
        )

    # Level 2: Sensitive action - (phone + DOB) OR (phone + email) OR OTP
    if level == VerificationLevel.LEVEL_2:
        first_name = patient_data.get("first_name", "").strip()
        last_name = patient_data.get("last_name", "").strip()
        phone = patient_data.get("phone", "").strip()
        dob = patient_data.get("date_of_birth", "").strip()
        otp_code = patient_data.get("otp_code", "").strip()

        # Option 1: OTP verification (preferred)
        if otp_code:
            # TODO: Implement OTP verification
            # For now, we'll check if OTP was requested and is valid
            otp_requested = patient_data.get("otp_requested", False)
            if otp_requested:
                # In real implementation, verify OTP against stored code and expiration
                # For now, accept any 6-digit code as valid (you'll implement real OTP later)
                if len(otp_code) == 6 and otp_code.isdigit():
                    return VerificationResult(verified=True, level=level, requires_otp=True)
                else:
                    return VerificationResult(
                        verified=False,
                        level=level,
                        requires_otp=True,
                        error_message="Invalid OTP code. Please check and try again.",
                    )

        # Option 2: phone + DOB (Kairos requirement)
        if phone and dob:
            if stored_patient_data:
                # Check both phone_e164 and patient_phone fields
                stored_phone = stored_patient_data.get("phone_e164", stored_patient_data.get("patient_phone", "")).strip()
                stored_dob = stored_patient_data.get("dob", stored_patient_data.get("patient_date_of_birth", "")).strip()

                # Normalize phone numbers
                normalized_phone = "".join(c for c in phone if c.isdigit())
                normalized_stored = "".join(c for c in stored_phone if c.isdigit())

                if normalized_phone == normalized_stored and dob == stored_dob:
                    return VerificationResult(verified=True, level=level)
                else:
                    return VerificationResult(
                        verified=False,
                        level=level,
                        error_message="The phone number and date of birth don't match our records. Would you like to receive an OTP code via SMS instead?",
                    )

            # If no stored data, we can't verify - need to find the appointment first
            return VerificationResult(
                verified=False,
                level=level,
                error_message="I need to find your appointment first. Please provide your phone number and date of birth.",
            )

        # Option 3: phone + email (Kairos requirement)
        email = patient_data.get("email", "").strip()
        if phone and email:
            if stored_patient_data:
                stored_phone = stored_patient_data.get("phone_e164", stored_patient_data.get("patient_phone", "")).strip()
                stored_email = stored_patient_data.get("email", "").strip()

                # Normalize phone numbers
                normalized_phone = "".join(c for c in phone if c.isdigit())
                normalized_stored = "".join(c for c in stored_phone if c.isdigit())

                if normalized_phone == normalized_stored and email.lower() == stored_email.lower():
                    return VerificationResult(verified=True, level=level)
                else:
                    return VerificationResult(
                        verified=False,
                        level=level,
                        error_message="The phone number and email don't match our records. Would you like to receive an OTP code via SMS instead?",
                    )

            # If no stored data, we can't verify
            return VerificationResult(
                verified=False,
                level=level,
                error_message="I need to find your appointment first. Please provide your phone number and email.",
            )

        # Missing required fields - Kairos requires (phone + DOB) OR (phone + email)
        missing = []
        if not phone:
            missing.append("phone number")
        if not dob and not patient_data.get("email"):
            missing.append("date of birth or email")

        error_msg = "For security, I need your phone number and either your date of birth or email address. Alternatively, I can send you an OTP code via SMS."
        if missing:
            error_msg = f"For security, I need your {' and '.join(missing)}. Alternatively, I can send you an OTP code via SMS."

        return VerificationResult(
            verified=False,
            level=level,
            missing_fields=missing,
            error_message=error_msg,
        )

    # Default: require escalation
    return VerificationResult(
        verified=False,
        level=VerificationLevel.LEVEL_3,
        requires_escalation=True,
        error_message="For security, I'll transfer you to the front desk.",
    )


def should_escalate(verification_result: VerificationResult) -> bool:
    """Check if the verification result requires escalation to human."""
    return verification_result.requires_escalation or verification_result.level == VerificationLevel.LEVEL_3
