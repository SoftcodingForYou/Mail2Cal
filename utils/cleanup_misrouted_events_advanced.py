#!/usr/bin/env python3
"""
Advanced Cleanup for Misrouted Teacher Events
Uses event tracking data to identify and clean up misrouted events more accurately
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from core.config import get_calendar_and_teacher_config

class AdvancedTeacherEventCleanup:
    def __init__(self):
        """Initialize the advanced cleanup tool"""
        self.calendar_service = None
        self.config = self.load_configuration()
        self.event_mappings = self.load_event_mappings()

    def load_configuration(self):
        """Load configuration from secure credentials"""
        try:
            config = get_calendar_and_teacher_config()
            print("[+] Configuration loaded successfully")
            return config
        except Exception as e:
            print(f"[!] Error loading configuration: {e}")
            raise
    
    def load_event_mappings(self):
        """Load event tracking data"""
        try:
            with open('event_mappings.json', 'r', encoding='utf-8') as f:
                mappings = json.load(f)
            print(f"[+] Loaded {len(mappings)} email mappings")
            return mappings
        except FileNotFoundError:
            print("[!] event_mappings.json not found")
            return {}
        except Exception as e:
            print(f"[!] Error loading event mappings: {e}")
            return {}
    
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
    
    def identify_teacher_from_sender(self, sender):
        """Identify teacher type from email sender"""
        sender_lower = sender.lower()
        
        if self.config['teacher_1_email'].lower() in sender_lower:
            return 'teacher_1', 'Teacher 1 (Calendar 1 only)'
        elif self.config['teacher_2_email'].lower() in sender_lower:
            return 'teacher_2', 'Teacher 2 (Calendar 2 only)'
        elif (self.config['teacher_3_email'].lower() in sender_lower or
              self.config['teacher_4_email'].lower() in sender_lower):
            return 'teacher_3_4', 'Teacher 3/4 (Both calendars)'
        else:
            return 'other', 'Other sender (Both calendars)'

    def should_event_exist_in_calendar(self, teacher_type, calendar_id):
        """Check if teacher's events should exist in specific calendar"""
        if teacher_type == 'teacher_1':
            # Teacher 1 should only be in Calendar 1
            return calendar_id == self.config['calendar_id_1']
        elif teacher_type == 'teacher_2':
            # Teacher 2 should only be in Calendar 2
            return calendar_id == self.config['calendar_id_2']
        elif teacher_type == 'teacher_3_4':
            # Teachers 3/4 should be in both calendars
            return True
        else:
            # Other senders can be in both calendars
            return True
    
    def get_event_from_calendar(self, calendar_id, event_id):
        """Get a specific event from calendar"""
        try:
            event = self.calendar_service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return event
        except Exception as e:
            # Event might not exist in this calendar
            return None
    
    def analyze_misrouted_events(self):
        """Analyze all tracked events to find misrouted ones"""
        print("\n" + "=" * 70)
        print("ANALYZING MISROUTED EVENTS USING TRACKING DATA")
        print("=" * 70)
        print("Checking tracked events against current calendar state...")
        print()
        
        misrouted_events = []
        teacher_stats = {
            'teacher_1': {'total': 0, 'misrouted': 0, 'calendars': {}},
            'teacher_2': {'total': 0, 'misrouted': 0, 'calendars': {}},
            'teacher_3_4': {'total': 0, 'misrouted': 0, 'calendars': {}},
            'other': {'total': 0, 'misrouted': 0, 'calendars': {}}
        }
        
        for email_id, mapping in self.event_mappings.items():
            sender = mapping.get('email_sender', '')
            email_subject = mapping.get('email_subject', '')
            
            # Identify teacher
            teacher_type, teacher_desc = self.identify_teacher_from_sender(sender)
            
            print(f"\n[*] Email: {email_subject[:50]}...")
            print(f"    Sender: {sender}")
            print(f"    Teacher: {teacher_desc}")
            
            # Check each event created by this email
            calendar_events = mapping.get('calendar_events', [])
            print(f"    Events created: {len(calendar_events)}")
            
            teacher_stats[teacher_type]['total'] += len(calendar_events)
            
            for event_info in calendar_events:
                event_id = event_info['calendar_event_id']
                event_summary = event_info['summary']
                
                # Check which calendar(s) this event exists in
                event_calendars = []
                
                for cal_name, cal_id in [("Calendar 1", self.config['calendar_id_1']), 
                                        ("Calendar 2", self.config['calendar_id_2'])]:
                    event = self.get_event_from_calendar(cal_id, event_id)
                    if event:
                        event_calendars.append((cal_name, cal_id, event))
                        
                        # Track calendar distribution
                        if cal_name not in teacher_stats[teacher_type]['calendars']:
                            teacher_stats[teacher_type]['calendars'][cal_name] = 0
                        teacher_stats[teacher_type]['calendars'][cal_name] += 1
                
                print(f"      Event: {event_summary[:40]}...")
                print(f"      Found in: {[cal[0] for cal in event_calendars]}")
                
                # Check for misrouted events
                for cal_name, cal_id, event in event_calendars:
                    should_exist = self.should_event_exist_in_calendar(teacher_type, cal_id)
                    
                    if not should_exist:
                        misrouted_events.append({
                            'email_id': email_id,
                            'email_subject': email_subject,
                            'sender': sender,
                            'teacher_type': teacher_type,
                            'teacher_desc': teacher_desc,
                            'event_id': event_id,
                            'event_summary': event_summary,
                            'wrong_calendar_id': cal_id,
                            'wrong_calendar_name': cal_name,
                            'event': event
                        })
                        
                        teacher_stats[teacher_type]['misrouted'] += 1
                        
                        print(f"        [!] MISROUTED in {cal_name}")
                    else:
                        print(f"        [OK] Correctly in {cal_name}")
        
        # Print summary statistics
        print("\n" + "=" * 70)
        print("TEACHER EVENT DISTRIBUTION SUMMARY")
        print("=" * 70)
        
        for teacher_type, stats in teacher_stats.items():
            if stats['total'] > 0:
                teacher_desc = {
                    'teacher_1': 'Teacher 1 (should be Calendar 1 only)',
                    'teacher_2': 'Teacher 2 (should be Calendar 2 only)',
                    'teacher_3_4': 'Teacher 3/4 (should be both calendars)',
                    'other': 'Other senders (can be both calendars)'
                }[teacher_type]
                
                print(f"\n{teacher_desc}:")
                print(f"  Total events: {stats['total']}")
                print(f"  Misrouted events: {stats['misrouted']}")
                print(f"  Calendar distribution:")
                for cal_name, count in stats['calendars'].items():
                    print(f"    {cal_name}: {count} events")
        
        print(f"\n[*] Total misrouted events found: {len(misrouted_events)}")
        return misrouted_events
    
    def delete_misrouted_events(self, misrouted_events, dry_run=True):
        """Delete misrouted events"""
        print("\n" + "=" * 70)
        print(f"{'DRY RUN - ' if dry_run else ''}DELETING MISROUTED EVENTS")
        print("=" * 70)
        
        if not misrouted_events:
            print("[+] No misrouted events to delete!")
            return
        
        print(f"[*] Processing {len(misrouted_events)} misrouted events")
        
        if dry_run:
            print("[!] DRY RUN MODE - No events will actually be deleted")
        else:
            print("[!] LIVE MODE - Events will be permanently deleted")
        
        print()
        
        # Group by teacher for better organization
        by_teacher = {}
        for item in misrouted_events:
            teacher_type = item['teacher_type']
            if teacher_type not in by_teacher:
                by_teacher[teacher_type] = []
            by_teacher[teacher_type].append(item)
        
        deleted_count = 0
        error_count = 0
        
        for teacher_type, events in by_teacher.items():
            teacher_desc = {
                'teacher_1': 'Teacher 1 (Calendar 1 only)',
                'teacher_2': 'Teacher 2 (Calendar 2 only)',
                'teacher_3_4': 'Teacher 3/4 (Both calendars)',
                'other': 'Other senders'
            }[teacher_type]
            
            print(f"\n--- {teacher_desc} ---")
            print(f"Misrouted events: {len(events)}")
            
            for item in events:
                event_summary = item['event_summary']
                wrong_calendar_name = item['wrong_calendar_name']
                event_id = item['event_id']
                
                print(f"\n[{'DRY RUN' if dry_run else 'DELETE'}] {event_summary}")
                print(f"  From: {wrong_calendar_name}")
                print(f"  Email: {item['email_subject'][:40]}...")
                print(f"  Event ID: {event_id}")
                
                if not dry_run:
                    try:
                        self.calendar_service.events().delete(
                            calendarId=item['wrong_calendar_id'],
                            eventId=event_id
                        ).execute()
                        
                        print(f"  Status: DELETED")
                        deleted_count += 1
                        
                    except Exception as e:
                        print(f"  Status: ERROR - {e}")
                        error_count += 1
                else:
                    print(f"  Status: WOULD DELETE")
        
        print(f"\n[*] Summary:")
        if dry_run:
            print(f"    Would delete: {len(misrouted_events)} events")
        else:
            print(f"    Successfully deleted: {deleted_count}")
            print(f"    Errors: {error_count}")
    
    def run_cleanup(self, dry_run=True):
        """Run the complete cleanup process"""
        print("ADVANCED TEACHER EVENT CLEANUP TOOL")
        print("=" * 70)
        print("This tool uses email tracking data to accurately identify and remove")
        print("events created by teachers in calendars where they should not exist.")
        print()
        print("TEACHER ROUTING RULES:")
        print(f"- Teacher 1 ({self.config['teacher_1_email']}) -> Calendar 1 only")
        print(f"- Teacher 2 ({self.config['teacher_2_email']}) -> Calendar 2 only")
        print(f"- Teacher 3 ({self.config['teacher_3_email']}) -> Both calendars")
        print(f"- Teacher 4 ({self.config['teacher_4_email']}) -> Both calendars")
        print()
        
        # Authenticate
        self.authenticate()
        
        # Analyze misrouted events
        misrouted_events = self.analyze_misrouted_events()
        
        # Delete misrouted events
        if misrouted_events:
            self.delete_misrouted_events(misrouted_events, dry_run)
            
            if dry_run:
                print("\n[!] This was a DRY RUN. To actually delete events, run:")
                print("python utils/cleanup_misrouted_events_advanced.py --live")
        else:
            print("\n[+] No misrouted teacher events found!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Advanced cleanup for misrouted teacher events')
    parser.add_argument('--live', action='store_true',
                       help='Actually delete events (default is dry-run)')
    
    args = parser.parse_args()
    
    cleanup = AdvancedTeacherEventCleanup()
    cleanup.run_cleanup(dry_run=not args.live)

if __name__ == "__main__":
    main()