"""Test script for webhook and dispatch flow."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_webhook(webhook_url: str = "http://localhost:8000") -> None:
    """Test webhook endpoint with mock call data.

    Args:
        webhook_url: Base URL of webhook service
    """
    print(f"Testing webhook at: {webhook_url}")

    # Test data - simulate incoming call for sunshine-clinic
    test_request = {
        "to_number": "+1-555-SUNSHINE",
        "from_number": "+1-555-123-4567",
    }

    print(f"\nSending test request: {json.dumps(test_request, indent=2)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test health endpoint first
            health_response = await client.get(f"{webhook_url}/health")
            print(f"\nHealth check: {health_response.status_code} - {health_response.json()}")

            # Test clinics list endpoint
            clinics_response = await client.get(f"{webhook_url}/clinics")
            print(f"\nClinics in database: {clinics_response.status_code}")
            if clinics_response.status_code == 200:
                clinics_data = clinics_response.json()
                print(f"  Found {len(clinics_data.get('clinics', []))} clinics")
                for clinic in clinics_data.get("clinics", []):
                    print(f"    - {clinic['id']}: {clinic['office_name']}")

            # Test incoming call webhook
            response = await client.post(
                f"{webhook_url}/webhook/incoming-call",
                json=test_request,
            )

            print(f"\nWebhook response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Dispatch ID: {data.get('dispatch_id')}")
                print(f"  Room Name: {data.get('room_name')}")
                print(f"  Clinic ID: {data.get('clinic_id')}")
                print(f"  Office Name: {data.get('office_name')}")
                print("\n✓ Dispatch created successfully!")
            else:
                print(f"  Error: {response.text}")
                print("\n✗ Failed to create dispatch")

        except httpx.ConnectError:
            print(f"\n✗ Could not connect to webhook service at {webhook_url}")
            print("  Make sure the webhook service is running:")
            print("    python -m services.webhook_service")
        except Exception as e:
            print(f"\n✗ Error: {e}")


async def test_with_clinic_id(webhook_url: str = "http://localhost:8000") -> None:
    """Test webhook with explicit clinic_id.

    Args:
        webhook_url: Base URL of webhook service
    """
    print(f"\nTesting with explicit clinic_id...")

    test_request = {
        "clinic_id": "sunshine-clinic",
        "from_number": "+1-555-123-4567",
    }

    print(f"Sending test request: {json.dumps(test_request, indent=2)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{webhook_url}/webhook/incoming-call",
                json=test_request,
            )

            print(f"\nWebhook response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Dispatch ID: {data.get('dispatch_id')}")
                print(f"  Room Name: {data.get('room_name')}")
                print(f"  Clinic ID: {data.get('clinic_id')}")
                print(f"  Office Name: {data.get('office_name')}")
                print("\n✓ Dispatch created successfully!")
            else:
                print(f"  Error: {response.text}")

        except Exception as e:
            print(f"\n✗ Error: {e}")


async def main() -> None:
    """Run all tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test webhook and dispatch flow")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Webhook service URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Webhook and Dispatch Test")
    print("=" * 60)

    await test_webhook(args.url)
    await test_with_clinic_id(args.url)

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
