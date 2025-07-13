# Mail2Cal - AI-Powered Email to Calendar Converter

## Overview
Mail2Cal is an intelligent system that converts school emails and local files (PDFs, images) into Google Calendar events using Claude AI. The system features secure credential management, OCR processing, multi-calendar routing, recurring event creation, and smart duplicate prevention.

## Project Structure

```
Mail2Cal/
├── 📄 run_mail2cal.py                 # Main entry point (START HERE)
│
├── 🧠 core/                           # Core Application Logic
│   ├── mail2cal.py                    # Main Mail2Cal class
│   ├── ai_parser.py                   # Claude AI integration
│   ├── event_tracker.py               # Event tracking system
│   └── global_event_cache.py          # Smart duplicate prevention
│
├── ⚙️ processors/                     # Content Processors
│   ├── file_event_processor.py        # File processing (PDFs, images)
│   └── pdf_attachment_processor.py    # PDF attachment processing
│
├── 🔐 auth/                           # Authentication & Credentials
│   ├── secure_credentials.py          # Secure credential management
│   └── secure_credentials_config.py   # Credential configuration
│
├── 🛠️ utils/                          # Utility Scripts
│   ├── preview_emails.py              # Preview emails (no AI tokens)
│   ├── cleanup_duplicates.py          # Remove duplicate events
│   └── check_calendar.py              # View calendar events
│
├── 📂 local_resources/                # File Processing Directory
│   ├── Calendar_1/                    # Files for Calendar 1 only
│   ├── Calendar_2/                    # Files for Calendar 2 only
│   └── Both/                          # Files for both calendars
│
├── 📚 docs/                           # Documentation
│   └── CLAUDE.md                     # Complete documentation (this file)
│
└── 📋 Essential Files
    ├── README.md                      # Project overview
    ├── SETUP_GUIDE.md                 # Quick setup instructions
    ├── requirements.txt               # Python dependencies
    ├── secure_credentials_config.py   # Secure credential configuration
    ├── .gitignore                     # Git ignore rules
    └── LICENSE                        # License file
```

## Quick Start

### 1. Installation
```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Setup
Follow the [`SETUP_GUIDE.md`](../SETUP_GUIDE.md) for complete configuration instructions.

### 3. Basic Usage
```bash
# Preview emails without using AI tokens
python run_mail2cal.py --preview

# Test with 3 recent emails (minimal tokens)
python run_mail2cal.py --test

# Process all emails with AI (full system)
python run_mail2cal.py --full
```

## Key Features

### 🤖 AI-Powered Email Analysis
- Uses Claude 3.5 Sonnet for intelligent email parsing
- Understands Spanish language context
- Extracts events, homework, meetings, deadlines automatically
- Handles complex email formats (HTML, plain text)
- Processes PDF attachments for calendar information

### 📄 PDF Attachment Processing
- **Auto-Detection**: Automatically finds and processes PDF attachments
- **Text Extraction**: Uses pdfplumber and PyMuPDF for robust text extraction
- **Table Support**: Handles structured calendar data in PDF tables
- **Spanish Text**: Optimized for Spanish language content
- **Content Types**: Holiday schedules, activity calendars, special announcements

### 🎓 Multi-Calendar Smart Routing
- **Teacher 1** → Calendar 1 only (8:00 AM default timing)
- **Teacher 2** → Calendar 2 only (8:00 AM default timing)
- **Teachers 3 & 4 (Afterschool)** → Both calendars (1:00 PM default timing)
- **Other school emails** → Both calendars (all-day events)

### 📅 Smart Event Management
- **Creates** new calendar events for detected activities
- **Updates** existing events when email content changes
- **Prevents** duplicate events through intelligent matching
- **Deletes** obsolete events when no longer relevant

### 🔒 Secure Credential Management
- Google Sheets integration for secure credential storage
- No hardcoded API keys or sensitive information in code
- Fallback to environment variables when needed
- OAuth 2.0 authentication with Google APIs

### ⏰ Intelligent Default Timing
- **Teachers 1 & 2**: 8:00 AM - 10:00 AM (2 hours) when no time specified
- **Afterschool Teachers (3 & 4)**: 1:00 PM - 3:00 PM (2 hours) when no time specified
- **Other senders**: All-day events when no time specified
- **Specific times mentioned**: Uses times from email content

## Command Reference

### Primary Commands
```bash
# Full processing (all emails)
python run_mail2cal.py --full

# Preview mode (no AI tokens used)
python run_mail2cal.py --preview

# Test mode (3 recent emails)
python run_mail2cal.py --test

# Process local files (PDFs and images)
python run_mail2cal.py --process-files

# List processed files
python run_mail2cal.py --list-files

# Check file processing dependencies
python run_mail2cal.py --check-file-deps

# Cleanup duplicates
python run_mail2cal.py --cleanup

# Check calendar events
python run_mail2cal.py --check
```

### Options
```bash
# Test with custom number of emails
python run_mail2cal.py --test --limit 5

# Interactive mode (menu-driven)
python run_mail2cal.py
```

## Configuration

### Secure Credentials (Google Sheets)
The system uses Google Sheets for secure credential storage:

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Claude AI API key |
| `GOOGLE_CALENDAR_ID_1` | Calendar 1 ID |
| `GOOGLE_CALENDAR_ID_2` | Calendar 2 ID |
| `GMAIL_ADDRESS` | Gmail account to scan |
| `EMAIL_SENDER_FILTER` | Email filter query |
| `TEACHER_1_EMAIL` | Teacher 1 → Calendar 1 only |
| `TEACHER_2_EMAIL` | Teacher 2 → Calendar 2 only |
| `TEACHER_3_EMAIL` | Teacher 3 → Both calendars (Afterschool) |
| `TEACHER_4_EMAIL` | Teacher 4 → Both calendars (Afterschool) |
| `AI_MODEL` | Claude model to use |
| `DEFAULT_MONTHS_BACK` | How many months to scan |

### Email Processing
- **Source**: Gmail account (configurable)
- **Filter**: Configurable email search query
- **Date Range**: Configurable months back to scan
- **Processing**: Only new/changed emails on subsequent runs

## Common Workflows

### Initial Setup
1. `python run_mail2cal.py --preview` - Review emails
2. `python run_mail2cal.py --test` - Test with 3 emails
3. `python run_mail2cal.py --full` - Process all emails

### Regular Use
1. `python run_mail2cal.py --full` - Update with new emails
2. `python run_mail2cal.py --process-files` - Process local files
3. `python run_mail2cal.py --cleanup` - Remove duplicates if needed
4. `python run_mail2cal.py --check` - Review calendar events

### File Processing Workflow
1. Place files in `local_resources/Calendar_1/`, `local_resources/Calendar_2/`, or `local_resources/Both/`
2. `python run_mail2cal.py --check-file-deps` - Verify OCR dependencies
3. `python run_mail2cal.py --process-files` - Extract events from files
4. `python run_mail2cal.py --list-files` - Review processed files

### Troubleshooting
```bash
# Validate installation
python troubleshooting/test_setup.py

# Test Gmail authentication
python troubleshooting/test_gmail_auth.py

# Limited test (3 emails)
python troubleshooting/test_limited.py
```

## Processing Flows

### Email Processing Flow
1. **Authentication**: OAuth 2.0 with Google APIs
2. **Email Retrieval**: Fetch emails matching filter criteria
3. **PDF Processing**: Extract text from PDF attachments (if any)
4. **AI Analysis**: Claude analyzes email + PDF content for events
5. **Routing Decision**: Determine target calendar(s) based on sender
6. **Event Creation**: Create/update calendar events with smart timing

### File Processing Flow
1. **File Scanning**: Scan `local_resources/` directory for PDFs and images
2. **Content Extraction**: 
   - PDFs: Text extraction using pdfplumber/PyMuPDF
   - Images: OCR text extraction using Tesseract
3. **AI Analysis**: Claude analyzes extracted text for calendar events
4. **Calendar Routing**: Route to Calendar 1, Calendar 2, or Both based on folder
5. **Event Creation**: Create recurring events with proper scheduling
6. **Change Detection**: Track file changes and update events accordingly

### Supported File Types
- **PDFs**: All PDF formats supported
- **Images**: JPG, JPEG, PNG, TIFF, BMP (requires Tesseract OCR)

### Directory Structure for Files
```
local_resources/
├── Calendar_1/        # Events for Calendar 1 only
├── Calendar_2/        # Events for Calendar 2 only  
└── Both/             # Events for both calendars
```
7. **Tracking**: Record email-to-event mappings to prevent duplicates

## PDF Attachment Processing

### Supported PDFs
- Holiday calendars and exceptional days off
- Special activity schedules
- School event programs
- Class timetable changes
- Administrative announcements

### Processing Flow
1. **Auto-Detection**: Scans emails for PDF attachments
2. **Download**: Retrieves PDF content via Gmail API
3. **Text Extraction**: Uses pdfplumber (primary) and PyMuPDF (fallback)
4. **Content Integration**: Adds PDF text to email content for AI analysis
5. **Event Creation**: AI processes combined email + PDF content

### Example Output
```
[📎] Found 1 PDF attachment(s)
[📄] Processing PDF 1/1: calendario_marzo_2025.pdf
[+] Successfully extracted 892 characters from PDF
[AI] Analyzing email content with Claude...
[+] Found 3 event(s) from PDF content
```

## Performance

### Email Processing
- **Speed**: ~3-5 seconds per email (including AI analysis)
- **Memory Usage**: Minimal (streams email data)
- **Rate Limits**: Respects Google API quotas

### AI Token Usage
- **Preview Mode**: 0 tokens (no AI calls)
- **Test Mode**: ~3-5 tokens (3 emails)
- **Full Mode**: Varies based on email count

## Error Handling

### Common Issues
1. **Credential Errors**: Check Google Sheets and Apps Script deployment
2. **Calendar Access**: Verify calendar ID and permissions
3. **OAuth Errors**: Re-authenticate or check app publishing status
4. **PDF Processing**: Requires pdfplumber and PyMuPDF libraries

### Authentication Flow
1. First run opens browser for Google OAuth
2. Credentials saved locally for future runs
3. Automatic token refresh when expired
4. Manual re-authentication if refresh fails

## File Management

### Persistent Files
- `token.pickle` - Authentication cache (auto-regenerated)
- `event_mappings.json` - Email-to-event tracking (maintains history)
- `secure_credentials_config.py` - Google Apps Script URL

### Temporary Files
- PDF downloads (automatically cleaned up)
- AI processing cache (optional)

## Security

### Data Protection
- No hardcoded credentials in source code
- Secure credential storage via Google Sheets
- OAuth 2.0 authentication only
- PDF content processed locally and discarded

### API Access
- **Gmail API**: Read-only access to scan emails
- **Calendar API**: Create/update/delete events only
- **Anthropic API**: Send email content for analysis only

## Current Status

✅ **Multi-Calendar System**: Teacher-based routing operational  
✅ **PDF Processing**: Automatic attachment processing enabled  
✅ **Secure Credentials**: Google Sheets integration active  
✅ **Smart Timing**: Default time assignment based on sender type  
✅ **Clean Repository**: Only essential files remain  

The Mail2Cal system is fully operational and ready for production use.