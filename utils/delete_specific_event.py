#!/usr/bin/env python3
"""
Delete Specific Event Tool
Allows deletion of specific events by ID or search criteria
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from googleapiclient.discovery import build
from auth.secure_credentials import get_secure_credential

class EventDeleter:
    def __init__(self):
        """Initialize the event deleter"""
        self.calendar_service = None
        self.config = self.load_configuration()
        
    def load_configuration(self):
        """Load configuration from secure credentials"""
        try:
            config = {
                'calendar_id_1': get_secure_credential('GOOGLE_CALENDAR_ID_1'),
                'calendar_id_2': get_secure_credential('GOOGLE_CALENDAR_ID_2')
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
    
    def get_event_details(self, calendar_id, event_id):
        """Get details of a specific event"""
        try:
            event = self.calendar_service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return event
        except Exception as e:
            print(f"[!] Error getting event details: {e}")
            return None
    
    def delete_event(self, calendar_id, event_id, dry_run=True):
        """Delete a specific event"""
        calendar_name = "Calendar 1" if calendar_id == self.config['calendar_id_1'] else "Calendar 2"
        
        # Get event details first
        event = self.get_event_details(calendar_id, event_id)
        if not event:
            print(f"[!] Event {event_id} not found in {calendar_name}")
            return False
        
        event_title = event.get('summary', 'Untitled')
        event_start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}DELETING EVENT:")
        print(f"Title: {event_title}")
        print(f"Start: {event_start}")
        print(f"Calendar: {calendar_name}")
        print(f"Event ID: {event_id}")
        
        if dry_run:
            print("[!] DRY RUN MODE - Event would be deleted")
            return True
        else:
            # Confirm deletion
            print(f"\n[!] WARNING: This will permanently delete the event!")
            response = input("Type 'DELETE' to confirm: ").strip()
            if response != 'DELETE':
                print("[!] Deletion cancelled")
                return False
            
            try:
                self.calendar_service.events().delete(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                
                print(f"[+] Event successfully deleted from {calendar_name}")
                return True
                
            except Exception as e:
                print(f"[!] Error deleting event: {e}")
                return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Delete specific calendar events')
    parser.add_argument('--event-id', required=True, help='Event ID to delete')
    parser.add_argument('--calendar', choices=['1', '2'], required=True, 
                       help='Calendar number (1 or 2)')
    parser.add_argument('--live', action='store_true',
                       help='Actually delete the event (default is dry-run)')
    
    args = parser.parse_args()
    
    deleter = EventDeleter()
    deleter.authenticate()
    
    # Determine calendar ID
    calendar_id = deleter.config['calendar_id_1'] if args.calendar == '1' else deleter.config['calendar_id_2']
    
    # Delete the event
    success = deleter.delete_event(calendar_id, args.event_id, dry_run=not args.live)
    
    if success and not args.live:
        print(f"\n[*] To actually delete this event, run:")
        print(f"python utils/delete_specific_event.py --event-id {args.event_id} --calendar {args.calendar} --live")

if __name__ == "__main__":
    main()