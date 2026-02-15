# OTP (One-Time Password) Implementation Guide

This document explains how to implement SMS-based OTP verification for patient identity verification.

## Overview

OTP verification is used for **Level 2** verification (sensitive actions like canceling or rescheduling appointments). It provides a more secure alternative to requiring name + DOB + phone.

## Architecture

### Components Needed

1. **OTP Generation Service**: Generates random 6-digit codes
2. **OTP Storage**: Temporary storage (Redis, in-memory cache, or database) with expiration
3. **SMS Provider**: Service to send SMS messages (Twilio, AWS SNS, etc.)
4. **OTP Verification**: Validates codes and checks expiration

### Flow

```
1. Patient requests to cancel/reschedule
2. Agent asks: "For security, I can send you a verification code via SMS. What's your phone number?"
3. Patient provides phone number
4. System generates 6-digit OTP code
5. System stores OTP with:
   - Phone number
   - Expiration time (5-10 minutes)
   - Attempt counter
6. System sends SMS via provider
7. Agent asks: "I've sent a code to [phone]. Please enter the 6-digit code."
8. Patient provides code
9. System verifies:
   - Code matches
   - Not expired
   - Attempts < 3
10. If valid: Proceed with action
    If invalid: Increment attempts, ask again or escalate
```

## Implementation Steps

### 1. Add OTP Service

Create `services/otp_service.py`:

```python
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

# In-memory storage (use Redis in production)
_otp_store: dict[str, dict] = {}


def generate_otp(phone: str, expiration_minutes: int = 10) -> str:
    """Generate a 6-digit OTP and store it.
    
    Args:
        phone: Phone number to send OTP to
        expiration_minutes: How long OTP is valid (default: 10)
    
    Returns:
        6-digit OTP code
    """
    # Generate random 6-digit code
    code = f"{secrets.randbelow(1000000):06d}"
    
    # Store with expiration
    _otp_store[phone] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=expiration_minutes),
        "attempts": 0,
        "created_at": datetime.now(),
    }
    
    return code


def verify_otp(phone: str, code: str) -> tuple[bool, str]:
    """Verify an OTP code.
    
    Args:
        phone: Phone number
        code: OTP code to verify
    
    Returns:
        (is_valid, error_message)
    """
    if phone not in _otp_store:
        return False, "No OTP found for this phone number. Please request a new code."
    
    stored = _otp_store[phone]
    
    # Check expiration
    if datetime.now() > stored["expires_at"]:
        del _otp_store[phone]
        return False, "OTP code has expired. Please request a new code."
    
    # Check attempts
    if stored["attempts"] >= 3:
        del _otp_store[phone]
        return False, "Too many failed attempts. Please request a new code."
    
    # Verify code
    if code != stored["code"]:
        stored["attempts"] += 1
        remaining = 3 - stored["attempts"]
        return False, f"Invalid code. {remaining} attempts remaining."
    
    # Valid - clean up
    del _otp_store[phone]
    return True, "Verified"
```

### 2. Add SMS Service

Create `services/sms_service.py`:

```python
import os
from typing import Optional

# Example using Twilio (install: pip install twilio)
from twilio.rest import Client

def send_otp_sms(phone: str, code: str) -> bool:
    """Send OTP code via SMS.
    
    Args:
        phone: Phone number (E.164 format: +1234567890)
        code: OTP code to send
    
    Returns:
        True if sent successfully, False otherwise
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    
    if not all([account_sid, auth_token, from_number]):
        raise ValueError("Twilio credentials not configured")
    
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=f"Your verification code is {code}. It expires in 10 minutes.",
            from_=from_number,
            to=phone,
        )
        return message.sid is not None
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        return False
```

### 3. Update Verification Service

Update `services/verification.py` to integrate OTP:

```python
from services.otp_service import generate_otp, verify_otp
from services.sms_service import send_otp_sms

# In verify_patient_identity, for Level 2:
if level == VerificationLevel.LEVEL_2:
    # ... existing code ...
    
    # Check if OTP was requested
    if patient_data.get("otp_requested") and not patient_data.get("otp_code"):
        # Generate and send OTP
        phone = patient_data.get("phone", "").strip()
        if phone:
            otp_code = generate_otp(phone)
            if send_otp_sms(phone, otp_code):
                return VerificationResult(
                    verified=False,
                    level=level,
                    requires_otp=True,
                    error_message=f"I've sent a verification code to {phone}. Please enter the 6-digit code.",
                )
            else:
                return VerificationResult(
                    verified=False,
                    level=level,
                    error_message="Failed to send SMS. Please try again or use name + DOB + phone verification.",
                )
    
    # Verify OTP if provided
    if patient_data.get("otp_code"):
        phone = patient_data.get("phone", "").strip()
        code = patient_data.get("otp_code", "").strip()
        is_valid, error_msg = verify_otp(phone, code)
        if is_valid:
            return VerificationResult(verified=True, level=level, requires_otp=True)
        else:
            return VerificationResult(
                verified=False,
                level=level,
                requires_otp=True,
                error_message=error_msg,
            )
```

### 4. Add Agent Tool for OTP

Add to `examples/voice_agents/basic_agent.py`:

```python
@function_tool
async def request_otp(
    self,
    context: RunContext,
    patient_phone: str,
) -> dict:
    """Request an OTP code to be sent via SMS for identity verification.
    
    Use this when a patient wants to cancel or reschedule and prefers
    SMS verification over providing name + DOB + phone.
    
    Args:
        patient_phone: Patient's phone number
    
    Returns:
        Confirmation that OTP was sent
    """
    from services.otp_service import generate_otp
    from services.sms_service import send_otp_sms
    
    try:
        code = generate_otp(patient_phone)
        success = send_otp_sms(patient_phone, code)
        
        if success:
            return {
                "status": "sent",
                "message": f"Verification code sent to {patient_phone}",
            }
        else:
            return {
                "status": "failed",
                "message": "Failed to send SMS. Please try again.",
            }
    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        raise
```

## Alternative SMS Providers

### AWS SNS
```python
import boto3

def send_otp_sms_aws(phone: str, code: str) -> bool:
    sns = boto3.client('sns', region_name='us-east-1')
    response = sns.publish(
        PhoneNumber=phone,
        Message=f"Your verification code is {code}. It expires in 10 minutes.",
    )
    return response['MessageId'] is not None
```

### Vonage (Nexmo)
```python
from vonage import Sms

def send_otp_sms_vonage(phone: str, code: str) -> bool:
    client = Sms(key=os.getenv("VONAGE_API_KEY"), secret=os.getenv("VONAGE_API_SECRET"))
    response = client.send_message({
        "from": os.getenv("VONAGE_FROM_NUMBER"),
        "to": phone,
        "text": f"Your verification code is {code}. It expires in 10 minutes.",
    })
    return response['messages'][0]['status'] == '0'
```

## Production Considerations

1. **Use Redis** instead of in-memory storage for OTP codes (supports multiple workers)
2. **Rate limiting**: Limit OTP requests per phone number (e.g., 3 per hour)
3. **Phone number validation**: Validate format before sending
4. **Error handling**: Graceful fallback if SMS fails
5. **Logging**: Log all OTP generation and verification attempts
6. **Security**: Don't log actual OTP codes
7. **Cost**: Monitor SMS costs (Twilio ~$0.0075 per SMS)

## Environment Variables

Add to `.env`:

```bash
# Twilio (example)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Or AWS SNS
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
```

## Testing

For development/testing, you can use a mock SMS service that logs codes instead of sending:

```python
def send_otp_sms_mock(phone: str, code: str) -> bool:
    """Mock SMS service that logs codes for testing."""
    logger.info(f"[MOCK SMS] Code {code} for {phone}")
    print(f"\n[MOCK SMS] Verification code for {phone}: {code}\n")
    return True
```
