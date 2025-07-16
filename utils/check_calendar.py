#!/usr/bin/env python3
"""
Check what events are in the calendar
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
from auth.secure_credentials import get_secure_credential

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

def check_recent_events(service):
    """Check recent events in calendar"""
    print("[*] Checking recent calendar events...")
    
    # Search for recent events
    now = datetime.utcnow()
    time_min = (now - timedelta(days=30)).isoformat() + 'Z'  # 30 days ago
    time_max = (now + timedelta(days=60)).isoformat() + 'Z'  # 60 days ahead
    
    try:
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        print(f"[*] Found {len(events)} recent events")
        
        for i, event in enumerate(events, 1):
            start = event.get('start', {})
            date_str = start.get('dateTime', start.get('date', 'No date'))
            title = event.get('summary', 'No title')
            event_id = event.get('id', 'No ID')
            
            # Check for source or extended properties
            source = event.get('source', {})
            extended_props = event.get('extendedProperties', {})
            
            source_info = ""
            if source:
                source_info = f" [Source: {source.get('title', 'Unknown')}]"
            if extended_props:
                source_info += f" [Extended Props: Yes]"
            
            print(f"{i:2d}. {date_str[:10]} - {title[:60]}{source_info}")
            print(f"    ID: {event_id}")
        
        return events
        
    except HttpError as error:
        print(f"[-] Error fetching events: {error}")
        return []

def main():
    """Main function"""
    print("[*] Calendar Event Checker")
    print("=" * 50)
    
    # Authenticate
    service = authenticate()
    
    # Check events
    events = check_recent_events(service)

if __name__ == "__main__":
    main()