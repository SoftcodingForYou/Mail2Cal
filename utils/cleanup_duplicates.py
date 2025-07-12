#!/usr/bin/env python3
"""
Clean up duplicate calendar events before running the full system
"""

import os
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration - Load from secure storage
import sys
sys.path.append('..')
from secure_credentials import get_secure_credential

GOOGLE_CALENDAR_ID = get_secure_credential('GOOGLE_CALENDAR_ID_1')  # Default to Calendar 1
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate():
    """Authenticate with Google Calendar API"""
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def find_school_events(service):
    """Find all Mail2Cal created events"""
    print("[*] Searching for Mail2Cal events...")
    
    # Search for events created by Mail2Cal
    now = datetime.utcnow()
    time_min = (now - timedelta(days=365)).isoformat() + 'Z'  # 1 year ago
    time_max = (now + timedelta(days=365)).isoformat() + 'Z'  # 1 year ahead
    
    try:
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=1000,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Filter for Mail2Cal events (check extended properties)
        mail2cal_events = []
        for event in events:
            # Check if event has Mail2Cal metadata or source
            source = event.get('source', {})
            extended_props = event.get('extendedProperties', {}).get('private', {})
            
            if (source.get('title', '').startswith('Mail2Cal') or 
                any('mail2cal' in str(v).lower() for v in extended_props.values()) or
                extended_props):  # Any extended properties likely from Mail2Cal
                mail2cal_events.append(event)
        
        print(f"[*] Found {len(mail2cal_events)} Mail2Cal events")
        return mail2cal_events
        
    except HttpError as error:
        print(f"[-] Error fetching events: {error}")
        return []

def find_duplicates(events):
    """Find duplicate events based on title and date"""
    print("[*] Analyzing for duplicates...")
    
    duplicates = {}
    
    for event in events:
        title = event.get('summary', '').lower().strip()
        start = event.get('start', {})
        
        # Get date (handle both date and dateTime)
        date_key = start.get('date') or start.get('dateTime', '')[:10]
        
        # Create a key for duplicate detection
        key = f"{title}_{date_key}"
        
        if key not in duplicates:
            duplicates[key] = []
        duplicates[key].append(event)
    
    # Find actual duplicates (more than 1 event with same key)
    actual_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
    
    print(f"[*] Found {len(actual_duplicates)} sets of duplicates")
    
    for key, duplicate_events in actual_duplicates.items():
        print(f"  - {key}: {len(duplicate_events)} duplicates")
    
    return actual_duplicates

def cleanup_duplicates(service, duplicates):
    """Remove duplicate events, keeping the most recent one"""
    print("[*] Cleaning up duplicates...")
    
    total_deleted = 0
    
    for key, duplicate_events in duplicates.items():
        if len(duplicate_events) <= 1:
            continue
        
        # Sort by creation time (keep most recent)
        duplicate_events.sort(key=lambda x: x.get('created', ''), reverse=True)
        
        # Keep the first (most recent), delete the rest
        events_to_delete = duplicate_events[1:]
        
        print(f"[*] Processing duplicates for: {key}")
        print(f"    Keeping: {duplicate_events[0]['id']}")
        print(f"    Deleting: {len(events_to_delete)} events")
        
        for event in events_to_delete:
            try:
                service.events().delete(
                    calendarId=GOOGLE_CALENDAR_ID,
                    eventId=event['id']
                ).execute()
                print(f"    [+] Deleted: {event['id']}")
                total_deleted += 1
            except HttpError as error:
                print(f"    [-] Error deleting {event['id']}: {error}")
    
    print(f"[+] Total events deleted: {total_deleted}")

def main():
    """Main cleanup function"""
    print("[*] Mail2Cal Duplicate Cleanup Tool")
    print("=" * 50)
    
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
    print("[*] You can now run the full Mail2Cal system")

if __name__ == "__main__":
    main()