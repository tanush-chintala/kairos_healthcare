import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import Kairos booking tools
from services.kairos_booking_tools import (
    book_appointment,
    cancel_appointment,
    find_openings,
    find_patient_appointments_by_phone,
    get_day_view,
    reschedule_appointment,
    upsert_patient,
)
from services.verification import (
    ActionType,
    VerificationLevel,
    VerificationResult,
    verify_patient_identity,
    should_escalate,
)

logger = logging.getLogger("basic-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(
        self,
        dental_office_name: str = "Kairos",
        greeting: str | None = None,
    ) -> None:
        """Initialize dental assistant agent.

        Args:
            dental_office_name: Name of the dental office
            greeting: Custom greeting message. If None, uses default greeting.
        """
        self.dental_office_name = dental_office_name
        self.greeting = greeting or f"Welcome to {dental_office_name}. How may I help you today?"

        super().__init__(
            instructions=(
                f"You are a professional dental front office assistant for {dental_office_name}. "
                "You interact with patients via voice, so keep your responses concise and clear. "
                "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
                "Your primary responsibility is to help patients book, cancel, or reschedule dental appointments. "
                "\n"
                "CRITICAL DATE CONTEXT:\n"
                "IMPORTANT: When patients mention dates without specifying a year (e.g., 'February sixteenth'), "
                "you MUST interpret them as dates in the year 2026. All appointments in the system are scheduled for 2026. "
                "For example, 'February 16th' should be converted to '2026-02-16', NOT '2024-02-16'. "
                "Always use 2026 as the default year when converting spoken dates internally. "
                "Never ask patients to provide dates in a specific format - accept their natural date expressions.\n"
                "\n"
                "CRITICAL RULES - YOU MUST FOLLOW THESE STRICTLY:\n"
                "1. NEVER make up, invent, or hallucinate appointment openings, row IDs, appointment IDs, dates, times, or any appointment details.\n"
                "2. ONLY use appointment data that is returned from the find_openings tool. If no openings are found, tell the patient there are no available appointments.\n"
                "3. ONLY book appointments using opening_row_id values that were returned from find_openings. Never use a row_id that you made up.\n"
                "4. If find_openings returns an empty list, you MUST tell the patient there are no available appointments. Do NOT make up slots.\n"
                "5. If a patient asks about appointments but you haven't called find_openings yet, you MUST call find_openings first before mentioning any appointments.\n"
                "6. When presenting available openings to the patient, ONLY mention openings that were returned from find_openings. Read the exact row_id, date, time, and provider name from the tool response.\n"
                "7. If a booking fails (e.g., opening not found or already booked), explain the error to the patient. Do NOT make up alternative openings.\n"
                "\n"
                "When booking an appointment:\n"
                "1. Ask what type of appointment they need (Cleaning, Filling, LimitedExam, etc.)\n"
                "2. Ask for their preferred date range naturally (e.g., 'What dates work for you?' or 'When would you like to schedule?'). "
                "Accept dates in any natural format they provide (e.g., 'February 16th', 'next Monday', 'the 20th').\n"
                "3. REMEMBER: Convert all spoken dates to 2026 year format internally (e.g., 'February 16th' = '2026-02-16'). "
                "Never mention date formats to the patient - just accept their natural date expressions.\n"
                "4. ALWAYS call find_openings with date_start and date_end (in YYYY-MM-DD format) to get REAL available openings from the system\n"
                "5. Present ONLY the openings returned from find_openings to the patient\n"
                "6. Let them choose an opening from the REAL options you received\n"
                "7. Collect their information: first name, last name, phone number (E.164 format: +1234567890), appointment type, and reason for visit\n"
                "8. Optionally collect email and date of birth (recommended for future verification)\n"
                "9. Use book_appointment with the EXACT opening_row_id from find_openings to confirm the appointment\n"
                "10. Verbally confirm the appointment details back to them using the data returned from book_appointment\n"
                "\n"
                "When cancelling or rescheduling:\n"
                "- Patients don't know their appointment_id or row_id - these are internal identifiers\n"
                "- Ask for their phone number (primary lookup key in E.164 format: +1234567890) to find their appointment\n"
                "- Use find_patient_appointments_by_phone to find their appointment(s) by phone number\n"
                "- Once you find their appointment, you'll get the appointment_id and row_id to use for cancel or reschedule\n"
                "- SECURITY: For existing patients, verify identity using (phone + DOB) OR (phone + email). If missing, escalate to human.\n"
                "- For rescheduling, you MUST call find_openings first to get available openings, then let them choose from the real options\n"
                "- Only use row_id values that were returned from find_openings or find_patient_appointments_by_phone\n"
                "\n"
                "Always confirm important details like dates, times, patient names, and phone numbers. "
                "Be friendly, professional, and helpful. You will speak english to the user."
            ),
        )

    async def on_enter(self):
        # Warm greeting when the agent first starts
        # Keep it uninterruptible so the client has time to calibrate AEC (Acoustic Echo Cancellation).
        self.session.generate_reply(
            instructions=f"Greet the caller warmly by saying: '{self.greeting}'",
            allow_interruptions=False,
        )

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def find_openings(
        self,
        context: RunContext,
        date_start: str,
        date_end: str,
        appt_type: str | None = None,
        duration_min: int | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find available appointment openings in Dr-Chair lane.

        CRITICAL: This is the ONLY source of appointment data. You MUST use this tool before
        mentioning any appointments to the patient. NEVER make up or invent appointment slots.

        Use this when the patient wants to see available appointment times.
        Ask the patient what type of appointment they need (e.g., Cleaning, Filling, LimitedExam)
        and their preferred date range.

        Args:
            date_start: Start date in YYYY-MM-DD format (required)
            date_end: End date in YYYY-MM-DD format (required, inclusive)
            appt_type: Type of appointment (e.g., "Cleaning", "Filling", "LimitedExam") (optional)
            duration_min: Duration in minutes (e.g., 30, 60) (optional)
            limit: Maximum number of slots to return (default: 5)

        Returns:
            List of available openings with row_id, slot_key, date_local, start_time_local,
            end_time_local, appt_type, duration_min, provider_name. If the list is empty, there are
            NO available appointments - you MUST tell the patient this and NOT make up any slots.

        IMPORTANT: If this returns an empty list, you MUST tell the patient there are no
        available appointments. Do NOT invent or make up slots.
        """
        logger.info(
            f"Finding openings: date_start={date_start}, date_end={date_end}, "
            f"appt_type={appt_type}, duration_min={duration_min}, limit={limit}"
        )
        try:
            openings = find_openings(
                date_start=date_start,
                date_end=date_end,
                appt_type=appt_type,
                duration_min=duration_min,
                limit=limit,
            )
            if not openings:
                logger.warning("No openings found - agent must inform patient, not make up slots")
            return openings
        except Exception as e:
            logger.error(f"Error finding openings: {e}")
            return []

    @function_tool
    async def find_patient_appointments_by_phone(
        self,
        context: RunContext,
        phone_e164: str,
        date: str | None = None,
    ) -> list[dict]:
        """Find a patient's existing appointments by their phone number.

        CRITICAL: Patients don't know their appointment_id or row_id - these are internal identifiers.
        Use this tool when a patient calls to cancel or reschedule their appointment.
        You need to look up their appointment using their phone number (primary lookup key).

        Use this when:
        - A patient wants to cancel their appointment
        - A patient wants to reschedule their appointment
        - A patient asks about their existing appointment

        Ask the patient for their phone number. Optionally ask for the appointment date if they know it.

        Args:
            phone_e164: Patient's phone number in E.164 format (e.g., +1234567890) (required)
            date: Appointment date in YYYY-MM-DD format (optional, helps narrow down results)

        Returns:
            List of appointment dictionaries with appointment_id, row_id, patient_id, date_local,
            start_time_local, end_time_local, appt_type, provider_name.
            If empty list, the patient has no appointments matching the criteria.
            Use the appointment_id or row_id from the results for cancel_appointment or reschedule_appointment.
        """
        logger.info(f"Finding appointments for phone: {phone_e164}, date: {date}")
        try:
            appointments = find_patient_appointments_by_phone(phone_e164=phone_e164, date=date)
            return appointments
        except Exception as e:
            logger.error(f"Error finding patient appointments: {e}")
            raise

    @function_tool
    async def book_appointment(
        self,
        context: RunContext,
        opening_row_id: str,
        patient_first_name: str,
        patient_last_name: str,
        phone_e164: str,
        appt_type: str,
        reason_for_visit: str,
        patient_email: str | None = None,
        patient_dob: str | None = None,
        urgency_level: str = "ROUTINE",
        triage_red_flags: str = "N",
    ) -> dict:
        """Book an appointment in the Dr-Chair lane.

        CRITICAL: You MUST only use opening_row_id values that were returned from find_openings.
        NEVER use a row_id that you made up or invented. If the booking fails, explain the
        error to the patient - do NOT make up alternative slots.

        This function will:
        1. Upsert the patient (find by phone_e164, create if new, update if existing)
        2. Book the appointment using the opening_row_id

        Use this after the patient has selected an opening from find_openings.
        Collect the patient's information: first name, last name, phone number (E.164 format),
        appointment type, and reason for visit.

        Args:
            opening_row_id: The EXACT row_id to book (MUST be from find_openings response, never made up)
            patient_first_name: Patient's first name (required)
            patient_last_name: Patient's last name (required)
            phone_e164: Patient's phone number in E.164 format, e.g., +1234567890 (required)
            appt_type: Appointment type (e.g., "Cleaning", "Filling", "LimitedExam") (required)
            reason_for_visit: Reason for the appointment (required)
            patient_email: Patient's email (optional)
            patient_dob: Patient's date of birth in YYYY-MM-DD format (optional, recommended)
            urgency_level: "ROUTINE", "SOON", or "URGENT" (default: "ROUTINE")
            triage_red_flags: "Y" or "N" (default: "N")

        Returns:
            Confirmation with appointment_id, row_id, patient_id, date, time, and appointment details.
            If booking fails, an error will be raised. You must explain the error to the patient.
        """
        logger.info(
            f"Booking appointment: opening_row_id={opening_row_id}, "
            f"patient={patient_first_name} {patient_last_name}, phone={phone_e164}"
        )
        try:
            # Upsert patient first
            patient_payload = {
                "first_name": patient_first_name,
                "last_name": patient_last_name,
                "phone_e164": phone_e164,
                "email": patient_email or "",
                "dob": patient_dob or "",
                "patient_type": "EXISTING",  # Will be determined by upsert_patient
            }
            patient_id = upsert_patient(patient_payload)

            # Get conversation/room ID from session if available
            conversation_id = None
            try:
                if hasattr(context, "session") and hasattr(context.session, "_room"):
                    conversation_id = context.session._room.name
            except Exception:
                pass

            # Book the appointment
            result = book_appointment(
                opening_row_id=opening_row_id,
                patient_id=patient_id,
                appt_type=appt_type,
                reason_for_visit=reason_for_visit,
                urgency_level=urgency_level,
                triage_red_flags=triage_red_flags,
                conversation_id=conversation_id,
            )
            return result
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            raise

    @function_tool
    async def verify_patient_identity(
        self,
        context: RunContext,
        action: str,
        patient_first_name: str | None = None,
        patient_last_name: str | None = None,
        patient_phone: str | None = None,
        patient_date_of_birth: str | None = None,
        otp_code: str | None = None,
        slot_id: str | None = None,
    ) -> dict:
        """Verify patient identity before sensitive actions like canceling or rescheduling.

        CRITICAL: You MUST verify patient identity before canceling or rescheduling appointments.
        This is a security requirement.

        Verification levels:
        - Level 0 (book_new): No verification needed for new patients
        - Level 1 (lookup_appointment): Name + DOB OR Name + Phone
        - Level 2 (cancel/reschedule): Name + DOB + Phone OR OTP code
        - Level 3: Escalate to human (after 3 failed attempts)

        Args:
            action: Action type - "book_new", "lookup_appointment", "cancel_appointment", or "reschedule_appointment"
            patient_first_name: Patient's first name
            patient_last_name: Patient's last name
            patient_phone: Patient's phone number
            patient_date_of_birth: Patient's date of birth (YYYY-MM-DD format)
            otp_code: OTP code if using SMS verification (6 digits)
            slot_id: Optional slot_id to get stored patient data for comparison

        Returns:
            Verification result with verified status, level, and any error messages or missing fields
        """
        logger.info(f"Verifying identity for action: {action}")
        try:
            # Map action string to ActionType
            action_map = {
                "book_new": ActionType.BOOK_NEW,
                "lookup_appointment": ActionType.LOOKUP_APPOINTMENT,
                "cancel_appointment": ActionType.CANCEL_APPOINTMENT,
                "reschedule_appointment": ActionType.RESCHEDULE_APPOINTMENT,
            }
            action_type = action_map.get(action)
            if not action_type:
                raise ValueError(f"Invalid action: {action}")

            patient_data = {
                "first_name": patient_first_name or "",
                "last_name": patient_last_name or "",
                "phone": patient_phone or "",
                "date_of_birth": patient_date_of_birth or "",
                "otp_code": otp_code or "",
                "otp_requested": bool(otp_code),
            }

            # Get stored patient data if appointment_id or row_id provided
            stored_data = None
            if slot_id:  # slot_id can be appointment_id or row_id
                from services.kairos_sheets_client import KairosSheetsClient
                client = KairosSheetsClient()
                # Try as appointment_id first
                result = client.find_row_by_appointment_id(slot_id)
                if not result:
                    # Try as row_id
                    result = client.find_row_by_row_id(slot_id)
                if result:
                    _, row_data = result
                    # Get patient data
                    patient_id = row_data.get("patient_id")
                    if patient_id:
                        patient_result = client.find_patient_by_id(patient_id)
                        if patient_result:
                            _, stored_data = patient_result

            verification_result = verify_patient_identity(
                action_type, patient_data, stored_patient_data=stored_data
            )

            return {
                "verified": verification_result.verified,
                "level": verification_result.level.value,
                "missing_fields": verification_result.missing_fields,
                "error_message": verification_result.error_message,
                "requires_otp": verification_result.requires_otp,
                "requires_escalation": verification_result.requires_escalation,
            }
        except Exception as e:
            logger.error(f"Error verifying identity: {e}")
            raise

    @function_tool
    async def cancel_appointment(
        self,
        context: RunContext,
        appointment_id: str | None = None,
        row_id: str | None = None,
        cancel_reason: str = "",
        phone_e164: str | None = None,
        patient_dob: str | None = None,
        patient_email: str | None = None,
    ) -> dict:
        """Cancel an existing appointment.

        CRITICAL: Patients don't know their appointment_id or row_id - these are internal identifiers.
        If you don't have these yet, you MUST first use find_patient_appointments_by_phone
        to look up their appointment by phone number. Then use the appointment_id or row_id from
        the results. Never make up IDs.

        SECURITY: For existing patients, you MUST verify identity using (phone + DOB) OR (phone + email).
        If verification fails, escalate to human.

        Use this when the patient wants to cancel their appointment.
        Ask for the reason for cancellation.

        Args:
            appointment_id: The appointment ID to cancel (e.g., A-000901) (optional if row_id provided)
            row_id: The row ID to cancel (e.g., IDX-0001) (optional if appointment_id provided)
            cancel_reason: Reason for cancellation (required)
            phone_e164: Patient's phone number in E.164 format for verification (required)
            patient_dob: Patient's date of birth in YYYY-MM-DD format for verification (required if no email)
            patient_email: Patient's email for verification (required if no DOB)

        Returns:
            Confirmation of cancellation. If cancellation fails or verification fails, an error will be raised.
        """
        logger.info(f"Cancelling appointment: appointment_id={appointment_id}, row_id={row_id}, reason={cancel_reason}")
        try:
            # Get conversation/room ID from session if available
            conversation_id = None
            try:
                if hasattr(context, "session") and hasattr(context.session, "_room"):
                    conversation_id = context.session._room.name
            except Exception:
                pass

            # Prepare patient data for verification
            patient_data = None
            if phone_e164:
                patient_data = {
                    "phone": phone_e164,
                    "date_of_birth": patient_dob or "",
                    "email": patient_email or "",
                }

            result = cancel_appointment(
                appointment_id=appointment_id,
                row_id=row_id,
                cancel_reason=cancel_reason,
                conversation_id=conversation_id,
                patient_data=patient_data,
            )
            return result
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            raise

    @function_tool
    async def reschedule_appointment(
        self,
        context: RunContext,
        old_identifier: str,
        new_opening_row_id: str,
        cancel_reason: str = "Rescheduled",
        phone_e164: str | None = None,
        patient_dob: str | None = None,
        patient_email: str | None = None,
    ) -> dict:
        """Reschedule an existing appointment to a new time.

        CRITICAL: Patients don't know their appointment_id or row_id - these are internal identifiers.
        If you don't have the old_identifier yet, you MUST first use find_patient_appointments_by_phone
        to look up their appointment by phone number. The new_opening_row_id MUST be from find_openings.
        Never make up or invent IDs.

        SECURITY: For existing patients, you MUST verify identity using (phone + DOB) OR (phone + email).
        If verification fails, escalate to human.

        Use this when the patient wants to change their appointment time.
        1. First use find_patient_appointments_by_phone to find their current appointment (if you don't have identifier)
        2. Then use find_openings to get available openings for the new time
        3. Let them pick a new time from the REAL available openings
        4. The system will automatically cancel the old appointment and book the new one

        Args:
            old_identifier: The appointment ID (A-xxxxxx) or row_id (IDX-xxxxxx) of the appointment to reschedule
            new_opening_row_id: The row_id of the new OPEN slot to book (MUST be from find_openings, never made up)
            cancel_reason: Reason for rescheduling (default: "Rescheduled")
            phone_e164: Patient's phone number in E.164 format for verification (required)
            patient_dob: Patient's date of birth in YYYY-MM-DD format for verification (required if no email)
            patient_email: Patient's email for verification (required if no DOB)

        Returns:
            Confirmation with both old and new appointment details. If rescheduling fails,
            an error will be raised. You must explain the error to the patient.
        """
        logger.info(f"Rescheduling from {old_identifier} to {new_opening_row_id}: {cancel_reason}")
        try:
            # Get conversation/room ID from session if available
            conversation_id = None
            try:
                if hasattr(context, "session") and hasattr(context.session, "_room"):
                    conversation_id = context.session._room.name
            except Exception:
                pass

            # Prepare patient data for verification
            patient_data = None
            if phone_e164:
                patient_data = {
                    "phone": phone_e164,
                    "date_of_birth": patient_dob or "",
                    "email": patient_email or "",
                }

            result = reschedule_appointment(
                old_identifier=old_identifier,
                new_opening_row_id=new_opening_row_id,
                cancel_reason=cancel_reason,
                conversation_id=conversation_id,
                patient_data=patient_data,
            )
            return result
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            raise


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Read metadata from job (set by dispatch layer)
    office_name = "Kairos"
    greeting = None

    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
            office_name = metadata.get("office_name", office_name)
            greeting = metadata.get("greeting")
            logger.info(
                f"Loaded clinic config from metadata: {office_name}",
                extra={"metadata": metadata},
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse job metadata: {e}, using defaults")

    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # Using Deepgram plugin directly to connect to Deepgram API (requires DEEPGRAM_API_KEY env var)
        # This bypasses LiveKit's gateway and avoids quota limits
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # Using OpenAI plugin directly to connect to OpenAI API (requires OPENAI_API_KEY env var)
        # This bypasses LiveKit's gateway and avoids quota limits
        llm=openai.LLM(model="gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # Using Cartesia plugin directly to connect to Cartesia API (requires CARTESIA_API_KEY env var)
        # This bypasses LiveKit's gateway and avoids quota limits
        tts=cartesia.TTS(model="sonic-2", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    # Create agent with clinic-specific configuration
    agent = MyAgent(dental_office_name=office_name, greeting=greeting)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
