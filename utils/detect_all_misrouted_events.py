#!/usr/bin/env python3
"""
Comprehensive Misrouted Event Detection
Finds ALL misrouted events in calendars, regardless of tracking data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pickle
import re
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from auth.secure_credentials import get_secure_credential

class ComprehensiveMisrouteDetector:
    def __init__(self):
        """Initialize the comprehensive detector"""
        self.calendar_service = None
        self.config = self.load_configuration()
        self.event_mappings = self.load_event_mappings()
        
    def load_configuration(self):
        """Load configuration from secure credentials"""
        try:
            config = {
                'calendar_id_1': get_secure_credential('GOOGLE_CALENDAR_ID_1'),
                'calendar_id_2': get_secure_credential('GOOGLE_CALENDAR_ID_2'),
                'teacher_1_email': get_secure_credential('TEACHER_1_EMAIL'),
                'teacher_2_email': get_secure_credential('TEACHER_2_EMAIL'),
                'teacher_3_email': get_secure_credential('TEACHER_3_EMAIL'),
                'teacher_4_email': get_secure_credential('TEACHER_4_EMAIL')
            }
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
            print("[!] event_mappings.json not found - will analyze all events")
            return {}
        except Exception as e:
            print(f"[!] Error loading event mappings: {e}")
            return {}
    
    def authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            print("[!] Authentication required. Please run the main system first to authenticate.")
            raise SystemExit("Cannot authenticate without valid credentials")
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        print("[+] Authenticated with Google Calendar API")
    
    def get_all_events_from_calendar(self, calendar_id, days_back=60):
        """Get all events from a calendar - focus on future events"""
        try:
            # Look back a bit for recent events, but focus on future events
            start_date = datetime.now() - timedelta(days=days_back)
            # Look far into the future to catch all scheduled events (2 years ahead)
            end_date = datetime.now() + timedelta(days=730)
            
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2000,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = result.get('items', [])
            return events
            
        except Exception as e:
            print(f"[!] Error fetching events: {e}")
            return []
    
    def identify_teacher_from_event_content(self, event):
        """Try to identify teacher from event content, metadata, or description"""
        # Check extended properties first
        extended_props = event.get('extendedProperties', {}).get('private', {})
        source_email_id = extended_props.get('mail2cal_source_email_id', '')
        
        # If we have tracking data, use it
        if source_email_id and source_email_id in self.event_mappings:
            mapping = self.event_mappings[source_email_id]
            sender = mapping.get('email_sender', '')
            return self.identify_teacher_from_sender(sender)
        
        # If no tracking data, try to identify from event content
        event_title = event.get('summary', '').lower()
        event_description = event.get('description', '').lower()
        event_content = f"{event_title} {event_description}"
        
        # Look for teacher name patterns in the content
        teacher_patterns = {
            'teacher_1': ['rosa', 'contreras'],
            'teacher_2': ['karla', 'morales'],
            'teacher_3': ['miriam', 'pacheco'],
            'teacher_4': ['lisette', 'rios']
        }
        
        for teacher_key, patterns in teacher_patterns.items():
            if any(pattern in event_content for pattern in patterns):
                return self.get_teacher_info(teacher_key)
        
        # For untracked events, try to match with tracked events of the same title
        # This helps identify misrouted events that lost their tracking
        for email_id, mapping in self.event_mappings.items():
            sender = mapping.get('email_sender', '')
            for event_info in mapping.get('calendar_events', []):
                tracked_title = event_info.get('summary', '').lower()
                if tracked_title == event_title:
                    # Found a tracked event with the same title - use its teacher
                    return self.identify_teacher_from_sender(sender)
        
        # Look for specific class-related keywords
        calendar_1_keywords = ['kinder', 'pre-kinder', 'play group', 'jardin a', 'clase a']
        calendar_2_keywords = ['jardin b', 'clase b', 'segundo grupo']
        
        if any(keyword in event_content for keyword in calendar_1_keywords):
            return self.get_teacher_info('teacher_1')  # Assume Rosa for Calendar 1 specific content
        elif any(keyword in event_content for keyword in calendar_2_keywords):
            return self.get_teacher_info('teacher_2')  # Assume Karla for Calendar 2 specific content
        
        # If we can't identify, assume it's a general event
        return self.get_teacher_info('other')
    
    def identify_teacher_from_sender(self, sender):
        """Identify teacher from email sender"""
        sender_lower = sender.lower()
        
        if self.config['teacher_1_email'].lower() in sender_lower:
            return self.get_teacher_info('teacher_1')
        elif self.config['teacher_2_email'].lower() in sender_lower:
            return self.get_teacher_info('teacher_2')
        elif (self.config['teacher_3_email'].lower() in sender_lower or 
              self.config['teacher_4_email'].lower() in sender_lower):
            return self.get_teacher_info('teacher_3_4')
        else:
            return self.get_teacher_info('other')
    
    def is_likely_misrouted_mail2cal_event(self, event_title):
        """Check if an untracked event is likely a misrouted Mail2Cal event"""
        # Get all tracked event titles from our mapping data
        tracked_titles = set()
        for email_id, mapping in self.event_mappings.items():
            for event_info in mapping.get('calendar_events', []):
                tracked_titles.add(event_info.get('summary', '').lower())
        
        # Check if this event title matches any tracked event exactly
        if event_title in tracked_titles:
            return True
        
        # Check for similar titles (common misrouted event patterns)
        similar_patterns = [
            'entrega de fotografia',
            'reunion de apoderados', 
            'dia de la familia',
            'evaluacion',
            'actividad',
            'experimento',
            'celebracion',
            'juegos',
            'manualidad'
        ]
        
        for pattern in similar_patterns:
            if pattern in event_title:
                return True
        
        return False
    
    def get_teacher_info(self, teacher_type):
        """Get teacher information structure"""
        teacher_info = {
            'teacher_1': {
                'type': 'teacher_1',
                'name': 'Rosa',
                'email': self.config['teacher_1_email'],
                'description': 'Rosa (Calendar 1 only)',
                'should_be_in': ['Calendar 1']
            },
            'teacher_2': {
                'type': 'teacher_2',
                'name': 'Karla',
                'email': self.config['teacher_2_email'],
                'description': 'Karla (Calendar 2 only)',
                'should_be_in': ['Calendar 2']
            },
            'teacher_3_4': {
                'type': 'teacher_3_4',
                'name': 'Miriam/Lisette',
                'email': f"{self.config['teacher_3_email']}/{self.config['teacher_4_email']}",
                'description': 'Miriam/Lisette (Both calendars)',
                'should_be_in': ['Calendar 1', 'Calendar 2']
            },
            'other': {
                'type': 'other',
                'name': 'Other/Unknown',
                'email': 'Various',
                'description': 'Other sender (Both calendars)',
                'should_be_in': ['Calendar 1', 'Calendar 2']
            }
        }
        return teacher_info.get(teacher_type, teacher_info['other'])
    
    def analyze_all_events_for_misrouting(self, days_back=60):
        """Analyze all events in both calendars to find misrouted ones"""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE MISROUTED EVENT ANALYSIS")
        print("=" * 80)
        print("Analyzing ALL events in both calendars to find misrouted events...")
        print(f"Date range: {days_back} days back to 2 years in the future")
        print()
        
        misrouted_events = []
        calendar_analysis = {}
        
        # Analyze both calendars
        for cal_name, cal_id in [("Calendar 1", self.config['calendar_id_1']), 
                                ("Calendar 2", self.config['calendar_id_2'])]:
            print(f"\n[*] Analyzing {cal_name}...")
            events = self.get_all_events_from_calendar(cal_id, days_back)
            print(f"    Found {len(events)} events to analyze")
            
            calendar_analysis[cal_name] = {
                'total_events': len(events),
                'teacher_1_events': 0,
                'teacher_2_events': 0,
                'teacher_3_4_events': 0,
                'other_events': 0,
                'misrouted_events': 0
            }
            
            for event in events:
                # Check if this is a Mail2Cal event - but DON'T skip untracked events
                # because misrouted events often lose their tracking
                extended_props = event.get('extendedProperties', {}).get('private', {})
                mail2cal_event = bool(extended_props.get('mail2cal_created_at'))
                
                # For untracked events, check if they have similar titles to tracked events
                # This helps catch misrouted events that lost their tracking
                if not mail2cal_event:
                    # Check if this event title matches any tracked events from our mapping data
                    event_title = event.get('summary', '').lower()
                    is_likely_mail2cal = self.is_likely_misrouted_mail2cal_event(event_title)
                    
                    if not is_likely_mail2cal:
                        # Skip non-Mail2Cal events (manually created, imported, etc.)
                        continue
                    else:
                        print(f"    [!] Found untracked event that appears to be misrouted Mail2Cal event: {event.get('summary', 'Untitled')[:50]}...")
                
                # Identify teacher for this event
                teacher_info = self.identify_teacher_from_event_content(event)
                teacher_type = teacher_info['type']
                
                # Count events by teacher
                if teacher_type == 'teacher_1':
                    calendar_analysis[cal_name]['teacher_1_events'] += 1
                elif teacher_type == 'teacher_2':
                    calendar_analysis[cal_name]['teacher_2_events'] += 1
                elif teacher_type == 'teacher_3_4':
                    calendar_analysis[cal_name]['teacher_3_4_events'] += 1
                else:
                    calendar_analysis[cal_name]['other_events'] += 1
                
                # Check if this event is misrouted
                if cal_name not in teacher_info['should_be_in']:
                    misrouted_events.append({
                        'event': event,
                        'calendar_name': cal_name,
                        'calendar_id': cal_id,
                        'teacher_info': teacher_info,
                        'event_id': event.get('id'),
                        'event_title': event.get('summary', 'Untitled'),
                        'event_start': event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                    })
                    
                    calendar_analysis[cal_name]['misrouted_events'] += 1
                    
                    print(f"    [!] MISROUTED: {event.get('summary', 'Untitled')[:50]}...")
                    print(f"        Teacher: {teacher_info['description']}")
                    print(f"        Should be in: {', '.join(teacher_info['should_be_in'])}")
                    print(f"        Currently in: {cal_name}")
                    print(f"        Event ID: {event.get('id')}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)
        
        for cal_name, analysis in calendar_analysis.items():
            print(f"\n{cal_name}:")
            print(f"  Total Mail2Cal events: {analysis['total_events']}")
            print(f"  Rosa events: {analysis['teacher_1_events']} {'(should be 0)' if cal_name == 'Calendar 2' else '(correct)'}")
            print(f"  Karla events: {analysis['teacher_2_events']} {'(should be 0)' if cal_name == 'Calendar 1' else '(correct)'}")
            print(f"  Miriam/Lisette events: {analysis['teacher_3_4_events']} (correct - can be in both)")
            print(f"  Other events: {analysis['other_events']} (correct - can be in both)")
            print(f"  MISROUTED events: {analysis['misrouted_events']}")
        
        print(f"\n[*] Total misrouted events found: {len(misrouted_events)}")
        return misrouted_events
    
    def delete_misrouted_events(self, misrouted_events, dry_run=True):
        """Delete the misrouted events"""
        print("\n" + "=" * 80)
        print(f"{'DRY RUN - ' if dry_run else ''}DELETING MISROUTED EVENTS")
        print("=" * 80)
        
        if not misrouted_events:
            print("[+] No misrouted events to delete!")
            return
        
        print(f"[*] Processing {len(misrouted_events)} misrouted events")
        
        if dry_run:
            print("[!] DRY RUN MODE - No events will actually be deleted")
        else:
            print("[!] LIVE MODE - Events will be permanently deleted")
        
        deleted_count = 0
        error_count = 0
        
        for item in misrouted_events:
            event_title = item['event_title']
            calendar_name = item['calendar_name']
            event_id = item['event_id']
            teacher_info = item['teacher_info']
            
            print(f"\n[{'DRY RUN' if dry_run else 'DELETE'}] {event_title}")
            print(f"  From: {calendar_name}")
            print(f"  Teacher: {teacher_info['description']}")
            print(f"  Should be in: {', '.join(teacher_info['should_be_in'])}")
            print(f"  Event ID: {event_id}")
            
            if not dry_run:
                try:
                    self.calendar_service.events().delete(
                        calendarId=item['calendar_id'],
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
    
    def run_analysis(self, days_back=60, dry_run=True):
        """Run the complete analysis"""
        print("COMPREHENSIVE MISROUTED EVENT DETECTOR")
        print("=" * 80)
        print("This tool analyzes ALL events in both calendars to find misrouted events,")
        print("regardless of whether they have tracking data or not.")
        print()
        print("TEACHER ROUTING RULES:")
        print(f"- Rosa ({self.config['teacher_1_email']}) -> Calendar 1 only")
        print(f"- Karla ({self.config['teacher_2_email']}) -> Calendar 2 only")
        print(f"- Miriam ({self.config['teacher_3_email']}) -> Both calendars")
        print(f"- Lisette ({self.config['teacher_4_email']}) -> Both calendars")
        print()
        
        # Authenticate
        self.authenticate()
        
        # Analyze all events
        misrouted_events = self.analyze_all_events_for_misrouting(days_back)
        
        # Delete misrouted events
        if misrouted_events:
            self.delete_misrouted_events(misrouted_events, dry_run)
            
            if dry_run:
                print("\n[!] This was a DRY RUN. To actually delete events, run:")
                print("python utils/detect_all_misrouted_events.py --live")
        else:
            print("\n[+] No misrouted events found!")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive misrouted event detection and cleanup')
    parser.add_argument('--days-back', type=int, default=60,
                       help='Number of days back to analyze (default: 60)')
    parser.add_argument('--live', action='store_true',
                       help='Actually delete events (default is dry-run)')
    
    args = parser.parse_args()
    
    detector = ComprehensiveMisrouteDetector()
    detector.run_analysis(days_back=args.days_back, dry_run=not args.live)

if __name__ == "__main__":
    main()