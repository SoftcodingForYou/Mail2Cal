#!/usr/bin/env python3
"""
EML File Processor for Mail2Cal
Processes local .eml email files the same way as Gmail emails
"""

import os
import email
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
from bs4 import BeautifulSoup


class EMLProcessor:
    """
    Processes local .eml files to extract calendar events
    Treats .eml files exactly like Gmail emails using the same AI parsing
    """
    
    def __init__(self, mail2cal_instance, base_directory: str = "local_resources"):
        self.mail2cal = mail2cal_instance
        self.base_directory = Path(base_directory)
        self.eml_mappings_file = "eml_event_mappings.json"
        self.eml_mappings = self._load_eml_mappings()
        
        # Calendar directory mapping
        self.calendar_mapping = {
            "Calendar_1": self.mail2cal.config['calendars']['calendar_id_1'],
            "Calendar_2": self.mail2cal.config['calendars']['calendar_id_2'],
            "Both": "both_calendars"  # For events that should go to both calendars
        }
        
        print(f"[*] EML processor initialized with base directory: {self.base_directory}")
    
    def _load_eml_mappings(self) -> Dict:
        """Load EML-to-event mappings from storage"""
        try:
            with open(self.eml_mappings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_eml_mappings(self):
        """Save EML-to-event mappings to storage"""
        try:
            with open(self.eml_mappings_file, 'w', encoding='utf-8') as f:
                json.dump(self.eml_mappings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Error saving EML mappings: {e}")
    
    def generate_eml_hash(self, file_path: Path) -> str:
        """Generate hash for EML file content to detect changes"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            print(f"[!] Error generating hash for {file_path}: {e}")
            return ""
    
    def scan_and_process_eml_files(self) -> Dict:
        """
        Scan the local_resources directory for .eml files and process them
        Returns summary of processing results
        """
        print(f"[*] Scanning for .eml files in: {self.base_directory}")
        
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
        
        # Scan each calendar subdirectory for .eml files
        for calendar_dir in self.base_directory.iterdir():
            if not calendar_dir.is_dir():
                continue
                
            calendar_name = calendar_dir.name
            if calendar_name not in self.calendar_mapping:
                print(f"[!] Unknown calendar directory: {calendar_name}")
                results["errors"].append(f"Unknown calendar directory: {calendar_name}")
                continue
            
            print(f"[*] Processing .eml files for {calendar_name}")
            
            # Look for mails subdirectory
            mails_dir = calendar_dir / "mails"
            if mails_dir.exists() and mails_dir.is_dir():
                print(f"[*] Found mails directory: {mails_dir}")
                self._process_eml_directory(mails_dir, calendar_name, results)
            
            # Also check root calendar directory for .eml files
            self._process_eml_directory(calendar_dir, calendar_name, results)
        
        return results
    
    def _process_eml_directory(self, directory: Path, calendar_name: str, results: Dict):
        """Process all .eml files in a specific directory"""
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == '.eml':
                try:
                    print(f"[*] Processing EML: {file_path.name}")
                    file_result = self._process_single_eml(file_path, calendar_name)
                    
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
    
    def _process_single_eml(self, file_path: Path, calendar_name: str) -> Dict:
        """
        Process a single .eml file and extract events
        Returns: {"action": "created|updated|skipped", "events_count": int}
        """
        file_id = str(file_path.relative_to(self.base_directory))
        current_hash = self.generate_eml_hash(file_path)
        
        # Check if file has been processed before
        if file_id in self.eml_mappings:
            stored_hash = self.eml_mappings[file_id]["file_hash"]
            if stored_hash == current_hash:
                print(f"[*] EML unchanged, skipping: {file_path.name}")
                return {"action": "skipped", "events_count": 0}
            else:
                print(f"[*] EML changed, reprocessing: {file_path.name}")
                return self._update_eml_events(file_path, file_id, current_hash, calendar_name)
        else:
            print(f"[*] New EML, processing: {file_path.name}")
            return self._create_eml_events(file_path, file_id, current_hash, calendar_name)
    
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
            body = self._extract_email_body(email_message)
            
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
    
    def _extract_email_body(self, email_message) -> str:
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
        
        # Create events in calendar(s) - same logic as Gmail processing
        created_events = []
        for event in events:
            # Add source email ID for tracking
            event['source_email_id'] = email_data['id']
            
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
                        calendar_name_display = "Calendar 1" if calendar_id == self.mail2cal.config['calendars']['calendar_id_1'] else "Calendar 2"
                        print(f"[+] Created event in {calendar_name_display}: {event.get('summary', '')[:50]}...")
                except Exception as e:
                    print(f"[!] Error creating event: {e}")
        
        # Track the EML mapping
        self.eml_mappings[file_id] = {
            'file_path': str(file_path),
            'file_hash': file_hash,
            'file_name': file_path.name,
            'calendar_name': calendar_name,
            'processed_at': datetime.now().isoformat(),
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'calendar_events': created_events,
            'email_data': {
                'subject': email_data['subject'],
                'sender': email_data['sender'],
                'date': email_data['date'],
                'body_length': len(email_data['body'])
            }
        }
        
        self._save_eml_mappings()
        
        return {"action": "created", "events_count": len(created_events)}
    
    def _update_eml_events(self, file_path: Path, file_id: str, file_hash: str, calendar_name: str) -> Dict:
        """Update events for a changed EML file"""
        
        # Delete existing events
        existing_mapping = self.eml_mappings[file_id]
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
        result = self._create_eml_events(file_path, file_id, file_hash, calendar_name)
        
        print(f"[+] Updated EML events: deleted {deleted_count}, created {result['events_count']}")
        
        return {"action": "updated", "events_count": result["events_count"]}
    
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
    
    def delete_eml_events(self, file_path: str) -> bool:
        """Delete events associated with an EML file (when file is removed)"""
        file_id = file_path
        
        if file_id not in self.eml_mappings:
            print(f"[!] No mapping found for EML file: {file_path}")
            return False
        
        mapping = self.eml_mappings[file_id]
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
        del self.eml_mappings[file_id]
        self._save_eml_mappings()
        
        print(f"[+] Deleted {deleted_count} events for removed EML: {file_path}")
        return True
    
    def get_processing_statistics(self) -> Dict:
        """Get statistics about processed EML files"""
        total_files = len(self.eml_mappings)
        total_events = sum(
            len(mapping.get('calendar_events', []))
            for mapping in self.eml_mappings.values()
        )
        
        # Count by calendar
        calendar_stats = {}
        for mapping in self.eml_mappings.values():
            calendar_name = mapping.get('calendar_name', 'Unknown')
            calendar_stats[calendar_name] = calendar_stats.get(calendar_name, 0) + 1
        
        return {
            'total_eml_files_processed': total_files,
            'total_events_from_eml': total_events,
            'eml_files_by_calendar': calendar_stats,
            'average_events_per_eml': total_events / total_files if total_files > 0 else 0
        }
    
    def list_processed_emls(self) -> List[Dict]:
        """List all processed EML files with their details"""
        files = []
        for file_id, mapping in self.eml_mappings.items():
            email_data = mapping.get('email_data', {})
            files.append({
                'file_id': file_id,
                'file_name': mapping.get('file_name', ''),
                'calendar_name': mapping.get('calendar_name', ''),
                'processed_at': mapping.get('processed_at', ''),
                'events_count': len(mapping.get('calendar_events', [])),
                'subject': email_data.get('subject', ''),
                'sender': email_data.get('sender', ''),
                'date': email_data.get('date', ''),
                'body_length': email_data.get('body_length', 0)
            })
        
        return sorted(files, key=lambda x: x['processed_at'], reverse=True)


if __name__ == "__main__":
    print("EML Processor - processes .eml files like Gmail emails")
    print("Usage: Use via run_mail2cal.py --process-eml-files")