"""SQLite database operations for clinic configurations."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH


class ClinicDatabase:
    """Database manager for clinic configurations."""

    def __init__(self, db_path: str = DATABASE_PATH) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db_exists(self) -> None:
        """Ensure database file and tables exist."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create table if it doesn't exist
        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clinic_configs (
                id TEXT PRIMARY KEY,
                office_name TEXT NOT NULL,
                greeting TEXT,
                phone_number TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get database connection (property for compatibility)."""
        return self._get_connection()

    def get_clinic_config(self, clinic_id: str) -> dict[str, Any] | None:
        """Get clinic configuration by ID.

        Args:
            clinic_id: Clinic identifier

        Returns:
            Clinic configuration dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM clinic_configs WHERE id = ?", (clinic_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return dict(row)

    def get_clinic_by_phone(self, phone_number: str) -> dict[str, Any] | None:
        """Get clinic configuration by phone number.

        Args:
            phone_number: Phone number to look up

        Returns:
            Clinic configuration dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM clinic_configs WHERE phone_number = ?", (phone_number,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return dict(row)

    def create_clinic_config(
        self,
        clinic_id: str,
        office_name: str,
        greeting: str | None = None,
        phone_number: str | None = None,
    ) -> dict[str, Any]:
        """Create a new clinic configuration.

        Args:
            clinic_id: Clinic identifier
            office_name: Name of the clinic
            greeting: Custom greeting message (optional)
            phone_number: Phone number for this clinic (optional)

        Returns:
            Created clinic configuration dict
        """
        conn = self._get_connection()
        now = datetime.utcnow().isoformat()

        conn.execute(
            """
            INSERT INTO clinic_configs (id, office_name, greeting, phone_number, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (clinic_id, office_name, greeting, phone_number, now, now),
        )
        conn.commit()
        conn.close()

        return self.get_clinic_config(clinic_id)

    def update_clinic_config(
        self, clinic_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Update clinic configuration.

        Args:
            clinic_id: Clinic identifier
            **kwargs: Fields to update (office_name, greeting, phone_number)

        Returns:
            Updated clinic configuration dict or None if not found
        """
        if not kwargs:
            return self.get_clinic_config(clinic_id)

        # Build update query dynamically
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ("office_name", "greeting", "phone_number"):
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return self.get_clinic_config(clinic_id)

        values.append(clinic_id)
        values.append(datetime.utcnow().isoformat())  # updated_at

        conn = self._get_connection()
        conn.execute(
            f"""
            UPDATE clinic_configs
            SET {', '.join(fields)}, updated_at = ?
            WHERE id = ?
            """,
            values,
        )
        conn.commit()
        conn.close()

        return self.get_clinic_config(clinic_id)

    def list_all_clinics(self) -> list[dict[str, Any]]:
        """List all clinic configurations.

        Returns:
            List of clinic configuration dicts
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM clinic_configs ORDER BY id")
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


# Global database instance
_db_instance: ClinicDatabase | None = None


def get_db() -> ClinicDatabase:
    """Get global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = ClinicDatabase()
    return _db_instance
