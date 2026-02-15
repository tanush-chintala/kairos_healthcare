#!/usr/bin/env python3
"""Interactive test script for the Kairos voice agent (console mode)."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    print("=" * 70)
    print("  KAIROS VOICE AGENT - INTERACTIVE CONSOLE TEST")
    print("=" * 70)
    print("\nStarting agent in console mode...")
    print("You can now interact with the agent via text input.")
    print("Type 'quit' or 'exit' to stop.\n")
    print("-" * 70 + "\n")

    # Import and run the agent in console mode
    from examples.voice_agents.basic_agent import cli

    # Run console mode
    import sys
    sys.argv = ["basic_agent.py", "console"]
    cli.run_app()
