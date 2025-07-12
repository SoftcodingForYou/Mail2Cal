# Mail2Cal - AI-Powered Email to Calendar Converter

An intelligent system that converts school emails into Google Calendar events using Claude AI, with multi-calendar support for different classes.

## 🔒 Security Notice

This repository contains **no sensitive credentials**. All API keys and personal information are stored securely via Google Sheets integration. See [`SETUP_GUIDE.md`](SETUP_GUIDE.md) for configuration instructions.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Follow setup guide for complete configuration
# See SETUP_GUIDE.md for detailed instructions

# Run the application
python run_mail2cal.py
```

## 📁 Project Structure

```
Mail2Cal/
├── 📄 Core Application
│   ├── run_mail2cal.py                 # Main entry point (START HERE)
│   ├── mail2cal.py                     # Core Mail2Cal class
│   ├── ai_parser.py                    # Claude AI integration
│   ├── event_tracker.py                # Event tracking system
│   ├── pdf_attachment_processor.py     # PDF processing
│   └── secure_credentials.py           # Secure credential management
│
├── 🛠️ utils/                           # Utility Scripts
│   ├── preview_emails.py               # Preview emails (no AI tokens)
│   ├── cleanup_duplicates.py           # Remove duplicate events
│   └── check_calendar.py               # View calendar events
│
├── 🔧 troubleshooting/                 # Troubleshooting & Testing
│   ├── test_setup.py                   # Validate installation
│   ├── test_gmail_auth.py              # Test Gmail authentication
│   └── test_limited.py                 # Test with limited emails
│
├── 📚 docs/                            # Documentation
│   └── CLAUDE.md                      # Complete documentation
│
└── 📋 Essential Files
    ├── README.md                       # Project overview
    ├── SETUP_GUIDE.md                  # Setup instructions  
    ├── requirements.txt                # Python dependencies
    ├── secure_credentials_config.py    # Google Apps Script URL
    ├── credentials.json                # OAuth credentials (user-provided)
    ├── token.pickle                    # Saved authentication tokens
    └── event_mappings.json             # Email-to-event tracking database
```

## 🎯 Usage

### Main Application
```bash
# Interactive mode (recommended for beginners)
python run_mail2cal.py

# Direct commands
python run_mail2cal.py --preview    # Preview emails (no AI tokens)
python run_mail2cal.py --test       # Test with 3 emails
python run_mail2cal.py --full       # Process all emails with AI
```

### Utilities (from project root)
```bash
# Calendar management
python utils/check_both_calendars.py
python utils/migrate_calendar_events.py
python utils/analyze_email_routing.py

# System maintenance
python utils/cleanup_duplicates.py
python utils/preview_emails.py
```

### Troubleshooting (from project root)
```bash
# System validation
python troubleshooting/test_setup.py
python troubleshooting/test_gmail_auth.py

# Testing & debugging
python troubleshooting/test_multi_calendar.py
python troubleshooting/test_limited.py
```

## 🎓 Multi-Calendar System

The system automatically routes emails to appropriate calendars:

- **Teacher 1 emails** → Calendar 1 only (8:00 AM default timing)
- **Teacher 2 emails** → Calendar 2 only (8:00 AM default timing)
- **Teacher 3 & 4 emails (Afterschool)** → Both calendars (1:00 PM default timing)
- **Other school emails** → Both calendars (all-day events)

## 📄 PDF Attachment Processing

The system now automatically processes PDF attachments containing important school information:

### 🔍 **What PDFs are Processed:**
- Holiday calendars and exceptional days off
- Special activity schedules  
- School event programs
- Class timetable changes
- Administrative announcements

### 🤖 **How It Works:**
1. **Auto-Detection**: Automatically finds PDF attachments in emails
2. **Text Extraction**: Extracts text from PDFs using advanced libraries
3. **AI Integration**: Includes PDF content in Claude analysis
4. **Event Creation**: Generates calendar events from PDF information

### ⚙️ **Setup Requirements:**
```bash
pip install pdfplumber PyMuPDF
```

## 📖 Documentation

- **Setup**: [`SETUP_GUIDE.md`](SETUP_GUIDE.md) - Quick setup instructions
- **Complete Documentation**: [`docs/CLAUDE.md`](docs/CLAUDE.md) - Full system documentation

## 🆘 Need Help?

1. **Installation issues**: Run `python troubleshooting/test_setup.py`
2. **Authentication problems**: Run `python troubleshooting/test_gmail_auth.py` 
3. **Limited testing**: Run `python troubleshooting/test_limited.py`
4. **General questions**: Check `docs/CLAUDE.md`

## ✅ Current Status

- **Calendar 1**: Teacher 1 events + afterschool events (Teachers 3&4) + other school senders
- **Calendar 2**: Teacher 2 events + afterschool events (Teachers 3&4) + other school senders
- **System**: Fully operational with correct multi-calendar routing
- **Migration**: All events properly distributed (July 2025)