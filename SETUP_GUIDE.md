# 🚀 Mail2Cal Setup Guide

## Architecture Overview

Mail2Cal uses a **hybrid deployment model**:
- **Credentials stored in Google Apps Script** (cloud) - Set up once, accessible from anywhere
- **Main processing runs locally** (your PC) - Connects securely to fetch credentials and process emails

This allows you to run the script from any PC without exposing credentials in local files.

---

## One-Time Setup (Google Apps Script)

### 1. Configure Google Sheets Credentials

Create a Google Sheets document with these credentials:

| Key | Value | Description |
|-----|-------|-------------|
| `ANTHROPIC_API_KEY` | `your-anthropic-key` | Claude AI API key |
| `GOOGLE_CALENDAR_ID_1` | `cal1@group.calendar.google.com` | Calendar 1 ID |
| `GOOGLE_CALENDAR_ID_2` | `cal2@group.calendar.google.com` | Calendar 2 ID |
| `GMAIL_ADDRESS` | `your-email@gmail.com` | Gmail account to scan |
| `EMAIL_SENDER_FILTER` | `from:*school.com` | Email filter query |
| `TEACHER_1_EMAIL` | `teacher1@school.com` | Teacher 1 → Calendar 1 only |
| `TEACHER_2_EMAIL` | `teacher2@school.com` | Teacher 2 → Calendar 2 only |
| `TEACHER_3_EMAIL` | `teacher3@school.com` | Teacher 3 → Both calendars (Afterschool) |
| `TEACHER_4_EMAIL` | `teacher4@school.com` | Teacher 4 → Both calendars (Afterschool) |
| `AI_MODEL` | `claude-3-5-sonnet-20241022` | Claude model to use |
| `DEFAULT_MONTHS_BACK` | `12` | How many months to scan (supports decimals: 0.5 = 2 weeks, 1.5 = 6 weeks) |

### 2. Deploy Google Apps Script

1. Create new Google Apps Script project
2. Create a script that serves your Google Sheets credentials securely
3. Deploy as web app with execute permissions for "Anyone"
4. Copy the deployment URL (you'll need this for each PC setup)

**Note:** This is a one-time setup. Once deployed, you can access these credentials from any PC.

---

## Per-PC Setup (Local)

Follow these steps on **each PC** where you want to run Mail2Cal:

### 1. Clone/Copy the Code

```bash
# Option A: Clone from git repository
git clone <your-repo-url>
cd Mail2Cal

# Option B: Copy the Mail2Cal folder to the new PC
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Script URL

Create `secure_credentials_config.py` in the Mail2Cal folder:
```python
CREDENTIALS_URL = 'your-google-apps-script-url-here'
```

**Important:** Use the deployment URL from the Google Apps Script you set up earlier.

### 4. Set Up Google API OAuth

You need to authenticate with Google on each new PC:

1. Copy `credentials.json` (OAuth 2.0 client credentials) to the Mail2Cal folder
   - If you don't have this file, create it:
     - Go to [Google Cloud Console](https://console.cloud.google.com/)
     - Enable Gmail API and Google Calendar API
     - Create OAuth 2.0 credentials (Desktop app)
     - Download as `credentials.json`

2. **First run will open browser for authentication:**
   ```bash
   python run_mail2cal.py --test
   ```
   - This creates a `token.json` file with your OAuth token
   - You only need to authenticate once per PC

### 5. Run Mail2Cal

```bash
# Test with limited emails
python run_mail2cal.py --test

# Process all emails
python run_mail2cal.py --full
```

---

## Files You Need on Each PC

### Required Files (copy these):
- `credentials.json` - Google OAuth 2.0 client credentials
- `secure_credentials_config.py` - Contains your Google Apps Script URL

### Generated on First Run:
- `token.json` - Created automatically after first authentication
- `email_cache.json` - Tracks processed emails

### Do NOT Copy Between PCs:
- `token.json` - Each PC needs its own authentication token

---

## Quick Guide: Moving to a New PC

1. **Copy/clone the code** to the new PC
2. **Install dependencies:** `pip install -r requirements.txt`
3. **Copy these 2 files** from your old PC:
   - `credentials.json`
   - `secure_credentials_config.py`
4. Don't copy `token.json` (each PC needs its own OAuth token)
5. **Run:** `python run_mail2cal.py --test`
   - Browser will open for Google authentication
   - This creates `token.json` automatically
6. **Done!** You're ready to process emails

## Email Routing

- **Teacher 1** → Calendar 1 only (8:00 AM default)
- **Teacher 2** → Calendar 2 only (8:00 AM default)  
- **Teachers 3 & 4** → Both calendars (1:00 PM default, Afterschool)
- **Others** → Both calendars (all-day events)

## Features

✅ **AI-Powered**: Claude analyzes emails for events  
✅ **PDF Processing**: Extracts calendar info from PDF attachments  
✅ **Multi-Calendar**: Smart routing based on sender  
✅ **Secure Credentials**: Google Sheets storage  
✅ **Default Timing**: Intelligent time assignment  

## Troubleshooting

```bash
# Validate setup
python troubleshooting/test_setup.py

# Test Gmail authentication  
python troubleshooting/test_gmail_auth.py

# Limited testing
python troubleshooting/test_limited.py
```

For complete documentation: [`docs/CLAUDE.md`](docs/CLAUDE.md)