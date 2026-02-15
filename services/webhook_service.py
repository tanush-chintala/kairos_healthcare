"""FastAPI webhook service for handling incoming calls and dispatching agents."""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request
from livekit import api
from pydantic import BaseModel

from services.config import AGENT_NAME, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL
from services.database import get_db

logger = logging.getLogger("webhook-service")
logger.setLevel(logging.INFO)

app = FastAPI(title="Dental Assistant Webhook Service")


class IncomingCallRequest(BaseModel):
    """Request model for incoming call webhook."""

    to_number: str | None = None
    from_number: str | None = None
    clinic_id: str | None = None
    # Allow additional fields for flexibility
    extra: dict[str, Any] | None = None


class DispatchResponse(BaseModel):
    """Response model for dispatch creation."""

    dispatch_id: str
    room_name: str
    clinic_id: str
    office_name: str


def identify_clinic(request: IncomingCallRequest) -> str | None:
    """Identify clinic from request data.

    Tries in order:
    1. Explicit clinic_id in request
    2. Lookup by phone number (to_number)

    Args:
        request: Incoming call request

    Returns:
        Clinic ID or None if not found
    """
    # First, try explicit clinic_id
    if request.clinic_id:
        return request.clinic_id

    # Then try phone number lookup
    if request.to_number:
        db = get_db()
        clinic = db.get_clinic_by_phone(request.to_number)
        if clinic:
            return clinic["id"]

    return None


@app.post("/webhook/incoming-call", response_model=DispatchResponse)
async def handle_incoming_call(request: IncomingCallRequest) -> DispatchResponse:
    """Handle incoming call and dispatch agent with clinic configuration.

    Args:
        request: Incoming call request data

    Returns:
        Dispatch response with room and clinic info

    Raises:
        HTTPException: If clinic not found or dispatch fails
    """
    # Identify clinic
    clinic_id = identify_clinic(request)
    if not clinic_id:
        raise HTTPException(
            status_code=404,
            detail=f"Clinic not found for phone number: {request.to_number}",
        )

    # Get clinic configuration from database
    db = get_db()
    clinic_config = db.get_clinic_config(clinic_id)
    if not clinic_config:
        raise HTTPException(
            status_code=404, detail=f"Clinic configuration not found: {clinic_id}"
        )

    logger.info(
        f"Processing incoming call for clinic: {clinic_id}",
        extra={"clinic": clinic_config, "request": request.model_dump()},
    )

    # Initialize LiveKit API
    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET",
        )

    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET
    )

    try:
        # Create room
        room_name = f"clinic-{clinic_id}-{str(uuid.uuid4().hex)[:12]}"
        room = await lkapi.room.create_room(api.CreateRoomRequest(name=room_name))
        logger.info(f"Created room: {room_name}")

        # Prepare metadata for agent
        metadata = json.dumps(
            {
                "clinic_id": clinic_id,
                "office_name": clinic_config["office_name"],
                "greeting": clinic_config.get("greeting"),
            }
        )

        # Dispatch agent job with metadata
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
        logger.info(
            f"Created dispatch: {dispatch.id} for agent {AGENT_NAME} in room {room_name}"
        )

        # Note: SIP participant creation would happen here if you have a SIP trunk configured
        # For now, this webhook just creates the dispatch. The actual call connection
        # would be handled by your telephony provider/SIP gateway.

        return DispatchResponse(
            dispatch_id=dispatch.id,
            room_name=room_name,
            clinic_id=clinic_id,
            office_name=clinic_config["office_name"],
        )

    except Exception as e:
        logger.exception(f"Error creating dispatch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create dispatch: {str(e)}")
    finally:
        await lkapi.aclose()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/clinics")
async def list_clinics() -> dict[str, Any]:
    """List all clinics in database (for debugging/admin)."""
    db = get_db()
    clinics = db.list_all_clinics()
    return {"clinics": clinics}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
