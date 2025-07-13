#!/usr/bin/env python3
"""
File-based Event Processor for Mail2Cal
Processes local PDF and image files to extract calendar events
Follows the same creation/updating/deletion logic as email processing
"""

import os
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import mimetypes

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
            
            # Process files in this calendar directory
            for file_path in calendar_dir.iterdir():
                if file_path.is_file() and self._is_supported_file(file_path):
                    try:
                        file_result = self._process_single_file(file_path, calendar_name)
                        
                        results["files_processed"] += 1
                        if file_result["action"] == "created":
                            results["events_created"] += file_result["events_count"]
                        elif file_result["action"] == "updated":
                            results["events_updated"] += file_result["events_count"]
                        elif file_result["action"] == "skipped":
                            results["files_skipped"] += 1
                            
                    except Exception as e:
                        error_msg = f"Error processing {file_path.name}: {e}"
                        print(f"[!] {error_msg}")
                        results["errors"].append(error_msg)
        
        return results
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported"""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        supported_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'image/bmp'
        ]
        
        return (mime_type in supported_types or 
                file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'])
    
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
        
        # Create events in calendar(s)
        created_events = []
        for event in events:
            for calendar_id in target_calendars:
                try:
                    event_id = self.mail2cal.create_calendar_event(event, calendar_id)
                    if event_id:
                        created_events.append({
                            'calendar_event_id': event_id,
                            'calendar_id': calendar_id,
                            'summary': event.get('summary', ''),
                            'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                            'created_at': datetime.now().isoformat()
                        })
                        print(f"[+] Created event: {event.get('summary', '')[:50]}...")
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
        
        return {"action": "created", "events_count": len(created_events)}
    
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