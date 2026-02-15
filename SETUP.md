# Kairos Voice Agent - Setup Guide

This guide will help you set up and run the Kairos voice agent on your local machine.

## Prerequisites

1. **Python 3.10+** installed
2. **`uv` package manager** installed ([install uv](https://github.com/astral-sh/uv))
3. **Git** installed
4. **Google Cloud Service Account** with Sheets API enabled
5. **API Keys** for:
   - LiveKit (Cloud account)
   - OpenAI (for LLM)
   - Deepgram (for Speech-to-Text)
   - Cartesia (for Text-to-Speech)

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd kairos_healthcare
```

## Step 2: Install Dependencies

The project uses `uv` for dependency management. Install dependencies:

```bash
# Install main dependencies
uv sync

# Or if you prefer pip, install from requirements files:
pip install -r requirements-booking.txt
pip install -r examples/voice_agents/requirements.txt
```

## Step 3: Set Up Google Sheets

1. **Create a Google Sheet** with 3 tabs:
   - `Patients` - Patient information
   - `Appt_Index` - Appointment index (source of truth)
   - `Master_Schedule` - Calendar view (read-only, derived)

2. **Set up Google Cloud Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or use existing
   - Enable **Google Sheets API**
   - Create a **Service Account**
   - Download the JSON key file
   - Share your Google Sheet with the service account email (found in the JSON file)

3. **Get your Spreadsheet ID**:
   - Open your Google Sheet
   - The ID is in the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`

## Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# LiveKit Configuration (get from https://cloud.livekit.io)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# OpenAI Configuration (for LLM)
OPENAI_API_KEY=your-openai-api-key

# Deepgram Configuration (for Speech-to-Text)
DEEPGRAM_API_KEY=your-deepgram-api-key

# Cartesia Configuration (for Text-to-Speech)
CARTESIA_API_KEY=your-cartesia-api-key

# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id-here
GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/your/service-account.json

# Optional: Customize sheet names (defaults shown)
PATIENTS_SHEET_NAME=Patients
APPT_INDEX_SHEET_NAME=Appt_Index
MASTER_SCHEDULE_SHEET_NAME=Master_Schedule
```

**Important Notes:**
- `GOOGLE_SERVICE_ACCOUNT_JSON` must be an **absolute path** to your JSON file
- Make sure the service account email has **edit access** to your Google Sheet
- Never commit your `.env` file to git (it should be in `.gitignore`)

## Step 5: Add Test Data (Optional but Recommended)

Before testing, add some test data to your Google Sheet:

```bash
uv run python scripts/add_test_data.py
```

This will add:
- Test patients to the `Patients` tab
- Test appointment slots to the `Appt_Index` tab

## Step 6: Run the Agent

### Option 1: Console Mode (Easiest for Testing)

Test the agent with text input:

```bash
uv run examples/voice_agents/basic_agent.py console
```

Type messages like "I need to book an appointment" and interact with the agent.

### Option 2: Dev Mode (For Web/Playground Testing)

Run the agent server:

```bash
uv run examples/voice_agents/basic_agent.py dev
```

Then:
1. Open [Agents Playground](https://agents-playground.livekit.io/)
2. Enter your LiveKit credentials
3. Create/join a room
4. The agent will automatically connect

### Option 3: Connect Command (Simulate a Job)

In one terminal, run:
```bash
uv run examples/voice_agents/basic_agent.py dev
```

In another terminal:
```bash
uv run examples/voice_agents/basic_agent.py connect --room test-room
```

## Troubleshooting

### "GOOGLE_SHEETS_SPREADSHEET_ID environment variable not set"
- Make sure your `.env` file is in the project root
- Check that variable names match exactly (case-sensitive)
- Try running `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID'))"` to verify

### "Permission denied" or "Unable to open spreadsheet"
- Make sure you shared the Google Sheet with the service account email
- Check that the service account JSON file path is correct and absolute
- Verify the service account has edit permissions

### "No module named 'gspread'"
- Run `uv sync` or `pip install -r requirements-booking.txt`

### Agent doesn't respond
- Check that all API keys are set correctly
- Verify LiveKit credentials are valid
- Check logs for error messages

## Testing

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing instructions.

## Additional Resources

- [KAIROS_SETUP.md](KAIROS_SETUP.md) - Detailed Google Sheets schema documentation
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing guide
- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)

## Need Help?

If you encounter issues:
1. Check the logs for error messages
2. Verify all environment variables are set
3. Ensure your Google Sheet has the correct structure (see KAIROS_SETUP.md)
4. Make sure all API keys are valid and have sufficient credits/quota
