"""Configuration management for services."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/clinic_configs.db")
DATABASE_DIR = Path(DATABASE_PATH).parent

# Agent configuration
AGENT_NAME = os.getenv("AGENT_NAME", "dental-assistant")

# LiveKit configuration (for webhook service)
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# Ensure database directory exists
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
