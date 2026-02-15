"""Initialize database with schema and optional seed data."""

import sys
from pathlib import Path

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import ClinicDatabase, get_db


def init_database(seed_example: bool = True) -> None:
    """Initialize database and optionally seed with example data.

    Args:
        seed_example: Whether to seed with example clinic data
    """
    db = get_db()
    print(f"Database initialized at: {db.db_path}")

    if seed_example:
        # Check if example already exists
        existing = db.get_clinic_config("sunshine-clinic")
        if existing:
            print("Example clinic 'sunshine-clinic' already exists. Skipping seed.")
        else:
            # Create example clinic
            db.create_clinic_config(
                clinic_id="sunshine-clinic",
                office_name="Sunshine Dental Clinic",
                greeting="Welcome to Sunshine Dental Clinic. How may I help you today?",
                phone_number="+1-555-SUNSHINE",
            )
            print("Seeded database with example clinic: sunshine-clinic")

    # List all clinics
    clinics = db.list_all_clinics()
    print(f"\nTotal clinics in database: {len(clinics)}")
    for clinic in clinics:
        print(f"  - {clinic['id']}: {clinic['office_name']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize clinic database")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip seeding example data",
    )
    args = parser.parse_args()

    init_database(seed_example=not args.no_seed)
