# Quick Start - Run Existing Setup

This guide is for running the **exact same** Kairos voice agent setup (same Google Sheet, same configuration).

## Prerequisites

1. **Python 3.10+** installed
2. **`uv` package manager** installed ([install uv](https://github.com/astral-sh/uv))
3. **Git** installed

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd kairos_healthcare
```

## Step 2: Install Dependencies

```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements-booking.txt
pip install -r examples/voice_agents/requirements.txt
```

## Step 3: Get Credentials from Repository Owner

You'll need these from the person who set up the repository:

1. **`.env` file** - Copy it to the project root, or get these values:
   - `LIVEKIT_URL`
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_API_SECRET`
   - `OPENAI_API_KEY`
   - `DEEPGRAM_API_KEY`
   - `CARTESIA_API_KEY`
   - `GOOGLE_SHEETS_SPREADSHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON` (path to the JSON file)

2. **Google Service Account JSON file** - Get the file and place it somewhere on your machine, then update the path in `.env`

3. **Google Sheet Access** - Make sure the Google Sheet is shared with the service account email (found in the JSON file)

## Step 4: Create `.env` File

Create a `.env` file in the project root with the values you received:

```bash
# Copy the .env values from the repository owner
# Or create it manually with the provided values
```

## Step 5: Run the Agent

### Console Mode (Easiest for Testing)

```bash
uv run examples/voice_agents/basic_agent.py console
```

Type messages like "I need to book an appointment" to test.

### Dev Mode (For Web/Playground)

```bash
uv run examples/voice_agents/basic_agent.py dev
```

Then open [Agents Playground](https://agents-playground.livekit.io/) and connect with your LiveKit credentials.

## That's It!

If you have all the credentials, you should be able to run it immediately after:
1. Cloning the repo
2. Installing dependencies (`uv sync`)
3. Adding the `.env` file with credentials
4. Running the agent

## Troubleshooting

### "GOOGLE_SHEETS_SPREADSHEET_ID environment variable not set"
- Make sure your `.env` file is in the project root
- Check that all variable names match exactly

### "Permission denied" on Google Sheet
- Ask the repository owner to share the Google Sheet with the service account email
- The service account email is in the JSON file (look for `"client_email"`)

### "No module named 'gspread'"
- Run `uv sync` or `pip install -r requirements-booking.txt`
