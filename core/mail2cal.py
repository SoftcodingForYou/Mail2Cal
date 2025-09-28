#!/usr/bin/env python3
"""
Mail2Cal - AI-powered email to calendar converter for school communications
"""

# =============================================================================
# SECURE CONFIGURATION - Credentials loaded from Google Sheets
# =============================================================================

from auth.secure_credentials import get_secure_credential

# Load credentials securely from Google Sheets
try:
    ANTHROPIC_API_KEY = get_secure_credential('ANTHROPIC_API_KEY')
    GOOGLE_CALENDAR_ID_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')  # Calendar 1 (Class A)
    GOOGLE_CALENDAR_ID_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')  # Calendar 2 (Class B)
    GMAIL_ADDRESS = get_secure_credential('GMAIL_ADDRESS')
    EMAIL_SENDER_FILTER = get_secure_credential('EMAIL_SENDER_FILTER')
    TEACHER_1_EMAIL = get_secure_credential('TEACHER_1_EMAIL')  # Teacher 1 → Calendar 1
    TEACHER_2_EMAIL = get_secure_credential('TEACHER_2_EMAIL')  # Teacher 2 → Calendar 2
    TEACHER_3_EMAIL = get_secure_credential('TEACHER_3_EMAIL')  # Teacher 3 (Afterschool) → Both Calendars
    TEACHER_4_EMAIL = get_secure_credential('TEACHER_4_EMAIL')  # Teacher 4 (Afterschool) → Both Calendars
    AI_MODEL = get_secure_credential('AI_MODEL')
    DEFAULT_MONTHS_BACK = float(get_secure_credential('DEFAULT_MONTHS_BACK'))
    
    print("[+] Credentials loaded securely from Google Sheets")
    
except Exception as e:
    print(f"[!] Error loading secure credentials: {e}")
    print("[!] Please ensure your Google Apps Script is deployed and accessible")
    raise SystemExit("Cannot continue without proper credentials")

# =============================================================================
# DO NOT MODIFY BELOW THIS LINE UNLESS YOU KNOW WHAT YOU'RE DOING
# =============================================================================

import os
import yaml
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import base64
import re
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .ai_parser import AIEmailParser
from .event_tracker import EventTracker
from .smart_event_merger import SmartEventMerger
from processors.pdf_attachment_processor import PDFAttachmentProcessor
from .global_event_cache import GlobalEventCache

# Gmail and Calendar API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar'
]

class Mail2Cal:
    def __init__(self):
        """Initialize Mail2Cal with configuration from script variables"""
        # Validate configuration
        if ANTHROPIC_API_KEY == "your-anthropic-api-key-here":
            raise ValueError("Please set ANTHROPIC_API_KEY at the top of this script")
        if GOOGLE_CALENDAR_ID_1 == "your-calendar-id-here" or GOOGLE_CALENDAR_ID_2 == "your-calendar-id-here":
            raise ValueError("Please set both GOOGLE_CALENDAR_ID_1 and GOOGLE_CALENDAR_ID_2 at the top of this script")
        
        # Set environment variable for AI API
        os.environ['ANTHROPIC_API_KEY'] = ANTHROPIC_API_KEY
        
        # Build configuration from script variables
        self.config = {
            'gmail': {
                'user_id': GMAIL_ADDRESS,
                'sender_filter': EMAIL_SENDER_FILTER
            },
            'calendars': {
                'calendar_id_1': GOOGLE_CALENDAR_ID_1,  # Calendar 1
                'calendar_id_2': GOOGLE_CALENDAR_ID_2,  # Calendar 2
                'teacher_1_email': TEACHER_1_EMAIL,     # Teacher 1 → Calendar 1
                'teacher_2_email': TEACHER_2_EMAIL,     # Teacher 2 → Calendar 2
                'teacher_3_email': TEACHER_3_EMAIL,     # Teacher 3 (Afterschool) → Both
                'teacher_4_email': TEACHER_4_EMAIL      # Teacher 4 (Afterschool) → Both
            },
            'date_range': {
                'default_months_back': DEFAULT_MONTHS_BACK
            },
            'ai_service': {
                'provider': 'anthropic',
                'api_key_env_var': 'ANTHROPIC_API_KEY',
                'model': AI_MODEL
            },
            'event_tracking': {
                'storage_file': 'event_mappings.json'
            },
            'pdf_processing': {
                'enabled': True,  # Enable PDF attachment processing
                'max_file_size_mb': 25,  # Maximum PDF file size to process
                'cache_extractions': True  # Cache PDF text extractions
            }
        }
        
        self.gmail_service = None
        self.calendar_service = None
        self.ai_parser = AIEmailParser(self.config)
        self.event_tracker = EventTracker(self.config['event_tracking']['storage_file'])
        self.smart_merger = SmartEventMerger(self.config['ai_service'], self.event_tracker)
        self.global_cache = GlobalEventCache()
        self.pdf_processor = None  # Will be initialized after Gmail service is ready
        
    def authenticate(self):
        """Authenticate with Google APIs"""
        creds = None
        
        # Load existing credentials
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        # Build services
        self.gmail_service = build('gmail', 'v1', credentials=creds)
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        
        # Refresh global cache with current calendar state
        calendar_ids = [
            self.config['calendars']['calendar_id_1'],
            self.config['calendars']['calendar_id_2']
        ]
        self.global_cache.refresh_from_calendars(self.calendar_service, calendar_ids)
        
        # Initialize PDF processor if enabled
        if self.config['pdf_processing']['enabled']:
            try:
                self.pdf_processor = PDFAttachmentProcessor(self.gmail_service, self.config)
                print("[+] PDF attachment processing enabled")
            except Exception as e:
                print(f"[!] Warning: PDF processing disabled due to error: {e}")
                self.pdf_processor = None
    
    def get_emails_from_date_range(self, days_back: int = None) -> List[Dict]:
        """Fetch emails from school within specified date range"""
        if days_back is None:
            days_back = int(self.config['date_range']['default_months_back'] * 30)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Format dates for Gmail API
        after_date = start_date.strftime('%Y/%m/%d')
        before_date = end_date.strftime('%Y/%m/%d')
        
        # Build search query
        query = f"{self.config['gmail']['sender_filter']} after:{after_date} before:{before_date}"
        
        try:
            # Search for emails
            result = self.gmail_service.users().messages().list(
                userId=self.config['gmail']['user_id'],
                q=query
            ).execute()
            
            messages = result.get('messages', [])
            emails = []
            
            for message in messages:
                # Get full message details
                msg = self.gmail_service.users().messages().get(
                    userId=self.config['gmail']['user_id'],
                    id=message['id']
                ).execute()
                
                emails.append(self._parse_email(msg))
            
            return emails
            
        except HttpError as error:
            print(f'Error fetching emails: {error}')
            return []
    
    def _parse_email(self, message: Dict) -> Dict:
        """Parse Gmail message into structured data"""
        headers = message['payload'].get('headers', [])
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Extract body
        body = self._extract_email_body(message['payload'])
        
        # Check for and process PDF attachments if enabled
        has_attachments = False
        if self.pdf_processor and self.config['pdf_processing']['enabled']:
            try:
                if self.pdf_processor.has_pdf_attachments(message):
                    has_attachments = True
                    attachment_summary = self.pdf_processor.get_attachment_summary(message)
                    # Clean the summary for safe printing
                    safe_summary = attachment_summary.encode('ascii', errors='replace').decode('ascii')
                    print(f"[PDF] {safe_summary}")
                    
                    # Create email dict first for processing
                    email_data = {
                        'id': message['id'],
                        'subject': subject,
                        'sender': sender,
                        'date': date_str,
                        'body': body,
                        'snippet': message.get('snippet', '')
                    }
                    
                    # Enhance body with PDF content
                    enhanced_body = self.pdf_processor.process_email_with_attachments(email_data, message)
                    body = enhanced_body
                    
            except Exception as e:
                print(f"[!] Error processing PDF attachments for email {message['id']}: {e}")
        
        return {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date_str,
            'body': body,
            'snippet': message.get('snippet', ''),
            'has_pdf_attachments': has_attachments
        }
    
    def _extract_email_body(self, payload: Dict) -> str:
        """Extract email body from payload with improved parsing"""
        body_parts = []
        
        def extract_from_part(part):
            """Recursively extract text from email parts"""
            if 'parts' in part:
                # Multipart message, recurse into parts
                for subpart in part['parts']:
                    extract_from_part(subpart)
            else:
                # Single part, extract content
                mime_type = part.get('mimeType', '')
                body_data = part.get('body', {})
                
                if 'data' in body_data and body_data['data']:
                    try:
                        # Decode base64 content
                        decoded_data = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='ignore')
                        
                        if mime_type == 'text/plain':
                            if decoded_data.strip():
                                body_parts.append(decoded_data.strip())
                        elif mime_type == 'text/html':
                            # Parse HTML and extract text
                            soup = BeautifulSoup(decoded_data, 'html.parser')
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
                        print(f"[!] Error decoding part {mime_type}: {e}")
        
        # Start extraction
        extract_from_part(payload)
        
        # Combine all parts
        body = '\n\n'.join(body_parts)
        
        # If still empty, try alternative approaches
        if not body.strip():
            # Try to get snippet from message
            snippet = payload.get('snippet', '')
            if snippet:
                body = f"[SNIPPET] {snippet}"
        
        return body.strip()
    
    def parse_events_from_email(self, email: Dict) -> List[Dict]:
        """Extract event information from email content using AI"""
        sender_type = self.get_sender_type(email)
        return self.ai_parser.parse_email_for_events(email, sender_type)
    
    def get_sender_type(self, email: Dict) -> str:
        """Determine sender type for AI parsing context"""
        sender = email.get('sender', '').lower()
        
        if self.config['calendars']['teacher_1_email'] in sender:
            return 'teacher_1'  # Teacher 1 → Calendar 1 (8:00 AM default)
        elif self.config['calendars']['teacher_2_email'] in sender:
            return 'teacher_2'  # Teacher 2 → Calendar 2 (8:00 AM default)
        elif (self.config['calendars']['teacher_3_email'] in sender or 
              self.config['calendars']['teacher_4_email'] in sender):
            return 'afterschool'  # Afterschool teachers 3&4 (1:00 PM default)
        else:
            return 'other'  # Other school senders (all-day default)
    
    def get_target_calendars(self, email: Dict) -> List[str]:
        """Determine which calendar(s) to use based on email sender"""
        sender = email.get('sender', '').lower()
        
        # ENHANCED DEBUG LOGGING
        print(f"[DEBUG] === ROUTING DECISION DEBUG ===")
        print(f"[DEBUG] Raw sender: {email.get('sender', '')}")
        print(f"[DEBUG] Sender (lowercase): {sender}")
        
        # Check for placeholder/unconfigured teacher emails
        teacher_emails = [
            self.config['calendars']['teacher_1_email'],
            self.config['calendars']['teacher_2_email'],
            self.config['calendars']['teacher_3_email'],
            self.config['calendars']['teacher_4_email']
        ]
        
        # ENHANCED DEBUG: Show all configured teacher emails
        print(f"[DEBUG] Configured teacher emails:")
        print(f"[DEBUG]   Teacher 1: {self.config['calendars']['teacher_1_email']}")
        print(f"[DEBUG]   Teacher 2: {self.config['calendars']['teacher_2_email']}")
        print(f"[DEBUG]   Teacher 3: {self.config['calendars']['teacher_3_email']}")
        print(f"[DEBUG]   Teacher 4: {self.config['calendars']['teacher_4_email']}")
        
        # Warn if teacher emails appear to be unconfigured
        unconfigured = [email for email in teacher_emails if 'example.com' in email or 'teacher' in email.lower()]
        if unconfigured:
            print(f"[!] WARNING: Some teacher emails appear unconfigured: {unconfigured}")
            print(f"[!] This may cause incorrect calendar routing. See SETUP_GUIDE.md for configuration.")
        
        # ENHANCED DEBUG: Test each matching condition explicitly
        teacher_1_email_lower = self.config['calendars']['teacher_1_email'].lower()
        teacher_2_email_lower = self.config['calendars']['teacher_2_email'].lower()
        teacher_3_email_lower = self.config['calendars']['teacher_3_email'].lower()
        teacher_4_email_lower = self.config['calendars']['teacher_4_email'].lower()
        
        print(f"[DEBUG] Testing matches:")
        print(f"[DEBUG]   '{teacher_1_email_lower}' in '{sender}': {teacher_1_email_lower in sender}")
        print(f"[DEBUG]   '{teacher_2_email_lower}' in '{sender}': {teacher_2_email_lower in sender}")
        print(f"[DEBUG]   '{teacher_3_email_lower}' in '{sender}': {teacher_3_email_lower in sender}")
        print(f"[DEBUG]   '{teacher_4_email_lower}' in '{sender}': {teacher_4_email_lower in sender}")
        
        if teacher_1_email_lower in sender:
            # Teacher 1 → Calendar 1 only
            print(f"[DEBUG] MATCH: Teacher 1 -> Calendar 1 only")
            return [self.config['calendars']['calendar_id_1']]
        elif teacher_2_email_lower in sender:
            # Teacher 2 → Calendar 2 only
            print(f"[DEBUG] MATCH: Teacher 2 -> Calendar 2 only")
            return [self.config['calendars']['calendar_id_2']]
        elif (teacher_3_email_lower in sender or teacher_4_email_lower in sender):
            # Afterschool teachers (3 & 4) → Both calendars
            matched_teacher = "Teacher 3" if teacher_3_email_lower in sender else "Teacher 4"
            print(f"[DEBUG] MATCH: {matched_teacher} -> Both calendars (afterschool)")
            return [
                self.config['calendars']['calendar_id_1'],
                self.config['calendars']['calendar_id_2']
            ]
        else:
            # All other school senders → Both calendars
            # Extract just email for cleaner logging
            email_part = sender.split('<')[-1].replace('>', '') if '<' in sender else sender
            print(f"[DEBUG] NO MATCH: Default routing -> Both calendars")
            print(f"[!] No teacher match for {email_part} -> routing to both calendars")
            print(f"[!] If this teacher should only use one calendar, configure their email in secure credentials")
            return [
                self.config['calendars']['calendar_id_1'],
                self.config['calendars']['calendar_id_2']
            ]
    
    def _extract_dates_from_text(self, text: str) -> List[datetime]:
        """Extract dates from text (basic implementation)"""
        dates = []
        
        # Spanish date patterns
        date_patterns = [
            r'(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{1,2})-(\d{1,2})-(\d{4})'
        ]
        
        spanish_months = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                try:
                    if 'de' in pattern:  # Spanish format
                        day = int(match.group(1))
                        month = spanish_months[match.group(2)]
                        year = datetime.now().year  # Assume current year
                        dates.append(datetime(year, month, day))
                    else:  # Numeric format
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                        dates.append(datetime(year, month, day))
                except (ValueError, KeyError):
                    continue
        
        return dates
    
    def check_for_duplicate_event(self, event_data: Dict, calendar_id: str) -> Optional[str]:
        """Check if a similar event already exists in the calendar"""
        try:
            # Get the date range to search (same day plus/minus 1 day for safety)
            if event_data.get('start_time'):
                search_date = event_data['start_time'].date()
            else:
                search_date = datetime.now().date()
            
            time_min = (search_date - timedelta(days=1)).isoformat() + 'T00:00:00Z'
            time_max = (search_date + timedelta(days=1)).isoformat() + 'T23:59:59Z'
            
            # Search for events in the target calendar
            result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            existing_events = result.get('items', [])
            
            # Check each existing event for similarity
            new_title = event_data['summary'].lower().strip()
            new_date = search_date.isoformat()
            
            for existing_event in existing_events:
                existing_title = existing_event.get('summary', '').lower().strip()
                
                # Get existing event date
                existing_start = existing_event.get('start', {})
                if 'date' in existing_start:
                    existing_date = existing_start['date']
                elif 'dateTime' in existing_start:
                    existing_date = existing_start['dateTime'][:10]  # Extract date part
                else:
                    continue
                
                # Check for exact title match on same date
                if new_title == existing_title and new_date == existing_date:
                    return existing_event['id']
                
                # Check for common school event patterns
                school_keywords = ['feriado', 'dia de la familia', 'actividad laboratorio', 
                                 'celebracion de', 'semana de', 'vacacion', 'reunion']
                
                for keyword in school_keywords:
                    if (keyword in new_title and keyword in existing_title and 
                        new_date == existing_date):
                        return existing_event['id']
                
                # Check for high similarity (80%+) on same date
                similarity = self.calculate_title_similarity(new_title, existing_title)
                if similarity > 0.8 and new_date == existing_date:
                    return existing_event['id']
                    
        except Exception as e:
            print(f"[!] Warning: Could not check for duplicate events: {e}")
            
        return None
    
    def calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two event titles"""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _extract_event_date(self, event_data: Dict) -> str:
        """Extract date string from event data for caching"""
        if event_data.get('start_time'):
            if hasattr(event_data['start_time'], 'date'):
                return event_data['start_time'].date().isoformat()
            else:
                return str(event_data['start_time'])[:10]
        else:
            return datetime.now().date().isoformat()
    
    def create_calendar_event(self, event_data: Dict, calendar_id: str) -> Optional[str]:
        """Create event in Google Calendar and return event ID"""
        try:
            # Extract event date for global cache
            event_date = self._extract_event_date(event_data)
            
            # Check global cache for duplicates first (most efficient)
            if self.global_cache.is_duplicate(event_data['summary'], event_date, calendar_id):
                print(f"[!] Skipping duplicate event (global cache): {event_data['summary']}")
                return None
            
            # Fallback: Check calendar directly for duplicates
            existing_event_id = self.check_for_duplicate_event(event_data, calendar_id)
            if existing_event_id:
                print(f"[!] Skipping duplicate event (calendar check): {event_data['summary']} (exists as {existing_event_id})")
                return existing_event_id
            
            # Prepare event for Calendar API
            event = {
                'summary': event_data['summary'],
                'description': event_data['description'],
            }
            
            # Add location if available
            if event_data.get('location'):
                event['location'] = event_data['location']
            
            # Handle date/time - PREVENT EXTENDED MULTI-DAY EVENTS
            if event_data.get('all_day'):
                # All-day event - ALWAYS single day only
                if event_data['start_time']:
                    start_date = event_data['start_time'].date()
                    event['start'] = {'date': start_date.isoformat()}
                    event['end'] = {'date': (start_date + timedelta(days=1)).isoformat()}
                else:
                    event['start'] = {'date': datetime.now().date().isoformat()}
                    event['end'] = {'date': (datetime.now().date() + timedelta(days=1)).isoformat()}
                print(f"[*] Creating single-day all-day event to prevent overlaps")
            else:
                # Timed event - LIMIT DURATION TO PREVENT OVERLAPS
                if event_data['start_time']:
                    start_dt = event_data['start_time']
                    end_dt = event_data['end_time'] or start_dt + timedelta(hours=1)
                    
                    # Prevent events longer than 8 hours (likely misinterpretation)
                    duration = end_dt - start_dt
                    if duration.total_seconds() > 8 * 3600:  # 8 hours
                        end_dt = start_dt + timedelta(hours=2)  # Default to 2 hours
                        print(f"[!] WARNING: Event duration capped at 2 hours to prevent overlaps")
                    
                    event['start'] = {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
                    event['end'] = {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
                else:
                    # Default to all-day if no time specified
                    event['start'] = {'date': datetime.now().date().isoformat()}
                    event['end'] = {'date': (datetime.now().date() + timedelta(days=1)).isoformat()}
            
            # Handle recurring events - CONSERVATIVE APPROACH
            if event_data.get('recurring'):
                # Limit recurring events to maximum 3 months to avoid overlaps
                max_end_date = datetime.now() + timedelta(days=90)  # 3 months max
                until_date = max_end_date.strftime('%Y%m%dT235959Z')
                event['recurrence'] = [f'RRULE:FREQ=WEEKLY;COUNT=12']  # Max 12 occurrences
                print(f"[+] Creating LIMITED recurring event (max 12 weeks)")
                print(f"[!] WARNING: Recurring event limited to prevent overlaps")
            
            # Add event metadata as extended properties
            event['extendedProperties'] = {
                'private': {
                    'mail2cal_source_email_id': event_data.get('source_email_id', ''),
                    'mail2cal_event_type': event_data.get('event_type', 'general'),
                    'mail2cal_priority': event_data.get('priority', 'medium'),
                    'mail2cal_recurring': str(event_data.get('recurring', False)),
                    'mail2cal_created_at': datetime.now().isoformat()
                }
            }
            
            result = self.calendar_service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            event_id = result.get('id')
            
            # Add to global cache
            self.global_cache.add_event(
                title=event_data['summary'],
                date=event_date,
                calendar_id=calendar_id,
                event_id=event_id
            )
            
            print(f"[+] Event created: {event_data['summary'][:50]}... (ID: {event_id})")
            return event_id
            
        except HttpError as error:
            print(f'[-] Error creating calendar event: {error}')
            return None
    
    def update_calendar_event(self, event_id: str, event_data: Dict, calendar_id: str) -> bool:
        """Update an existing calendar event"""
        try:
            
            # Get existing event
            existing_event = self.calendar_service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update with new data
            existing_event['summary'] = event_data['summary']
            existing_event['description'] = event_data['description']
            
            if event_data.get('location'):
                existing_event['location'] = event_data['location']
            
            # Update date/time
            if event_data.get('all_day'):
                if event_data['start_time']:
                    start_date = event_data['start_time'].date()
                    existing_event['start'] = {'date': start_date.isoformat()}
                    existing_event['end'] = {'date': (start_date + timedelta(days=1)).isoformat()}
            else:
                if event_data['start_time']:
                    start_dt = event_data['start_time']
                    end_dt = event_data['end_time'] or start_dt + timedelta(hours=1)
                    
                    existing_event['start'] = {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
                    existing_event['end'] = {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'America/Santiago',
                    }
            
            # Update metadata
            if 'extendedProperties' not in existing_event:
                existing_event['extendedProperties'] = {'private': {}}
            
            existing_event['extendedProperties']['private'].update({
                'mail2cal_updated_at': datetime.now().isoformat(),
                'mail2cal_event_type': event_data.get('event_type', 'general'),
                'mail2cal_priority': event_data.get('priority', 'medium')
            })
            
            result = self.calendar_service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event
            ).execute()
            
            print(f"[+] Event updated: {event_data['summary'][:50]}...")
            return True
            
        except HttpError as error:
            print(f'[-] Error updating calendar event: {error}')
            return False
    
    def delete_calendar_event(self, event_id: str, calendar_id: str) -> bool:
        """Delete a calendar event"""
        try:
            
            self.calendar_service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            print(f"[+] Event deleted: {event_id}")
            return True
            
        except HttpError as error:
            # 404 (Not Found) and 410 (Resource has been deleted) are considered successful
            # since the event is already gone from the calendar
            if error.resp.status in [404, 410]:
                print(f"[+] Event already deleted: {event_id} (status: {error.resp.status})")
                return True
            else:
                print(f'[-] Error deleting calendar event: {error}')
                return False
    
    def run(self, days_back: int = None):
        """Main execution method with intelligent processing"""
        print("[*] Starting AI-powered Mail2Cal...")
        
        # Authenticate
        print("[*] Authenticating with Google APIs...")
        self.authenticate()
        
        # Fetch emails
        print("[*] Fetching emails from school...")
        emails = self.get_emails_from_date_range(days_back)
        print(f"[*] Found {len(emails)} emails")
        
        if not emails:
            print("[!] No emails found in the specified date range")
            return
        
        # Track statistics
        stats = {
            'processed': 0,
            'new_events': 0,
            'updated_events': 0,
            'deleted_events': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Get existing email IDs for cleanup
        existing_email_ids = {email['id'] for email in emails}
        
        # Process each email
        for i, email in enumerate(emails, 1):
            print(f"\n[{i}/{len(emails)}] Processing: {email['subject'][:60]}...")

            # Skip emails with specific subjects that should be ignored
            if email.get('subject', '').strip() == "Alerta de Inasistencia a Clases":
                print(f"[>] Skipping ignored email subject: {email['subject']}")
                stats['skipped'] += 1
                continue

            try:
                # Check if email needs processing
                email_processed = self.event_tracker.is_email_processed(email)
                email_changed = self.event_tracker.has_email_changed(email)
                
                if email_processed and not email_changed:
                    # Even if email hasn't changed, check if its events still exist
                    calendar_ids = [
                        self.config['calendars']['calendar_id_1'],
                        self.config['calendars']['calendar_id_2']
                    ]
                    events_exist = self.event_tracker.events_still_exist(email, self.calendar_service, calendar_ids)
                    
                    if events_exist:
                        print(f"[>] Skipping unchanged email (events still exist)")
                        stats['skipped'] += 1
                        continue
                    else:
                        print(f"[!] Email already processed but events were deleted - reprocessing to recreate events")
                        print(f"[!] Subject: {email['subject']}")
                        # Continue processing to recreate the missing events
                
                # Parse events using AI
                print("[AI] Analyzing email content with Claude...")
                events = self.parse_events_from_email(email)
                
                if not events:
                    print("[!] No events detected in this email")
                    stats['processed'] += 1
                    continue
                
                print(f"[+] Found {len(events)} event(s)")
                
                # Add source email info to events for smart merging
                for event in events:
                    event['source_email_subject'] = email.get('subject', '')
                    event['source_email_sender'] = email.get('sender', '')
                    event['source_email_date'] = email.get('date', '')
                
                # UNIFIED: Use AI-powered smart duplicate detection with 2-week window
                print("[AI] Checking for potential duplicate events (2-week window from today)...")
                potential_duplicates = self.smart_merger.find_potential_duplicates(events, email)

                # Handle existing vs new events with unified duplicate detection
                calendar_event_ids = []

                # Determine target calendars based on sender
                target_calendars = self.get_target_calendars(email)
                sender_name = email.get('sender', '').split('<')[0].strip()

                print(f"[*] Target calendars: {len(target_calendars)} ({'Calendar 1 only' if len(target_calendars) == 1 and target_calendars[0] == self.config['calendars']['calendar_id_1'] else 'Calendar 2 only' if len(target_calendars) == 1 else 'Both calendars'})")

                # Process events with unified duplicate detection
                processed_events = set()

                # First pass: Handle AI-detected duplicates (high confidence)
                for duplicate_info in potential_duplicates:
                    if duplicate_info['action'] == 'merge' or self.smart_merger.should_auto_merge(duplicate_info):
                        print(f"[MERGE] Auto-merging duplicate event: {duplicate_info['new_event'].get('summary', 'Untitled')[:50]}...")
                        merged_event_id = self.smart_merger.merge_events(duplicate_info, self.calendar_service, self.config)
                        if merged_event_id:
                            calendar_event_ids.append(merged_event_id)
                            stats['updated_events'] += 1
                            # Mark this event as processed
                            new_event_signature = self.event_tracker.generate_event_signature(duplicate_info['new_event'])
                            processed_events.add(new_event_signature)
                        else:
                            stats['errors'] += 1
                    elif duplicate_info['similarity_score'] > 0.7:
                        print(f"[REVIEW] Potential duplicate found (similarity: {duplicate_info['similarity_score']:.2f}): {duplicate_info['new_event'].get('summary', 'Untitled')[:50]}...")
                        print(f"         Creating as separate event - manual review recommended")
                        # Don't mark as processed, let it be created as new event

                # Fallback: Use legacy signature-based matching for events not handled by AI
                similar_events = self.event_tracker.find_similar_events(events)
                
                # Second pass: Process remaining events (not handled by AI merger)
                for event in events:
                    event_signature = self.event_tracker.generate_event_signature(event)

                    # Skip events that were already processed by smart merger
                    if event_signature in processed_events:
                        print(f"[SKIP] Event already processed by AI merger: {event.get('summary', 'Untitled')[:50]}...")
                        continue

                    # Process event for each target calendar
                    for calendar_id in target_calendars:
                        calendar_name = "Calendar 1 (Class A)" if calendar_id == self.config['calendars']['calendar_id_1'] else "Calendar 2 (Class B)"

                        # Check legacy signature-based duplicates (fallback only)
                        if event_signature in similar_events:
                            # Update existing similar event (legacy method)
                            existing_event_id = similar_events[event_signature]
                            print(f"[LEGACY] Updating existing event in {calendar_name}: {event.get('summary', 'Untitled')[:50]}...")
                            if self.update_calendar_event(existing_event_id, event, calendar_id):
                                calendar_event_ids.append(existing_event_id)
                                stats['updated_events'] += 1

                                # Update the tracking for this event
                                self.event_tracker.update_event_mapping(email, existing_event_id, existing_event_id, event)
                            else:
                                stats['errors'] += 1
                        else:
                            # Create new event (no duplicates found by any method)
                            print(f"[NEW] Creating new event in {calendar_name}: {event.get('summary', 'Untitled')[:50]}...")
                            event_id = self.create_calendar_event(event, calendar_id)
                            if event_id:
                                calendar_event_ids.append(event_id)
                                stats['new_events'] += 1
                            else:
                                stats['errors'] += 1
                
                # Track the email processing
                self.event_tracker.track_email_processing(email, events, calendar_event_ids)
                stats['processed'] += 1
                
            except Exception as e:
                print(f"[-] Error processing email: {e}")
                stats['errors'] += 1
        
        # Cleanup orphaned mappings
        print("\n[*] Cleaning up orphaned mappings...")
        orphaned_events = self.event_tracker.cleanup_orphaned_mappings(existing_email_ids)
        for event_id in orphaned_events:
            # Try to delete from both calendars (we don't know which one it's in)
            deleted = False
            for calendar_id in [self.config['calendars']['calendar_id_1'], self.config['calendars']['calendar_id_2']]:
                try:
                    if self.delete_calendar_event(event_id, calendar_id):
                        deleted = True
                        break
                except:
                    continue  # Event might not exist in this calendar
            if deleted:
                stats['deleted_events'] += 1
        
        # Display final statistics
        print(f"\n[*] PROCESSING COMPLETE")
        print(f"{'='*50}")
        print(f"Emails processed: {stats['processed']}")
        print(f"New events created: {stats['new_events']}")
        print(f"Events updated: {stats['updated_events']}")
        print(f"Events deleted: {stats['deleted_events']}")
        print(f"Emails skipped: {stats['skipped']}")
        print(f"Errors: {stats['errors']}")
        
        # Show tracker statistics
        tracker_stats = self.event_tracker.get_processing_statistics()
        print(f"\n[*] OVERALL STATISTICS")
        print(f"{'='*50}")
        print(f"Total emails in database: {tracker_stats['total_emails_processed']}")
        print(f"Total events in database: {tracker_stats['total_events_created']}")
        print(f"Emails processed this month: {tracker_stats['emails_this_month']}")
        print(f"Average events per email: {tracker_stats['average_events_per_email']:.1f}")
        
        print(f"\n[+] Mail2Cal processing completed successfully!")

def main():
    """Main entry point"""
    mail2cal = Mail2Cal()
    mail2cal.run()

if __name__ == "__main__":
    main()