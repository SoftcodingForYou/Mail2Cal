#!/usr/bin/env python3
"""
Mail2Cal - Single Entry Point
Unified script with all features accessible through command-line options
"""

import sys
import argparse
from core.mail2cal import Mail2Cal
from utils.preview_emails import EmailPreview
from utils.cleanup_duplicates import authenticate, find_school_events, find_duplicates, cleanup_duplicates
from utils.check_calendar import check_recent_events
from processors.file_event_processor import FileEventProcessor, check_file_processing_dependencies

# Import credential function (actual loading happens in functions that need them)
from auth.secure_credentials import get_secure_credential

def load_credentials():
    """Load credentials when actually needed"""
    try:
        ANTHROPIC_API_KEY = get_secure_credential('ANTHROPIC_API_KEY')
        GOOGLE_CALENDAR_ID_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')  # Calendar 1 (Class A)
        GOOGLE_CALENDAR_ID_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')  # Calendar 2 (Class B)
        return ANTHROPIC_API_KEY, GOOGLE_CALENDAR_ID_1, GOOGLE_CALENDAR_ID_2
    except Exception as e:
        print(f"[!] Error loading credentials: {e}")
        print("[!] Please ensure your Google Apps Script is deployed and accessible")
        sys.exit(1)

def preview_emails():
    """Preview emails without using AI tokens"""
    print("[*] PREVIEW MODE - No AI tokens will be used")
    print("=" * 60)
    
    preview = EmailPreview()
    emails = preview.get_school_emails()
    
    preview.display_email_summary(emails)
    
    if emails:
        print(f"\n[?] Would you like to see detailed preview of first 5 emails? (y/n): ", end="")
        try:
            response = input().lower().strip()
            if response in ['y', 'yes']:
                preview.display_detailed_preview(emails, 5)
        except:
            pass
        
        print(f"\n[*] Ready to process with AI? You have {len(emails)} emails that will use API tokens.")

def test_limited(limit=3):
    """Test with limited number of emails"""
    print(f"[*] TEST MODE - Processing only {limit} most recent emails")
    print("=" * 60)
    
    from troubleshooting.test_limited import LimitedMail2Cal
    test_app = LimitedMail2Cal()
    test_app.run_test()

def cleanup_duplicates_cmd():
    """Clean up duplicate calendar events"""
    print("[*] CLEANUP MODE - Removing duplicate calendar events")
    print("=" * 60)
    
    # Authenticate
    service = authenticate()
    
    # Find Mail2Cal events
    events = find_school_events(service)
    
    if not events:
        print("[!] No Mail2Cal events found")
        return
    
    # Find duplicates
    duplicates = find_duplicates(events)
    
    if not duplicates:
        print("[+] No duplicates found!")
        return
    
    # Ask for confirmation
    print(f"\n[?] Found duplicates. Proceed with cleanup? (y/n): ", end="")
    try:
        response = input().lower().strip()
        if response not in ['y', 'yes']:
            print("[!] Cleanup cancelled")
            return
    except:
        print("[!] Cleanup cancelled")
        return
    
    # Clean up duplicates
    cleanup_duplicates(service, duplicates)
    print("\n[+] Duplicate cleanup completed!")

def check_calendar():
    """Check current calendar events"""
    print("[*] CALENDAR CHECK - Viewing current events")
    print("=" * 60)
    
    service = authenticate()
    check_recent_events(service)

def process_files():
    """Process local files (PDFs and images) to create calendar events"""
    print("[*] FILE PROCESSING MODE - Processing local files")
    print("=" * 60)
    
    # Check dependencies
    available, status = check_file_processing_dependencies()
    print("File Processing Dependencies:")
    print(status)
    
    if not available:
        print("\n[-] Required libraries not available. Please install them to continue.")
        return
    
    # Initialize Mail2Cal and FileProcessor
    try:
        app = Mail2Cal()
        app.authenticate()
        
        processor = FileEventProcessor(app)
        
        print(f"\n[*] Scanning for files in: {processor.base_directory}")
        results = processor.scan_and_process_files()
        
        # Display results
        print("\n" + "=" * 60)
        print("FILE PROCESSING RESULTS:")
        print(f"Files processed: {results['files_processed']}")
        print(f"Events created: {results['events_created']}")
        print(f"Events updated: {results['events_updated']}")
        print(f"Events enhanced: {results.get('events_enhanced', 0)}")
        print(f"Files skipped (unchanged): {results['files_skipped']}")
        
        if results.get('errors'):
            print(f"Errors: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"  - {error}")
            if len(results['errors']) > 3:
                print(f"  ... and {len(results['errors']) - 3} more errors")
        
        # Show statistics
        stats = processor.get_processing_statistics()
        print(f"\nTotal statistics:")
        print(f"  Files tracked: {stats['total_files_processed']}")
        print(f"  Events created: {stats['total_events_created']}")
        print(f"  Avg events per file: {stats['average_events_per_file']:.1f}")
        
        if stats['files_by_calendar']:
            print(f"  Files by calendar: {stats['files_by_calendar']}")
        
    except Exception as e:
        print(f"[!] Error during file processing: {e}")

def list_files():
    """List all processed files and their status"""
    print("[*] FILE LIST - Showing processed files")
    print("=" * 60)
    
    try:
        app = Mail2Cal()
        app.authenticate()
        
        processor = FileEventProcessor(app)
        files = processor.list_processed_files()
        
        if not files:
            print("No files have been processed yet.")
            print("Use --process-files to scan and process files in local_resources/")
            return
        
        print(f"Found {len(files)} processed files:")
        print()
        
        for i, file_info in enumerate(files, 1):
            print(f"{i:2d}. {file_info['file_name']}")
            print(f"     Calendar: {file_info['calendar_name']}")
            print(f"     Events: {file_info['events_count']}")
            print(f"     Processed: {file_info['processed_at'][:19]}")
            print(f"     Content: {file_info['content_length']} chars")
            print()
        
    except Exception as e:
        print(f"[!] Error listing files: {e}")

def check_file_dependencies():
    """Check file processing dependencies"""
    print("[*] FILE DEPENDENCIES CHECK")
    print("=" * 60)
    
    available, status = check_file_processing_dependencies()
    print(status)
    
    if available:
        print("\n[+] File processing is ready!")
        print("\nDirectory structure expected:")
        print("local_resources/")
        print("|-- Calendar_1/     # Files for Calendar 1 only")
        print("|-- Calendar_2/     # Files for Calendar 2 only")
        print("|-- Both/           # Files for both calendars")
        print("\nSupported formats: PDF, JPG, PNG, TIFF, BMP, EML")
    else:
        print("\n[-] File processing not available")
        print("\nTo enable PDF processing:")
        print("  pip install pdfplumber PyMuPDF")
        print("\nTo enable image OCR:")
        print("  pip install pillow pytesseract")
        print("  (Also requires Tesseract binary installation)")

def run_full_system():
    """Run the complete Mail2Cal system"""
    # Get email count dynamically
    try:
        from utils.preview_emails import EmailPreview
        preview = EmailPreview()
        emails = preview.get_school_emails()
        email_count = len(emails)
        print(f"[*] FULL PROCESSING MODE - All {email_count} emails will be processed with AI")
    except:
        print("[*] FULL PROCESSING MODE - All emails will be processed with AI")
    print("=" * 60)
    
    # Load and validate credentials
    ANTHROPIC_API_KEY, GOOGLE_CALENDAR_ID_1, GOOGLE_CALENDAR_ID_2 = load_credentials()
    if not ANTHROPIC_API_KEY or not GOOGLE_CALENDAR_ID_1 or not GOOGLE_CALENDAR_ID_2:
        print("[-] Error: Missing required credentials from secure storage")
        return
    
    print("[!] This will use Anthropic API tokens to process all emails.")
    print("[?] Continue? (y/n): ", end="")
    try:
        response = input().lower().strip()
        if response not in ['y', 'yes']:
            print("[!] Processing cancelled")
            return
    except:
        print("[!] Processing cancelled")
        return
    
    # Run the full system
    mail2cal = Mail2Cal()
    mail2cal.run()

def main():
    """Main entry point with command-line options"""
    parser = argparse.ArgumentParser(
        description='Mail2Cal - AI-powered email to calendar converter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mail2cal.py --preview           # Preview emails without using AI tokens
  python run_mail2cal.py --test              # Test with 3 recent emails
  python run_mail2cal.py --cleanup           # Clean up duplicate calendar events
  python run_mail2cal.py --check             # View current calendar events
  python run_mail2cal.py --full              # Process all emails with AI
  python run_mail2cal.py                     # Interactive mode (default)
        """
    )
    
    parser.add_argument('--preview', action='store_true',
                       help='Preview emails without using AI tokens')
    parser.add_argument('--test', action='store_true',
                       help='Test with 3 most recent emails')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up duplicate calendar events')
    parser.add_argument('--check', action='store_true',
                       help='Check current calendar events')
    parser.add_argument('--full', action='store_true',
                       help='Process all emails with AI (uses tokens)')
    parser.add_argument('--process-files', action='store_true',
                       help='Process local files (PDFs and images) for calendar events')
    parser.add_argument('--list-files', action='store_true',
                       help='List all processed files and their status')
    parser.add_argument('--check-file-deps', action='store_true',
                       help='Check file processing dependencies')
    parser.add_argument('--limit', type=int, default=3,
                       help='Number of emails for test mode (default: 3)')
    
    args = parser.parse_args()
    
    # Handle command-line options
    if args.preview:
        preview_emails()
    elif args.test:
        test_limited(args.limit)
    elif args.cleanup:
        cleanup_duplicates_cmd()
    elif args.check:
        check_calendar()
    elif args.full:
        run_full_system()
    elif args.process_files:
        process_files()
    elif args.list_files:
        list_files()
    elif args.check_file_deps:
        check_file_dependencies()
    else:
        # Interactive mode
        interactive_mode()

def interactive_mode():
    """Interactive mode for selecting options"""
    print("""
[*] Mail2Cal - AI-powered Email to Calendar Converter
=====================================================

Select an option:

1. Preview emails (no AI tokens used)
2. Test with 3 recent emails (minimal tokens)
3. Clean up duplicate calendar events
4. Check current calendar events
5. Process ALL emails (full AI processing)
6. Process local files (PDFs and images)
7. List processed files
8. Check file processing dependencies
9. Exit

""")
    
    try:
        choice = input("Enter choice (1-9): ").strip()
        
        if choice == '1':
            preview_emails()
        elif choice == '2':
            test_limited(3)
        elif choice == '3':
            cleanup_duplicates_cmd()
        elif choice == '4':
            check_calendar()
        elif choice == '5':
            run_full_system()
        elif choice == '6':
            process_files()
        elif choice == '7':
            list_files()
        elif choice == '8':
            check_file_dependencies()
        elif choice == '9':
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter 1-9.")
            interactive_mode()
    
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        interactive_mode()

if __name__ == "__main__":
    main()