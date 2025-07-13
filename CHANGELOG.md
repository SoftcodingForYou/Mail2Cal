# Mail2Cal Changelog

## Repository Reorganization - July 2025

### 📁 Restructured Directories
- **core/** - Core application logic (mail2cal.py, ai_parser.py, etc.)
- **processors/** - Content processing modules (file_event_processor.py, etc.)
- **auth/** - Authentication and credential management
- **utils/** - Utility scripts (preview, cleanup, etc.)
- **local_resources/** - File processing directories

### 🗑️ Removed Files
- `cleanup_file_events.py` - Temporary cleanup script
- `fix_cheerleaders_schedule.py` - Temporary fix script  
- `test_json_fix.py` - JSON debugging test
- `test_cache.json` - Test cache file
- `test_event_mappings.json` - Test mappings
- `troubleshooting/` - Entire troubleshooting directory
- `nul` - Empty file artifact

### ✨ Repository Features (Final State)
- **Core Email Processing**: Full AI-powered email to calendar conversion
- **File Processing**: PDF and image OCR processing with AI event extraction
- **Smart Routing**: Multi-calendar support with numbered teacher system
- **Duplicate Prevention**: Global event cache with intelligent similarity detection
- **Recurring Events**: Proper weekly recurring event creation
- **Secure Credentials**: Google Sheets-based credential management
- **Clean Codebase**: Production-ready with comprehensive documentation

### 📁 Final Structure
```
Mail2Cal/
├── run_mail2cal.py           # Main entry point
├── core/                     # Core logic (4 files)
├── processors/               # Content processors (2 files)
├── auth/                     # Authentication (2 files)
├── utils/                    # Utilities (4 files)
├── local_resources/          # File processing (3 directories)
├── docs/                     # Documentation (1 file)
└── config files              # Requirements, README, etc.
```

### 🎯 Current Capabilities
- ✅ Email processing with PDF attachments
- ✅ Local file processing (PDFs + images with OCR)
- ✅ Multi-calendar routing (Teacher 1→Calendar 1, etc.)
- ✅ Recurring event creation for weekly activities
- ✅ Smart duplicate prevention
- ✅ File change detection and event updates
- ✅ Comprehensive CLI interface

Total: **21 core files** (down from 30+ with test files)