#!/usr/bin/env python3
"""
Cleanup Misrouted Teacher Events
Deletes events from calendars where specific teachers should not have events
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from core.config import get_calendar_and_teacher_config

class TeacherEventCleanup:
    def __init__(self):
        """Initialize the cleanup tool"""
        self.calendar_service = None
        self.config = self.load_configuration()

    def load_configuration(self):
        """Load configuration from secure credentials"""
        try:
            config = get_calendar_and_teacher_config()
            print("[+] Configuration loaded successfully")
            return config
        except Exception as e:
            print(f"[!] Error loading configuration: {e}")
            raise
    
    def authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing credentials
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            print("[!] Authentication required. Please run the main system first to authenticate.")
            raise SystemExit("Cannot authenticate without valid credentials")
        
        # Build service
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        print("[+] Authenticated with Google Calendar API")
    
    def get_events_from_calendar(self, calendar_id, days_back=30):
        """Get all events from a calendar - focus on future events"""
        try:
            # Calculate date range - look back a bit but focus on future
            start_date = datetime.now() - timedelta(days=days_back)
            # Look far into the future to catch all scheduled events (2 years ahead)
            end_date = datetime.now() + timedelta(days=730)
            
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            print(f"[*] Fetching events from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Get events
            result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=1000,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = result.get('items', [])
            print(f"[+] Found {len(events)} events")
            return events
            
        except Exception as e:
            print(f"[!] Error fetching events: {e}")
            return []
    
    def identify_teacher_from_event(self, event):
        """Try to identify which teacher created an event based on metadata"""
        # Check extended properties for source email
        extended_props = event.get('extendedProperties', {}).get('private', {})
        source_email_id = extended_props.get('mail2cal_source_email_id', '')
        
        # Check event description for email patterns
        description = event.get('description', '')
        
        # Check for teacher email patterns
        teacher_emails = {
            'teacher_1': self.config['teacher_1_email'],
            'teacher_2': self.config['teacher_2_email'],
            'teacher_3': self.config['teacher_3_email'],
            'teacher_4': self.config['teacher_4_email']
        }
        
        # Try to match based on description or metadata
        for teacher_key, teacher_email in teacher_emails.items():
            teacher_domain = teacher_email.split('@')[0] if '@' in teacher_email else teacher_email
            
            if (teacher_email.lower() in description.lower() or 
                teacher_domain.lower() in description.lower() or
                teacher_email.lower() in source_email_id.lower()):
                return teacher_key
        
        return None
    
    def should_event_be_in_calendar(self, teacher_key, calendar_id):
        """Check if a teacher's events should be in a specific calendar"""
        if teacher_key == 'teacher_1':
            # Teacher 1 should only be in Calendar 1
            return calendar_id == self.config['calendar_id_1']
        elif teacher_key == 'teacher_2':
            # Teacher 2 should only be in Calendar 2
            return calendar_id == self.config['calendar_id_2']
        elif teacher_key in ['teacher_3', 'teacher_4']:
            # Teachers 3 & 4 (afterschool) should be in both calendars
            return True
        else:
            # Unknown teacher or other senders - can be in both
            return True
    
    def analyze_misrouted_events(self, days_back=30):
        """Analyze events to find misrouted teacher events"""
        print("\n" + "=" * 60)
        print("ANALYZING MISROUTED TEACHER EVENTS")
        print("=" * 60)
        
        misrouted_events = []
        
        # Check both calendars
        for calendar_name, calendar_id in [("Calendar 1", self.config['calendar_id_1']), 
                                          ("Calendar 2", self.config['calendar_id_2'])]:
            print(f"\n[*] Checking {calendar_name}...")
            events = self.get_events_from_calendar(calendar_id, days_back)
            
            for event in events:
                teacher_key = self.identify_teacher_from_event(event)
                
                if teacher_key:
                    should_be_here = self.should_event_be_in_calendar(teacher_key, calendar_id)
                    
                    if not should_be_here:
                        misrouted_events.append({
                            'event': event,
                            'calendar_id': calendar_id,
                            'calendar_name': calendar_name,
                            'teacher_key': teacher_key,
                            'teacher_email': self.config.get(f'{teacher_key}_email', 'Unknown')
                        })
                        
                        print(f"[!] MISROUTED: {event.get('summary', 'Untitled')[:50]}...")
                        print(f"    Teacher: {teacher_key} ({self.config.get(f'{teacher_key}_email', 'Unknown')})")
                        print(f"    In: {calendar_name}")
                        print(f"    Should be in: {self.get_correct_calendars_for_teacher(teacher_key)}")
                        print(f"    Event ID: {event['id']}")
                        print()
        
        return misrouted_events
    
    def get_correct_calendars_for_teacher(self, teacher_key):
        """Get the correct calendar(s) for a teacher"""
        if teacher_key == 'teacher_1':
            return "Calendar 1 only"
        elif teacher_key == 'teacher_2':
            return "Calendar 2 only"
        elif teacher_key in ['teacher_3', 'teacher_4']:
            return "Both calendars"
        else:
            return "Both calendars (default)"
    
    def delete_misrouted_events(self, misrouted_events, dry_run=True):
        """Delete misrouted events (with dry-run option)"""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN - ' if dry_run else ''}DELETING MISROUTED EVENTS")
        print("=" * 60)
        
        if not misrouted_events:
            print("[+] No misrouted events found!")
            return
        
        print(f"[*] Found {len(misrouted_events)} misrouted events")
        
        if dry_run:
            print("[!] DRY RUN MODE - No events will actually be deleted")
        else:
            print("[!] LIVE MODE - Events will be permanently deleted")
        
        print()
        
        deleted_count = 0
        error_count = 0
        
        for item in misrouted_events:
            event = item['event']
            calendar_id = item['calendar_id']
            calendar_name = item['calendar_name']
            teacher_key = item['teacher_key']
            
            event_title = event.get('summary', 'Untitled')
            event_id = event['id']
            
            print(f"[{'DRY RUN' if dry_run else 'DELETE'}] {event_title[:50]}...")
            print(f"  From: {calendar_name}")
            print(f"  Teacher: {teacher_key}")
            print(f"  Event ID: {event_id}")
            
            if not dry_run:
                try:
                    self.calendar_service.events().delete(
                        calendarId=calendar_id,
                        eventId=event_id
                    ).execute()
                    
                    print(f"  Status: DELETED")
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"  Status: ERROR - {e}")
                    error_count += 1
            else:
                print(f"  Status: WOULD DELETE")
            
            print()
        
        print(f"[*] Summary:")
        if dry_run:
            print(f"    Would delete: {len(misrouted_events)} events")
        else:
            print(f"    Successfully deleted: {deleted_count}")
            print(f"    Errors: {error_count}")
    
    def run_cleanup(self, days_back=30, dry_run=True):
        """Run the complete cleanup process"""
        print("TEACHER EVENT CLEANUP TOOL")
        print("=" * 60)
        print("This tool finds and removes events created by teachers in calendars")
        print("where they should not have events based on your configuration.")
        print()
        print("TEACHER ROUTING RULES:")
        print(f"- Teacher 1 ({self.config['teacher_1_email']}) → Calendar 1 only")
        print(f"- Teacher 2 ({self.config['teacher_2_email']}) → Calendar 2 only")
        print(f"- Teacher 3 ({self.config['teacher_3_email']}) → Both calendars")
        print(f"- Teacher 4 ({self.config['teacher_4_email']}) → Both calendars")
        print()
        
        # Authenticate
        self.authenticate()
        
        # Analyze misrouted events
        misrouted_events = self.analyze_misrouted_events(days_back)
        
        # Delete misrouted events
        if misrouted_events:
            self.delete_misrouted_events(misrouted_events, dry_run)
            
            if dry_run:
                print("\n[!] This was a DRY RUN. To actually delete events, run:")
                print("python utils/cleanup_misrouted_teacher_events.py --live")
        else:
            print("\n[+] No misrouted teacher events found!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup misrouted teacher events')
    parser.add_argument('--days-back', type=int, default=30, 
                       help='Number of days back to check (default: 30)')
    parser.add_argument('--live', action='store_true',
                       help='Actually delete events (default is dry-run)')
    
    args = parser.parse_args()
    
    cleanup = TeacherEventCleanup()
    cleanup.run_cleanup(days_back=args.days_back, dry_run=not args.live)

if __name__ == "__main__":
    main()