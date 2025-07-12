# 🚀 Mail2Cal Setup Guide

## Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Google Sheets Credentials

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
| `DEFAULT_MONTHS_BACK` | `12` | How many months to scan |

### 3. Deploy Google Apps Script

1. Create new Google Apps Script project
2. Create a script that serves your Google Sheets credentials securely
3. Deploy as web app with execute permissions for "Anyone" 
4. Copy the deployment URL

### 4. Configure Script URL

Create `secure_credentials_config.py`:
```python
CREDENTIALS_URL = 'your-google-apps-script-url-here'
```

### 5. Set Up Google API

1. Enable Gmail API and Google Calendar API
2. Create OAuth 2.0 credentials 
3. Download as `credentials.json`
4. Place in Mail2Cal folder

### 6. Run Mail2Cal

```bash
# Test with limited emails
python run_mail2cal.py --test

# Process all emails  
python run_mail2cal.py --full
```

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