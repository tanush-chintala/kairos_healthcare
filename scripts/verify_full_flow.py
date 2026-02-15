"""Complete verification script for webhook + dispatch + agent flow."""

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


async def verify_full_flow() -> None:
    """Verify the complete flow: webhook -> dispatch -> agent connection."""
    print("=" * 70)
    print("COMPLETE FLOW VERIFICATION")
    print("=" * 70)
    
    # Check prerequisites
    print("\n📋 Checking prerequisites...")
    webhook_url = "http://localhost:8000"
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    agent_name = os.getenv("AGENT_NAME", "dental-assistant")

    # Check webhook
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{webhook_url}/health")
            if health.status_code == 200:
                print("   ✓ Webhook service is running")
            else:
                print("   ❌ Webhook service returned error")
                return
    except Exception:
        print("   ❌ Webhook service is NOT running!")
        print("   → Start it with: uv run python -m services.webhook_service")
        return

    # Check LiveKit credentials
    if not all([livekit_url, api_key, api_secret]):
        print("   ❌ Missing LiveKit credentials")
        print("   → Set: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
        return
    print("   ✓ LiveKit credentials configured")

    # Step 1: Create dispatch
    print("\n1️⃣  Creating dispatch via webhook...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{webhook_url}/webhook/incoming-call",
                json={"clinic_id": "sunshine-clinic", "from_number": "+1-555-TEST"},
            )

            if response.status_code != 200:
                print(f"   ❌ Failed: {response.text}")
                return

            data = response.json()
            room_name = data["room_name"]
            dispatch_id = data["dispatch_id"]
            office_name = data["office_name"]

            print(f"   ✓ Dispatch created: {dispatch_id}")
            print(f"   ✓ Room: {room_name}")
            print(f"   ✓ Office: {office_name}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return

    # Step 2: Wait for agent to connect
    print("\n2️⃣  Waiting for agent to connect (10 seconds)...")
    print("   (Check Terminal 1 - agent server should show connection logs)")
    for i in range(10, 0, -1):
        print(f"   ⏳ {i}...", end="\r")
        await asyncio.sleep(1)
    print("   ✓ Wait complete")

    # Step 3: Verify room and participants
    print("\n3️⃣  Checking room status...")
    lkapi = api.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)

    try:
        # Check room exists
        room_request = api.ListRoomsRequest(names=[room_name])
        rooms_response = await lkapi.room.list_rooms(room_request)

        if not rooms_response.rooms:
            print(f"   ❌ Room {room_name} not found!")
            print("   → Room may have been deleted or never created")
            return

        room_info = rooms_response.rooms[0]
        print(f"   ✓ Room exists: {room_info.name}")
        print(f"   ✓ Participants: {room_info.num_participants}")

        # Check participants
        participants_request = api.ListParticipantsRequest(room=room_name)
        participants_response = await lkapi.room.list_participants(participants_request)

        agent_found = False
        if participants_response.participants:
            print(f"\n   📊 Found {len(participants_response.participants)} participant(s):")
            for p in participants_response.participants:
                is_agent = p.kind == api.ParticipantKind.PARTICIPANT_KIND_AGENT
                kind_str = "🤖 AGENT" if is_agent else "👤 USER"
                print(f"      {kind_str}: {p.identity}")
                if is_agent:
                    agent_found = True
        else:
            print("   ⚠️  No participants in room")
            print("   → This could mean:")
            print("     • Agent hasn't connected yet (wait longer)")
            print("     • Agent server is not running")
            print("     • AGENT_NAME mismatch (check .env file)")

        # Check dispatch
        print("\n4️⃣  Checking dispatch status...")
        dispatch_request = api.ListAgentDispatchRequest(agent_name=agent_name)
        dispatch_response = await lkapi.agent_dispatch.list_agent_dispatch(dispatch_request)

        our_dispatch = None
        for d in dispatch_response.dispatches:
            if d.id == dispatch_id:
                our_dispatch = d
                break

        if our_dispatch:
            state_name = api.AgentDispatchState.Name(our_dispatch.state)
            print(f"   ✓ Dispatch found: {our_dispatch.id}")
            print(f"   ✓ State: {state_name}")
            
            if our_dispatch.metadata:
                try:
                    metadata = json.loads(our_dispatch.metadata)
                    print(f"\n   📝 Metadata verified:")
                    print(f"      • Clinic: {metadata.get('clinic_id')}")
                    print(f"      • Office: {metadata.get('office_name')}")
                    print(f"      • Greeting: {metadata.get('greeting', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"   ⚠️  Metadata: {our_dispatch.metadata}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await lkapi.aclose()

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    if agent_found:
        print("✅ SUCCESS! Agent is connected to the room")
        print(f"\n🎤 To test voice interaction:")
        print(f"   1. Go to: https://agents-playground.livekit.io/")
        print(f"   2. Enter room: {room_name}")
        print(f"   3. Click 'Connect' and allow microphone access")
        print(f"   4. The agent should greet you: '{office_name}'")
    else:
        print("⚠️  PARTIAL: Dispatch created but agent not connected yet")
        print("\n🔍 Troubleshooting:")
        print("   • Check Terminal 1 (agent server) for error logs")
        print("   • Verify AGENT_NAME in .env matches the dispatch")
        print("   • Make sure agent server is running: uv run examples/voice_agents/basic_agent.py dev")
        print("   • Wait a bit longer and run this script again")
    
    print(f"\n📋 Room details:")
    print(f"   Room: {room_name}")
    print(f"   Dispatch: {dispatch_id}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify_full_flow())
