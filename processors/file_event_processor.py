#!/usr/bin/env python3
"""
File-based Event Processor for Mail2Cal
Processes local PDF and image files to extract calendar events
Follows the same creation/updating/deletion logic as email processing
"""

import os
import hashlib
import json
import email
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import mimetypes
import base64
from bs4 import BeautifulSoup

# OCR and image processing
try:
    from PIL import Image
    import pytesseract
    
    # Configure Tesseract path for Windows
    import os
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(os.getenv('USERNAME', '')),
        "tesseract"  # If in PATH
    ]
    
    tesseract_found = False
    for path in tesseract_paths:
        if os.path.exists(path) or path == "tesseract":
            try:
                if path != "tesseract":
                    pytesseract.pytesseract.tesseract_cmd = path
                # Test if it works
                pytesseract.get_tesseract_version()
                tesseract_found = True
                print(f"[+] Tesseract found at: {path}")
                break
            except:
                continue
    
    OCR_AVAILABLE = tesseract_found
    if not tesseract_found:
        print("[!] Tesseract binary not accessible. OCR disabled.")
        
except ImportError:
    OCR_AVAILABLE = False
    print("[!] OCR not available. Install with: pip install pillow pytesseract")

# PDF processing (reuse existing)
try:
    import pdfplumber
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class FileEventProcessor:
    """
    Processes local files (PDFs, images) to extract calendar events
    Maintains file tracking similar to email tracking
    """
    
    def __init__(self, mail2cal_instance, base_directory: str = "local_resources"):
        self.mail2cal = mail2cal_instance
        self.base_directory = Path(base_directory)
        self.file_mappings_file = "file_event_mappings.json"
        self.file_mappings = self._load_file_mappings()
        
        # Calendar directory mapping
        self.calendar_mapping = {
            "Calendar_1": self.mail2cal.config['calendars']['calendar_id_1'],
            "Calendar_2": self.mail2cal.config['calendars']['calendar_id_2'],
            "Both": "both_calendars"  # For events that should go to both calendars
        }
        
        print(f"[*] File processor initialized with base directory: {self.base_directory}")
    
    def _load_file_mappings(self) -> Dict:
        """Load file-to-event mappings from storage"""
        try:
            with open(self.file_mappings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_file_mappings(self):
        """Save file-to-event mappings to storage"""
        try:
            with open(self.file_mappings_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_mappings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Error saving file mappings: {e}")
    
    def generate_file_hash(self, file_path: Path) -> str:
        """Generate hash for file content to detect changes"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            print(f"[!] Error generating hash for {file_path}: {e}")
            return ""
    
    def scan_and_process_files(self) -> Dict:
        """
        Scan the local_resources directory and process all files
        Returns summary of processing results
        """
        print(f"[*] Scanning directory: {self.base_directory}")
        
        if not self.base_directory.exists():
            print(f"[!] Directory not found: {self.base_directory}")
            return {"error": "Directory not found"}
        
        results = {
            "files_processed": 0,
            "events_created": 0,
            "events_updated": 0,
            "events_enhanced": 0,
            "files_skipped": 0,
            "errors": []
        }
        
        # Scan each calendar subdirectory
        for calendar_dir in self.base_directory.iterdir():
            if not calendar_dir.is_dir():
                continue
                
            calendar_name = calendar_dir.name
            if calendar_name not in self.calendar_mapping:
                print(f"[!] Unknown calendar directory: {calendar_name}")
                results["errors"].append(f"Unknown calendar directory: {calendar_name}")
                continue
            
            print(f"[*] Processing files for {calendar_name}")
            
            # Process files recursively in this calendar directory
            self._process_directory_recursively(calendar_dir, calendar_name, results)
        
        return results
    
    def _process_directory_recursively(self, directory: Path, calendar_name: str, results: Dict):
        """Recursively process all supported files in a directory and its subdirectories"""
        for item_path in directory.iterdir():
            if item_path.is_file() and self._is_supported_file(item_path):
                # Process the file
                try:
                    print(f"[*] Found file: {item_path.relative_to(self.base_directory)}")
                    file_result = self._process_single_file(item_path, calendar_name)
                    
                    results["files_processed"] += 1
                    if file_result["action"] == "created":
                        results["events_created"] += file_result["events_count"]
                    elif file_result["action"] == "updated":
                        results["events_updated"] += file_result["events_count"]
                    elif file_result["action"] == "enhanced":
                        results["events_enhanced"] += file_result["events_count"]
                    elif file_result["action"] == "skipped":
                        results["files_skipped"] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing {item_path.name}: {e}"
                    print(f"[!] {error_msg}")
                    results["errors"].append(error_msg)
            
            elif item_path.is_dir():
                # Recursively process subdirectory
                print(f"[*] Scanning subdirectory: {item_path.relative_to(self.base_directory)}")
                self._process_directory_recursively(item_path, calendar_name, results)
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported"""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        supported_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'image/bmp',
            'message/rfc822'  # EML files
        ]
        
        return (mime_type in supported_types or 
                file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.eml'])
    
    def _process_single_file(self, file_path: Path, calendar_name: str) -> Dict:
        """
        Process a single file and extract events
        Returns: {"action": "created|updated|skipped", "events_count": int}
        """
        file_id = str(file_path.relative_to(self.base_directory))
        current_hash = self.generate_file_hash(file_path)
        
        # Check if file has been processed before
        if file_id in self.file_mappings:
            stored_hash = self.file_mappings[file_id]["file_hash"]
            if stored_hash == current_hash:
                print(f"[*] File unchanged, skipping: {file_path.name}")
                return {"action": "skipped", "events_count": 0}
            else:
                print(f"[*] File changed, reprocessing: {file_path.name}")
                return self._update_file_events(file_path, file_id, current_hash, calendar_name)
        else:
            print(f"[*] New file, processing: {file_path.name}")
            return self._create_file_events(file_path, file_id, current_hash, calendar_name)
    
    def _create_file_events(self, file_path: Path, file_id: str, file_hash: str, calendar_name: str) -> Dict:
        """Create events for a new file"""
        
        # Handle EML files differently - parse as actual emails
        if file_path.suffix.lower() == '.eml':
            return self._create_eml_events(file_path, file_id, file_hash, calendar_name)
        
        # Extract text content from file
        content = self._extract_file_content(file_path)
        if not content:
            print(f"[!] Could not extract content from: {file_path.name}")
            return {"action": "skipped", "events_count": 0}
        
        print(f"[+] Extracted {len(content)} characters from {file_path.name}")
        
        # Create fake email structure for AI processing
        fake_email = {
            'id': f"file_{file_id}",
            'subject': f"Local File: {file_path.name}",
            'sender': f"File System - {calendar_name}",
            'date': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%a, %d %b %Y %H:%M:%S +0000'),
            'body': content
        }
        
        # Use existing AI parser to extract events
        events = self.mail2cal.parse_events_from_email(fake_email)
        
        if not events:
            print(f"[!] No events found in file: {file_path.name}")
            return {"action": "skipped", "events_count": 0}
        
        print(f"[+] Found {len(events)} event(s) in {file_path.name}")
        
        # Determine target calendars
        target_calendars = self._get_target_calendars(calendar_name)
        
        # Create events in calendar(s) with full duplicate checking
        created_events = []
        
        # Check for similar events in the email tracker (cross-system duplicate detection)
        similar_events = self.mail2cal.event_tracker.find_similar_events(events)
        
        for event in events:
            event_signature = self.mail2cal.event_tracker.generate_event_signature(event)
            
            # Process event for each target calendar
            for calendar_id in target_calendars:
                calendar_name_display = "Calendar 1" if calendar_id == self.mail2cal.config['calendars']['calendar_id_1'] else "Calendar 2"
                
                # Check if we have a similar event from emails already
                if event_signature in similar_events:
                    existing_event_id = similar_events[event_signature]
                    print(f"[~] Found similar event (email tracker): {event.get('summary', '')[:50]}... (ID: {existing_event_id})")
                    
                    # Try to enhance the existing event with new information
                    if self._enhance_existing_event(existing_event_id, event, calendar_id):
                        print(f"[+] Enhanced existing event with new information from file")
                        created_events.append({
                            'calendar_event_id': existing_event_id,
                            'calendar_id': calendar_id,
                            'summary': event.get('summary', ''),
                            'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                            'created_at': datetime.now().isoformat(),
                            'action': 'enhanced'
                        })
                    continue
                
                try:
                    # This call also does global cache + calendar duplicate checking
                    event_id = self.mail2cal.create_calendar_event(event, calendar_id)
                    
                    # If create_calendar_event returns None, it might be a duplicate
                    # Try to find and enhance the existing event
                    if not event_id:
                        existing_event_id = self.mail2cal.check_for_duplicate_event(event, calendar_id)
                        if existing_event_id and self._enhance_existing_event(existing_event_id, event, calendar_id):
                            print(f"[+] Enhanced existing calendar event with new information")
                            created_events.append({
                                'calendar_event_id': existing_event_id,
                                'calendar_id': calendar_id,
                                'summary': event.get('summary', ''),
                                'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                                'created_at': datetime.now().isoformat(),
                                'action': 'enhanced'
                            })
                        continue
                    
                    if event_id:
                        created_events.append({
                            'calendar_event_id': event_id,
                            'calendar_id': calendar_id,
                            'summary': event.get('summary', ''),
                            'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                            'created_at': datetime.now().isoformat(),
                            'action': 'created'
                        })
                        print(f"[+] Created event in {calendar_name_display}: {event.get('summary', '')[:50]}...")
                except Exception as e:
                    print(f"[!] Error creating event: {e}")
        
        # Track the file mapping
        self.file_mappings[file_id] = {
            'file_path': str(file_path),
            'file_hash': file_hash,
            'file_name': file_path.name,
            'calendar_name': calendar_name,
            'processed_at': datetime.now().isoformat(),
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'calendar_events': created_events,
            'content_length': len(content)
        }
        
        self._save_file_mappings()
        
        # Also track these events in the main email tracker for cross-system duplicate detection
        if created_events:
            # Create calendar event IDs list for email tracker
            calendar_event_ids = [event['calendar_event_id'] for event in created_events]
            # Track the file processing (treating file as a pseudo-email)
            self.mail2cal.event_tracker.track_email_processing(fake_email, events, calendar_event_ids)
        
        # Determine the action based on what happened
        enhanced_count = len([e for e in created_events if e.get('action') == 'enhanced'])
        created_count = len([e for e in created_events if e.get('action') == 'created'])
        
        if enhanced_count > 0 and created_count == 0:
            return {"action": "enhanced", "events_count": enhanced_count}
        elif enhanced_count > 0 and created_count > 0:
            return {"action": "mixed", "events_count": len(created_events), "enhanced": enhanced_count, "created": created_count}
        else:
            return {"action": "created", "events_count": created_count}
    
    def _update_file_events(self, file_path: Path, file_id: str, file_hash: str, calendar_name: str) -> Dict:
        """Update events for a changed file"""
        
        # Delete existing events
        existing_mapping = self.file_mappings[file_id]
        deleted_count = 0
        
        for event_info in existing_mapping.get('calendar_events', []):
            try:
                self.mail2cal.calendar_service.events().delete(
                    calendarId=event_info['calendar_id'],
                    eventId=event_info['calendar_event_id']
                ).execute()
                deleted_count += 1
                print(f"[+] Deleted outdated event: {event_info['summary'][:50]}...")
            except Exception as e:
                print(f"[!] Error deleting event {event_info['calendar_event_id']}: {e}")
        
        # Create new events
        result = self._create_file_events(file_path, file_id, file_hash, calendar_name)
        
        print(f"[+] Updated file events: deleted {deleted_count}, created {result['events_count']}")
        
        return {"action": "updated", "events_count": result["events_count"]}
    
    def _extract_file_content(self, file_path: Path) -> str:
        """Extract text content from PDF or image file"""
        
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.pdf':
            return self._extract_pdf_content(file_path)
        elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            return self._extract_image_content(file_path)
        elif file_extension == '.eml':
            return self._extract_eml_content(file_path)
        else:
            print(f"[!] Unsupported file type: {file_extension}")
            return ""
    
    def _extract_pdf_content(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        if not PDF_AVAILABLE:
            print("[!] PDF processing libraries not available")
            return ""
        
        content = []
        
        # Try pdfplumber first
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        content.append(f"\n--- PÁGINA {page_num} (TABLAS) ---")
                        for table_num, table in enumerate(tables, 1):
                            content.append(f"\nTabla {table_num}:")
                            for row in table:
                                if row:
                                    row_text = " | ".join([cell or "" for cell in row])
                                    content.append(row_text)
                    
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        content.append(f"\n--- PÁGINA {page_num} (TEXTO) ---")
                        content.append(page_text)
            
            return "\n".join(content)
            
        except Exception as e:
            print(f"[!] pdfplumber failed for {file_path.name}: {e}")
            
            # Fallback to PyMuPDF
            try:
                doc = fitz.open(file_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    
                    if page_text.strip():
                        content.append(f"\n--- PÁGINA {page_num + 1} ---")
                        content.append(page_text)
                
                doc.close()
                return "\n".join(content)
                
            except Exception as e2:
                print(f"[!] PyMuPDF also failed for {file_path.name}: {e2}")
                return ""
    
    def _extract_image_content(self, file_path: Path) -> str:
        """Extract text from image using OCR"""
        if not OCR_AVAILABLE:
            print("[!] OCR libraries not available")
            return ""
        
        try:
            # Ensure file_path is a Path object
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            # Open image
            image = Image.open(file_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(image, lang='spa+eng')  # Spanish + English
            
            if text.strip():
                return f"=== CONTENIDO EXTRAÍDO DE IMAGEN: {file_path.name} ===\n{text}\n=== FIN DE IMAGEN ==="
            else:
                print(f"[!] No text found in image: {file_path.name}")
                return ""
                
        except Exception as e:
            print(f"[!] OCR failed for {file_path.name}: {e}")
            return ""
    
    def _get_target_calendars(self, calendar_name: str) -> List[str]:
        """Get target calendar IDs based on directory name"""
        if calendar_name == "Calendar_1":
            return [self.calendar_mapping["Calendar_1"]]
        elif calendar_name == "Calendar_2":
            return [self.calendar_mapping["Calendar_2"]]
        elif calendar_name == "Both":
            return [self.calendar_mapping["Calendar_1"], self.calendar_mapping["Calendar_2"]]
        else:
            # Default to both calendars for unknown directories
            return [self.calendar_mapping["Calendar_1"], self.calendar_mapping["Calendar_2"]]
    
    def delete_file_events(self, file_path: str) -> bool:
        """Delete events associated with a file (when file is removed)"""
        file_id = file_path
        
        if file_id not in self.file_mappings:
            print(f"[!] No mapping found for file: {file_path}")
            return False
        
        mapping = self.file_mappings[file_id]
        deleted_count = 0
        
        for event_info in mapping.get('calendar_events', []):
            try:
                self.mail2cal.calendar_service.events().delete(
                    calendarId=event_info['calendar_id'],
                    eventId=event_info['calendar_event_id']
                ).execute()
                deleted_count += 1
                print(f"[+] Deleted event: {event_info['summary'][:50]}...")
            except Exception as e:
                print(f"[!] Error deleting event {event_info['calendar_event_id']}: {e}")
        
        # Remove from mappings
        del self.file_mappings[file_id]
        self._save_file_mappings()
        
        print(f"[+] Deleted {deleted_count} events for removed file: {file_path}")
        return True
    
    def get_processing_statistics(self) -> Dict:
        """Get statistics about processed files"""
        total_files = len(self.file_mappings)
        total_events = sum(
            len(mapping.get('calendar_events', []))
            for mapping in self.file_mappings.values()
        )
        
        # Count by calendar
        calendar_stats = {}
        for mapping in self.file_mappings.values():
            calendar_name = mapping.get('calendar_name', 'Unknown')
            calendar_stats[calendar_name] = calendar_stats.get(calendar_name, 0) + 1
        
        return {
            'total_files_processed': total_files,
            'total_events_created': total_events,
            'files_by_calendar': calendar_stats,
            'average_events_per_file': total_events / total_files if total_files > 0 else 0
        }
    
    def list_processed_files(self) -> List[Dict]:
        """List all processed files with their details"""
        files = []
        for file_id, mapping in self.file_mappings.items():
            files.append({
                'file_id': file_id,
                'file_name': mapping.get('file_name', ''),
                'calendar_name': mapping.get('calendar_name', ''),
                'processed_at': mapping.get('processed_at', ''),
                'events_count': len(mapping.get('calendar_events', [])),
                'content_length': mapping.get('content_length', 0)
            })
        
        return sorted(files, key=lambda x: x['processed_at'], reverse=True)
    
    def _create_eml_events(self, file_path: Path, file_id: str, file_hash: str, calendar_name: str) -> Dict:
        """Create events for a new EML file"""
        
        # Parse EML file into email format
        email_data = self._parse_eml_file(file_path)
        if not email_data:
            return {"action": "skipped", "events_count": 0}
        
        print(f"[+] Parsed EML: {email_data['subject'][:50]}...")
        print(f"[+] From: {email_data['sender']}")
        print(f"[+] Date: {email_data['date']}")
        print(f"[+] Body length: {len(email_data['body'])} characters")
        
        # Use existing AI parser to extract events (same as Gmail emails)
        events = self.mail2cal.parse_events_from_email(email_data)
        
        if not events:
            print(f"[!] No events found in EML: {file_path.name}")
            return {"action": "skipped", "events_count": 0}
        
        print(f"[+] Found {len(events)} event(s) in EML")
        
        # Determine target calendars based on calendar directory
        target_calendars = self._get_target_calendars(calendar_name)
        
        # Create events in calendar(s) with full duplicate checking (same as Gmail processing)
        created_events = []
        
        # Check for similar events in the email tracker (cross-system duplicate detection)
        similar_events = self.mail2cal.event_tracker.find_similar_events(events)
        
        for event in events:
            # Add source email ID for tracking
            event['source_email_id'] = email_data['id']
            event_signature = self.mail2cal.event_tracker.generate_event_signature(event)
            
            # Process event for each target calendar
            for calendar_id in target_calendars:
                calendar_name_display = "Calendar 1" if calendar_id == self.mail2cal.config['calendars']['calendar_id_1'] else "Calendar 2"
                
                # Check if we have a similar event from emails already
                if event_signature in similar_events:
                    existing_event_id = similar_events[event_signature]
                    print(f"[~] Found similar event (email tracker): {event.get('summary', '')[:50]}... (ID: {existing_event_id})")
                    
                    # Try to enhance the existing event with new information
                    if self._enhance_existing_event(existing_event_id, event, calendar_id):
                        print(f"[+] Enhanced existing event with new information from EML")
                        created_events.append({
                            'calendar_event_id': existing_event_id,
                            'calendar_id': calendar_id,
                            'summary': event.get('summary', ''),
                            'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                            'created_at': datetime.now().isoformat(),
                            'action': 'enhanced'
                        })
                    continue
                
                try:
                    # This call also does global cache + calendar duplicate checking
                    event_id = self.mail2cal.create_calendar_event(event, calendar_id)
                    
                    # If create_calendar_event returns None, it might be a duplicate
                    # Try to find and enhance the existing event
                    if not event_id:
                        existing_event_id = self.mail2cal.check_for_duplicate_event(event, calendar_id)
                        if existing_event_id and self._enhance_existing_event(existing_event_id, event, calendar_id):
                            print(f"[+] Enhanced existing calendar event with new information")
                            created_events.append({
                                'calendar_event_id': existing_event_id,
                                'calendar_id': calendar_id,
                                'summary': event.get('summary', ''),
                                'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                                'created_at': datetime.now().isoformat(),
                                'action': 'enhanced'
                            })
                        continue
                    
                    if event_id:
                        created_events.append({
                            'calendar_event_id': event_id,
                            'calendar_id': calendar_id,
                            'summary': event.get('summary', ''),
                            'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                            'created_at': datetime.now().isoformat(),
                            'action': 'created'
                        })
                        print(f"[+] Created event in {calendar_name_display}: {event.get('summary', '')[:50]}...")
                except Exception as e:
                    print(f"[!] Error creating event: {e}")
        
        # Track the EML mapping
        self.file_mappings[file_id] = {
            'file_path': str(file_path),
            'file_hash': file_hash,
            'file_name': file_path.name,
            'calendar_name': calendar_name,
            'processed_at': datetime.now().isoformat(),
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'calendar_events': created_events,
            'content_length': len(email_data['body']),
            'file_type': 'eml',
            'email_data': {
                'subject': email_data['subject'],
                'sender': email_data['sender'],
                'date': email_data['date'],
                'body_length': len(email_data['body'])
            }
        }
        
        self._save_file_mappings()
        
        # Also track these events in the main email tracker for cross-system duplicate detection
        if created_events:
            # Create calendar event IDs list for email tracker
            calendar_event_ids = [event['calendar_event_id'] for event in created_events]
            # Track the EML processing (treating it as a real email)
            self.mail2cal.event_tracker.track_email_processing(email_data, events, calendar_event_ids)
        
        # Determine the action based on what happened
        enhanced_count = len([e for e in created_events if e.get('action') == 'enhanced'])
        created_count = len([e for e in created_events if e.get('action') == 'created'])
        
        if enhanced_count > 0 and created_count == 0:
            return {"action": "enhanced", "events_count": enhanced_count}
        elif enhanced_count > 0 and created_count > 0:
            return {"action": "mixed", "events_count": len(created_events), "enhanced": enhanced_count, "created": created_count}
        else:
            return {"action": "created", "events_count": created_count}
    
    def _parse_eml_file(self, file_path: Path) -> Dict:
        """Parse EML file into the same format as Gmail emails"""
        try:
            with open(file_path, 'rb') as f:
                email_message = email.message_from_bytes(f.read())
            
            # Extract headers (same format as Gmail)
            subject = email_message.get('Subject', '')
            sender = email_message.get('From', '')
            date_str = email_message.get('Date', '')
            message_id = email_message.get('Message-ID', f"eml_{file_path.name}")
            
            # Extract body using the same logic as Gmail processing
            body = self._extract_eml_body(email_message)
            
            # Create email dict in same format as Gmail messages
            email_data = {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date_str,
                'body': body,
                'snippet': body[:150] + "..." if len(body) > 150 else body,
                'has_pdf_attachments': False  # TODO: Could add attachment processing later
            }
            
            return email_data
            
        except Exception as e:
            print(f"[!] Error parsing EML file {file_path}: {e}")
            return None
    
    def _extract_eml_body(self, email_message) -> str:
        """Extract email body with improved parsing (same as Gmail processing)"""
        body_parts = []
        
        def extract_from_part(part):
            """Recursively extract text from email parts"""
            if part.is_multipart():
                # Multipart message, recurse into parts
                for subpart in part.get_payload():
                    extract_from_part(subpart)
            else:
                # Single part, extract content
                content_type = part.get_content_type()
                charset = part.get_content_charset() or 'utf-8'
                
                try:
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            text = payload.decode(charset, errors='ignore').strip()
                            if text:
                                body_parts.append(text)
                    elif content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            html = payload.decode(charset, errors='ignore')
                            # Parse HTML and extract text
                            soup = BeautifulSoup(html, 'html.parser')
                            # Remove script and style elements
                            for script in soup(["script", "style"]):
                                script.decompose()
                            text = soup.get_text()
                            # Clean up whitespace
                            lines = (line.strip() for line in text.splitlines())
                            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                            text = ' '.join(chunk for chunk in chunks if chunk)
                            if text.strip():
                                body_parts.append(text.strip())
                except Exception as e:
                    print(f"[!] Error decoding part {content_type}: {e}")
        
        # Start extraction
        extract_from_part(email_message)
        
        # Combine all parts
        body = '\n\n'.join(body_parts)
        
        return body.strip()
    
    def _extract_eml_content(self, file_path: Path) -> str:
        """Extract content from EML file - this method is kept for consistency but not used for EML processing"""
        # EML files are processed directly as emails via _create_eml_events
        # This method exists for consistency with other file types
        email_data = self._parse_eml_file(file_path)
        if email_data:
            return email_data['body']
        return ""
    
    def _enhance_existing_event(self, existing_event_id: str, new_event: Dict, calendar_id: str) -> bool:
        """
        Enhance an existing calendar event with additional information from new sources.
        Returns True if the event was successfully enhanced.
        """
        try:
            # Get the existing event from Google Calendar
            existing_event = self.mail2cal.calendar_service.events().get(
                calendarId=calendar_id,
                eventId=existing_event_id
            ).execute()
            
            print(f"[*] Analyzing existing event for enhancement opportunities...")
            
            # Track what gets enhanced
            enhancements = []
            enhanced = False
            
            # 1. Enhance description with additional details
            existing_description = existing_event.get('description', '')
            new_description = new_event.get('description', '')
            
            if new_description and new_description not in existing_description:
                # Merge descriptions intelligently
                if existing_description:
                    # Add new information as a separate section
                    enhanced_description = f"{existing_description}\n\n--- INFORMACIÓN ADICIONAL ---\n{new_description}"
                else:
                    enhanced_description = new_description
                
                existing_event['description'] = enhanced_description
                enhancements.append("description")
                enhanced = True
            
            # 2. Enhance location if missing or add alternative location
            existing_location = existing_event.get('location', '')
            new_location = new_event.get('location', '')
            
            if new_location and new_location not in existing_location:
                if not existing_location:
                    existing_event['location'] = new_location
                    enhancements.append("location")
                    enhanced = True
                elif new_location.lower() != existing_location.lower():
                    # Add as alternative location
                    existing_event['location'] = f"{existing_location} / {new_location}"
                    enhancements.append("location (alternative)")
                    enhanced = True
            
            # 3. Enhance time precision if the new event has more specific timing
            if self._has_better_time_info(existing_event, new_event):
                # Update with more precise timing
                if new_event.get('start_time') and not new_event.get('all_day'):
                    start_dt = new_event['start_time']
                    end_dt = new_event.get('end_time') or start_dt + timedelta(hours=1)
                    
                    existing_event['start'] = {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
                    existing_event['end'] = {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
                    enhancements.append("time precision")
                    enhanced = True
            
            # 4. Add source information to extended properties
            if 'extendedProperties' not in existing_event:
                existing_event['extendedProperties'] = {'private': {}}
            
            # Track sources that contributed to this event
            sources = existing_event['extendedProperties']['private'].get('mail2cal_sources', '')
            new_source = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if sources:
                existing_event['extendedProperties']['private']['mail2cal_sources'] = f"{sources}, {new_source}"
            else:
                existing_event['extendedProperties']['private']['mail2cal_sources'] = new_source
            
            existing_event['extendedProperties']['private']['mail2cal_enhanced_at'] = datetime.now().isoformat()
            
            # 5. Update the event if we made any enhancements
            if enhanced:
                result = self.mail2cal.calendar_service.events().update(
                    calendarId=calendar_id,
                    eventId=existing_event_id,
                    body=existing_event
                ).execute()
                
                print(f"[+] Enhanced with: {', '.join(enhancements)}")
                return True
            else:
                print(f"[*] No new information to add")
                return False
                
        except Exception as e:
            print(f"[!] Error enhancing existing event: {e}")
            return False
    
    def _has_better_time_info(self, existing_event: Dict, new_event: Dict) -> bool:
        """Check if the new event has better/more precise time information"""
        # If existing event is all-day and new event has specific time
        existing_start = existing_event.get('start', {})
        if 'date' in existing_start and new_event.get('start_time') and not new_event.get('all_day'):
            return True
        
        # If existing event has generic time (8:00 AM) and new event has different specific time
        if 'dateTime' in existing_start:
            existing_time = existing_start['dateTime']
            if '08:00:00' in existing_time and new_event.get('start_time'):
                new_time = new_event['start_time'].time()
                if new_time.hour != 8 or new_time.minute != 0:
                    return True
        
        return False


def check_file_processing_dependencies() -> Tuple[bool, str]:
    """Check if required libraries for file processing are available"""
    status = []
    
    if PDF_AVAILABLE:
        status.append("[+] PDF processing available (pdfplumber, PyMuPDF)")
    else:
        status.append("[-] PDF processing missing - install with: pip install pdfplumber PyMuPDF")
    
    if OCR_AVAILABLE:
        status.append("[+] OCR available (Pillow, pytesseract)")
    else:
        status.append("[-] OCR missing - install with: pip install pillow pytesseract")
        status.append("   Note: Also requires Tesseract binary installation")
    
    available = PDF_AVAILABLE or OCR_AVAILABLE
    return available, "\n".join(status)


if __name__ == "__main__":
    # Test dependencies
    available, status = check_file_processing_dependencies()
    print("File Processing Dependencies:")
    print(status)
    
    if available:
        print("\n✅ File processing capabilities available!")
    else:
        print("\n❌ Install required libraries to enable file processing")