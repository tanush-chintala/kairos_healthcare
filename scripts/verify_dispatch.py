"""Script to verify that dispatches are working and agents are connecting to rooms."""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from livekit import api

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


async def verify_dispatch_flow() -> None:
    """Create a dispatch and verify the agent connects."""
    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8000")
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_url, api_key, api_secret]):
        print("❌ Missing LiveKit credentials in environment variables")
        print("   Set: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
        return

    print("=" * 60)
    print("Dispatch Verification Test")
    print("=" * 60)

    # Step 1: Create a dispatch via webhook
    print("\n1. Creating dispatch via webhook...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{webhook_url}/webhook/incoming-call",
                json={
                    "clinic_id": "sunshine-clinic",
                    "from_number": "+1-555-VERIFY",
                },
            )

            if response.status_code != 200:
                print(f"   ❌ Failed to create dispatch: {response.text}")
                return

            data = response.json()
            room_name = data["room_name"]
            dispatch_id = data["dispatch_id"]

            print(f"   ✓ Dispatch created: {dispatch_id}")
            print(f"   ✓ Room name: {room_name}")

        except Exception as e:
            print(f"   ❌ Error creating dispatch: {e}")
            return

    # Step 2: Wait a moment for agent to connect
    print("\n2. Waiting for agent to connect (5 seconds)...")
    await asyncio.sleep(5)

    # Step 3: Check room status via LiveKit API
    print("\n3. Checking room status...")
    lkapi = api.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)

    try:
        # List rooms to find our room
        room_request = api.ListRoomsRequest(names=[room_name])
        rooms_response = await lkapi.room.list_rooms(room_request)

        if not rooms_response.rooms:
            print(f"   ❌ Room {room_name} not found!")
            print("   This could mean:")
            print("     - The room was never created")
            print("     - The room was already deleted")
            return

        room_info = rooms_response.rooms[0]
        print(f"   ✓ Room found: {room_info.name}")
        print(f"   ✓ Room SID: {room_info.sid}")
        print(f"   ✓ Num participants: {room_info.num_participants}")

        # Step 4: List participants in the room
        print("\n4. Checking participants...")
        participants_request = api.ListParticipantsRequest(room=room_name)
        participants_response = await lkapi.room.list_participants(participants_request)

        if not participants_response.participants:
            print("   ⚠️  No participants in room yet")
            print("   This could mean:")
            print("     - Agent hasn't connected yet (wait longer)")
            print("     - Agent server is not running")
            print("     - Agent name mismatch (check AGENT_NAME env var)")
        else:
            print(f"   ✓ Found {len(participants_response.participants)} participant(s):")
            for p in participants_response.participants:
                kind = "AGENT" if p.kind == api.ParticipantKind.PARTICIPANT_KIND_AGENT else "USER"
                print(f"     - {p.identity} ({kind})")

        # Step 5: Check dispatch status
        print("\n5. Checking dispatch status...")
        dispatch_request = api.ListAgentDispatchRequest(agent_name=os.getenv("AGENT_NAME", "dental-assistant"))
        dispatch_response = await lkapi.agent_dispatch.list_agent_dispatch(dispatch_request)

        our_dispatch = None
        for d in dispatch_response.dispatches:
            if d.id == dispatch_id:
                our_dispatch = d
                break

        if our_dispatch:
            print(f"   ✓ Dispatch found: {our_dispatch.id}")
            print(f"   ✓ State: {api.AgentDispatchState.Name(our_dispatch.state)}")
            print(f"   ✓ Room: {our_dispatch.room}")
            print(f"   ✓ Metadata: {our_dispatch.metadata}")
            
            # Parse metadata to verify clinic config
            if our_dispatch.metadata:
                try:
                    metadata = json.loads(our_dispatch.metadata)
                    print(f"\n   Metadata contents:")
                    print(f"     - Clinic ID: {metadata.get('clinic_id')}")
                    print(f"     - Office Name: {metadata.get('office_name')}")
                    print(f"     - Greeting: {metadata.get('greeting', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"     ⚠️  Could not parse metadata: {our_dispatch.metadata}")
        else:
            print(f"   ⚠️  Dispatch {dispatch_id} not found in list")

    except Exception as e:
        print(f"   ❌ Error checking room: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await lkapi.aclose()

    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)
    print("\nTo test voice interaction:")
    print(f"  1. Go to https://agents-playground.livekit.io/")
    print(f"  2. Enter room name: {room_name}")
    print(f"  3. Click Connect and allow microphone access")


if __name__ == "__main__":
    asyncio.run(verify_dispatch_flow())
