#!/usr/bin/env python3
"""
Find Specific Event Tool
Helps locate specific events and identify which calendar they're in
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from auth.secure_credentials import get_secure_credential

class EventFinder:
    def __init__(self):
        """Initialize the event finder"""
        self.calendar_service = None
        self.config = self.load_configuration()
        
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
    
    def search_events_by_keyword(self, keyword, days_back=30):
        """Search for events containing a specific keyword"""
        print(f"\n[*] Searching for events containing: '{keyword}'")
        print("=" * 60)
        
        # Calculate date range
        end_date = datetime.now() + timedelta(days=30)  # Also look ahead
        start_date = datetime.now() - timedelta(days=days_back)
        
        time_min = start_date.isoformat() + 'Z'
        time_max = end_date.isoformat() + 'Z'
        
        found_events = []
        
        # Search both calendars
        for cal_name, cal_id in [("Calendar 1", self.config['calendar_id_1']), 
                                ("Calendar 2", self.config['calendar_id_2'])]:
            print(f"\n[*] Searching {cal_name}...")
            
            try:
                result = self.calendar_service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=1000,
                    singleEvents=True,
                    orderBy='startTime',
                    q=keyword  # Search by keyword
                ).execute()
                
                events = result.get('items', [])
                print(f"    Found {len(events)} matching events")
                
                for event in events:
                    # Get extended properties to find source info
                    extended_props = event.get('extendedProperties', {}).get('private', {})
                    source_email_id = extended_props.get('mail2cal_source_email_id', 'Unknown')
                    created_at = extended_props.get('mail2cal_created_at', 'Unknown')
                    
                    found_events.append({
                        'calendar_name': cal_name,
                        'calendar_id': cal_id,
                        'event': event,
                        'source_email_id': source_email_id,
                        'created_at': created_at
                    })
                    
            except Exception as e:
                print(f"    Error searching {cal_name}: {e}")
        
        return found_events
    
    def analyze_event_source(self, source_email_id):
        """Analyze event source from tracking data"""
        try:
            with open('event_mappings.json', 'r', encoding='utf-8') as f:
                mappings = json.load(f)
            
            if source_email_id in mappings:
                mapping = mappings[source_email_id]
                sender = mapping.get('email_sender', 'Unknown')
                subject = mapping.get('email_subject', 'Unknown')
                date = mapping.get('email_date', 'Unknown')
                
                # Identify teacher
                teacher_info = self.identify_teacher_from_sender(sender)
                
                return {
                    'sender': sender,
                    'subject': subject,
                    'date': date,
                    'teacher_info': teacher_info
                }
            else:
                return None
                
        except Exception as e:
            print(f"[!] Error reading event mappings: {e}")
            return None
    
    def identify_teacher_from_sender(self, sender):
        """Identify teacher from email sender"""
        sender_lower = sender.lower()
        
        if self.config['teacher_1_email'].lower() in sender_lower:
            return {
                'type': 'teacher_1',
                'name': 'Rosa',
                'description': 'Rosa (Calendar 1 only)',
                'should_be_in': ['Calendar 1']
            }
        elif self.config['teacher_2_email'].lower() in sender_lower:
            return {
                'type': 'teacher_2', 
                'name': 'Karla',
                'description': 'Karla (Calendar 2 only)',
                'should_be_in': ['Calendar 2']
            }
        elif (self.config['teacher_3_email'].lower() in sender_lower or 
              self.config['teacher_4_email'].lower() in sender_lower):
            return {
                'type': 'teacher_3_4',
                'name': 'Miriam/Lisette',
                'description': 'Miriam/Lisette (Both calendars)',
                'should_be_in': ['Calendar 1', 'Calendar 2']
            }
        else:
            return {
                'type': 'other',
                'name': 'Other',
                'description': 'Other sender (Both calendars)',
                'should_be_in': ['Calendar 1', 'Calendar 2']
            }
    
    def display_event_details(self, found_events):
        """Display detailed information about found events"""
        print(f"\n[*] DETAILED EVENT ANALYSIS")
        print("=" * 60)
        
        if not found_events:
            print("[!] No events found matching the search criteria")
            return
        
        misrouted_events = []
        
        for i, item in enumerate(found_events, 1):
            event = item['event']
            calendar_name = item['calendar_name']
            source_email_id = item['source_email_id']
            
            print(f"\n--- Event {i} ---")
            print(f"Title: {event.get('summary', 'Untitled')}")
            print(f"Start: {event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))}")
            print(f"Calendar: {calendar_name}")
            print(f"Event ID: {event.get('id', 'Unknown')}")
            print(f"Source Email ID: {source_email_id}")
            
            # Analyze source
            source_info = self.analyze_event_source(source_email_id)
            if source_info:
                teacher_info = source_info['teacher_info']
                print(f"Email Subject: {source_info['subject']}")
                print(f"Email Sender: {source_info['sender']}")
                print(f"Teacher: {teacher_info['description']}")
                print(f"Should be in: {', '.join(teacher_info['should_be_in'])}")
                
                # Check if this event is misrouted
                if calendar_name not in teacher_info['should_be_in']:
                    print(f"[!] MISROUTED: This event should NOT be in {calendar_name}")
                    misrouted_events.append({
                        'event': event,
                        'calendar_name': calendar_name,
                        'calendar_id': item['calendar_id'],
                        'teacher_info': teacher_info,
                        'source_info': source_info
                    })
                else:
                    print(f"[OK] Correctly placed in {calendar_name}")
            else:
                print(f"[!] Could not find source information")
        
        # Summary of misrouted events
        if misrouted_events:
            print(f"\n[!] SUMMARY: Found {len(misrouted_events)} misrouted events")
            print("=" * 60)
            
            for item in misrouted_events:
                event = item['event']
                teacher_info = item['teacher_info']
                
                print(f"\n[MISROUTED] {event.get('summary', 'Untitled')}")
                print(f"  Currently in: {item['calendar_name']}")
                print(f"  Should be in: {', '.join(teacher_info['should_be_in'])}")
                print(f"  Teacher: {teacher_info['description']}")
                print(f"  Event ID: {event.get('id')}")
        else:
            print(f"\n[+] All events are correctly placed!")
        
        return misrouted_events

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Find and analyze specific events')
    parser.add_argument('keyword', help='Keyword to search for in event titles')
    parser.add_argument('--days-back', type=int, default=30,
                       help='Number of days back to search (default: 30)')
    
    args = parser.parse_args()
    
    finder = EventFinder()
    finder.authenticate()
    
    # Search for events
    found_events = finder.search_events_by_keyword(args.keyword, args.days_back)
    
    # Display detailed analysis
    misrouted_events = finder.display_event_details(found_events)
    
    if misrouted_events:
        print(f"\n[*] To delete these misrouted events, you can use:")
        print("python utils/cleanup_misrouted_events_advanced.py --live")

if __name__ == "__main__":
    main()