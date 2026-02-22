#!/usr/bin/env python3
"""
Find and fix cancelled Mail2Cal events
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from core.config import get_calendar_ids

SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/gmail.readonly']

def fix_cancelled_events():
    """Find and reactivate cancelled Mail2Cal events"""

    # Load configuration
    try:
        cal_id_1, cal_id_2 = get_calendar_ids()
        config = {'calendar_id_1': cal_id_1, 'calendar_id_2': cal_id_2}
    except Exception as e:
        print(f"[!] Error loading configuration: {e}")
        return
    
    # Authenticate with proper flow
    creds = None
    
    # Load existing credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[*] Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("[*] Starting authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        print("[+] Credentials saved")
    
    calendar_service = build('calendar', 'v3', credentials=creds)
    print("[+] Authenticated with Google Calendar API")
    
    print("\n[*] FINDING CANCELLED MAIL2CAL EVENTS")
    print("=" * 60)
    
    cancelled_events = []
    
    # Check both calendars
    for cal_name, cal_id in [("Calendar 1", config['calendar_id_1']), 
                            ("Calendar 2", config['calendar_id_2'])]:
        
        print(f"\n[*] Checking {cal_name}...")
        
        # Get events including cancelled ones
        try:
            # Look back and forward to get all events
            start_date = datetime.now() - timedelta(days=60)
            end_date = datetime.now() + timedelta(days=730)  # 2 years ahead
            
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            result = calendar_service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2000,
                singleEvents=True,
                orderBy='startTime',
                showDeleted=True  # Include cancelled/deleted events
            ).execute()
            
            events = result.get('items', [])
            print(f"    Found {len(events)} total events (including cancelled)")
            
            for event in events:
                # Check if this is a Mail2Cal event that's cancelled
                extended_props = event.get('extendedProperties', {}).get('private', {})
                is_mail2cal = bool(extended_props.get('mail2cal_created_at'))
                status = event.get('status', 'confirmed')
                
                if is_mail2cal and status == 'cancelled':
                    cancelled_events.append({
                        'event': event,
                        'calendar_name': cal_name,
                        'calendar_id': cal_id
                    })
                    
                    event_title = event.get('summary', 'Untitled')
                    event_start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                    
                    print(f"    [!] CANCELLED: {event_title[:50]}...")
                    print(f"        Start: {event_start}")
                    print(f"        Event ID: {event.get('id')}")
                    
        except Exception as e:
            print(f"    [!] Error checking {cal_name}: {e}")
    
    print(f"\n[*] Found {len(cancelled_events)} cancelled Mail2Cal events")
    
    if not cancelled_events:
        print("[+] No cancelled events found!")
        return
    
    # Auto-approve reactivation for automation
    print(f"\n[*] Auto-approving reactivation of {len(cancelled_events)} cancelled events...")
    # Skip user input for automation
    
    print("\n[*] REACTIVATING CANCELLED EVENTS")
    print("=" * 60)
    
    reactivated_count = 0
    error_count = 0
    
    for item in cancelled_events:
        event = item['event']
        calendar_id = item['calendar_id']
        calendar_name = item['calendar_name']
        
        event_title = event.get('summary', 'Untitled')
        event_id = event.get('id')
        
        print(f"\n[REACTIVATE] {event_title}")
        print(f"  In: {calendar_name}")
        print(f"  Event ID: {event_id}")
        
        try:
            # Update the event to change status from cancelled to confirmed
            event['status'] = 'confirmed'
            
            updated_event = calendar_service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            print(f"  Status: REACTIVATED")
            reactivated_count += 1
            
        except Exception as e:
            print(f"  Status: ERROR - {e}")
            error_count += 1
    
    print(f"\n[*] Summary:")
    print(f"    Successfully reactivated: {reactivated_count}")
    print(f"    Errors: {error_count}")

if __name__ == "__main__":
    fix_cancelled_events()