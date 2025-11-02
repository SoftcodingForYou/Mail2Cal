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
│   ├── ai_parser.py                   # Claude AI integration (two-stage processing)
│   ├── event_tracker.py               # Event tracking system
│   ├── smart_event_merger.py          # AI-powered cross-email event merging
│   ├── global_event_cache.py          # Smart duplicate prevention
│   └── token_tracker.py               # AI token usage and cost tracking
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
│   ├── test_smart_merger.py           # Test AI-powered event merging
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

# Process all emails with AI (full system) - INCLUDES SMART MERGING
python run_mail2cal.py --full
```

### 4. Smart Event Merging
The AI-powered smart merger automatically activates during email processing:

```bash
# Run email processing (option 5) to activate smart merging
python run_mail2cal.py
# Choose option 5: Process ALL emails

# Smart merger output examples:
[AI] Checking for potential duplicate events across all emails...
[MERGE] Auto-merging duplicate event: Día de la Familia...
[REVIEW] Potential duplicate found (similarity: 0.78): Reunión de Apoderados...
```

**What you'll see during merging:**
- `[MERGE]` - Events automatically merged (>85% similarity)
- `[REVIEW]` - Potential duplicates flagged for manual review (70-85% similarity)
- `[SKIP]` - Events already processed by smart merger
- Combined event descriptions with source tracking

## Key Features

### 🤖 Two-Stage AI Processing (Cost Optimized)
**Stage 1: Email Classification (Haiku 4.5 - Fast & Cheap)**
- Quickly determines if email contains events (yes/no)
- ~$0.0001 per email
- Skips 50-70% of non-event emails automatically

**Stage 2: Event Extraction (Sonnet 4.5 - Powerful)**
- Only runs if Stage 1 confirms events present
- Intelligent email parsing with deep understanding
- Understands Spanish language context
- Extracts events, homework, meetings, deadlines automatically
- Handles complex email formats (HTML, plain text)
- Processes PDF attachments for calendar information

**Cost Savings**: 50-70% reduction in extraction costs vs. single-stage processing

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

### 🧠 AI-Powered Cross-Email Event Merging
- **Semantic Analysis**: Uses Claude Haiku 4.5 to detect duplicate events across different emails
- **Batch Processing**: Compares 1 new event against 5 candidates in a single API call (5x efficiency)
- **Smart Merging**: Automatically combines events about the same activity from multiple sources
- **Information Enrichment**: Merges descriptions, requirements, and details into comprehensive events
- **Auto-Decision**: Events with >85% similarity from same sender merge automatically
- **Manual Review**: Events with 70-85% similarity flagged for review
- **Audit Trail**: Tracks all source emails that contributed to merged events
- **Example**: Multiple "Día de la Familia" emails → One comprehensive merged event
- **Cost Optimized**: Uses cheap Haiku model + batching = 95% cost reduction vs. original approach

### 📊 AI Token Usage Tracking & Cost Visibility
- **Real-time Tracking**: Logs every AI API call with input/output tokens
- **Cost Calculation**: Automatic cost computation based on current pricing
- **Detailed Breakdown**: Session summary showing:
  - Total API calls by operation type (classification, extraction, duplicate detection)
  - Token usage (input/output) per operation
  - Cost per operation and total session cost
  - Average cost per email
  - Percentage breakdown by operation
- **Session Summary**: Displays comprehensive report at end of each run
- **JSON Export**: Saves detailed log to `ai_usage_log.json` for analysis
- **Example Output**:
  ```
  AI TOKEN USAGE SUMMARY
  ==========================================
  Total Calls: 127
  Total Tokens: 245,830
  Total Cost: $0.8234

  BREAKDOWN BY OPERATION:
  - email_classification: $0.0080 (0.4%)
  - event_extraction: $1.0125 (97.9%)
  - duplicate_detection_batch: $0.0174 (1.7%)
  ```

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

| Key | Description | Example Value |
|-----|-------------|---------------|
| `ANTHROPIC_API_KEY` | Claude AI API key | sk-ant-... |
| `GOOGLE_CALENDAR_ID_1` | Calendar 1 ID | user@gmail.com |
| `GOOGLE_CALENDAR_ID_2` | Calendar 2 ID | user@gmail.com |
| `GMAIL_ADDRESS` | Gmail account to scan | user@gmail.com |
| `EMAIL_SENDER_FILTER` | Email filter query | from:*@school.com |
| `TEACHER_1_EMAIL` | Teacher 1 → Calendar 1 only | teacher1@school.com |
| `TEACHER_2_EMAIL` | Teacher 2 → Calendar 2 only | teacher2@school.com |
| `TEACHER_3_EMAIL` | Teacher 3 → Both calendars (Afterschool) | teacher3@school.com |
| `TEACHER_4_EMAIL` | Teacher 4 → Both calendars (Afterschool) | teacher4@school.com |
| `AI_MODEL` | Claude model for event extraction (powerful) | claude-sonnet-4-5-20250929 |
| `AI_MODEL_CHEAP` | Claude model for classification & duplicates (cheap) | claude-haiku-4-5-20251001 |
| `DEFAULT_MONTHS_BACK` | How many months to scan (supports decimals: 0.5 = 2 weeks) | 1.0 |

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
4. **AI Stage 1 - Classification** (Haiku 4.5): Quick yes/no determination if email has events
   - If NO events detected → Skip to next email (cost savings!)
   - If YES events detected → Proceed to Stage 2
5. **AI Stage 2 - Extraction** (Sonnet 4.5): Full event extraction from email + PDF content
6. **Duplicate Detection** (Haiku 4.5): Batch comparison against existing events in 2-week window
7. **Routing Decision**: Determine target calendar(s) based on sender
8. **Event Creation**: Create/update calendar events with smart timing
9. **Token Tracking**: Log all AI usage for cost visibility

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
- **Speed**: ~4-6 seconds per email (including two-stage AI analysis)
  - Stage 1 (Classification): ~0.5 seconds
  - Stage 2 (Extraction): ~3-4 seconds (only if Stage 1 = yes)
  - Duplicate Detection: ~1 second (batched)
- **Memory Usage**: Minimal (streams email data)
- **Rate Limits**: Respects Google API quotas

### AI Token Usage & Cost

#### **Per Email (Typical)**
- **Classification** (Haiku 4.5): ~300 tokens → $0.0003
- **Extraction** (Sonnet 4.5): ~4,000 tokens → $0.02 (only if has events)
- **Duplicate Detection** (Haiku 4.5, batched): ~200 tokens → $0.0002
- **Total per event email**: ~$0.02
- **Total per non-event email**: ~$0.0003 (95% cheaper!)

#### **Session Examples**
| Emails | Event Emails | Non-Event | Classification | Extraction | Duplicates | **Total Cost** |
|--------|-------------|-----------|----------------|------------|------------|----------------|
| 10     | 5           | 5         | $0.003         | $0.10      | $0.001     | **~$0.10**     |
| 50     | 25          | 25        | $0.015         | $0.50      | $0.005     | **~$0.52**     |
| 100    | 45          | 55        | $0.030         | $0.90      | $0.009     | **~$0.94**     |

#### **Cost Optimization**
- **Two-Stage Processing**: 50-70% reduction (skips extraction for non-event emails)
- **Batch Duplicate Detection**: 80% reduction (5x fewer API calls)
- **Cheap Model for Simple Tasks**: 95% reduction (Haiku vs. Sonnet for classification/duplicates)
- **Combined Savings**: ~85-92% vs. naive implementation

#### **Usage Modes**
- **Preview Mode**: 0 tokens, $0.00 (no AI calls)
- **Test Mode (3 emails)**: ~13,000 tokens, ~$0.05
- **Full Mode**: Varies based on email count (see table above)

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
- `ai_usage_log.json` - Detailed AI token usage and cost tracking (per session)

### Temporary Files
- PDF downloads (automatically cleaned up)
- AI processing cache (optional)

### AI Usage Log Structure
The `ai_usage_log.json` file contains detailed information about AI API usage:
```json
{
  "session_start": "2025-01-15T10:30:00",
  "session_duration_seconds": 312,
  "total_calls": 127,
  "total_tokens": 245830,
  "total_cost": 0.8234,
  "operations": {
    "email_classification": {
      "count": 100,
      "total_tokens": 15200,
      "cost": 0.0080,
      "model": "claude-haiku-4-5-20251001"
    },
    "event_extraction": {
      "count": 45,
      "total_tokens": 175500,
      "cost": 1.0125,
      "model": "claude-sonnet-4-5-20250929"
    },
    "duplicate_detection_batch": {
      "count": 23,
      "total_tokens": 55130,
      "cost": 0.0174,
      "model": "claude-haiku-4-5-20251001"
    }
  }
}
```

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

## Development Guidelines

### Code Standards
- **Unicode Safety**: Avoid emojis and special Unicode characters in Python print statements
  - ❌ Don't use: `print(f"[📎] Processing...")`
  - ✅ Use instead: `print(f"[PDF] Processing...")`
  - **Reason**: Unicode characters cause encoding errors on Windows systems (cp1252 codec issues)
  - **Solution**: Use ASCII-safe characters and text descriptions instead of emojis

- **Error Handling**: Always handle Unicode in user-facing content:
  ```python
  # Safe printing of potentially Unicode content
  safe_text = text.encode('ascii', errors='replace').decode('ascii')
  print(f"[INFO] {safe_text}")
  ```

- **Attachment Processing**: Use Unicode-safe text cleaning for extracted content:
  ```python
  def _clean_unicode_text(self, text: str) -> str:
      # Replace problematic Unicode characters with ASCII equivalents
      # Remove emoji and high Unicode characters that cause encoding issues
  ```

### Testing Guidelines
- Test on Windows systems to catch Unicode encoding issues early
- Verify all print statements work with special characters in content
- Test PDF processing with files containing Unicode characters

## Current Status

✅ **Multi-Calendar System**: Teacher-based routing operational
✅ **PDF Processing**: Automatic attachment processing enabled (Unicode-safe)
✅ **Secure Credentials**: Google Sheets integration active
✅ **Smart Timing**: Default time assignment based on sender type
✅ **Unicode Safety**: All print statements and text processing Unicode-safe
✅ **Two-Stage AI Processing**: Cost-optimized classification + extraction pipeline
✅ **Token Tracking**: Real-time AI usage monitoring and cost visibility
✅ **Batch Duplicate Detection**: 5x efficiency improvement via batched API calls
✅ **Cost Optimization**: 85-92% reduction vs. naive implementation
✅ **Model Configuration**: Soft-coded models (Sonnet 4.5 + Haiku 4.5) via spreadsheet

## AI Models Used

| Purpose | Model | Cost | Reason |
|---------|-------|------|--------|
| **Email Classification** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | $1/$5 per million tokens | Fast, cheap yes/no decision |
| **Event Extraction** | Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) | $3/$15 per million tokens | Deep understanding, accurate extraction |
| **Duplicate Detection** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | $1/$5 per million tokens | Simple comparison task, batched |

The Mail2Cal system is fully operational, cost-optimized, and ready for production use.