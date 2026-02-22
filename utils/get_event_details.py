#!/usr/bin/env python3
"""
Get detailed information about a specific event by ID
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from googleapiclient.discovery import build
from core.config import get_calendar_ids

def get_event_details():
    """Get detailed information about the plumavit event"""

    # Load configuration
    try:
        cal_id_1, cal_id_2 = get_calendar_ids()
        config = {'calendar_id_1': cal_id_1, 'calendar_id_2': cal_id_2}
    except Exception as e:
        print(f"[!] Error loading configuration: {e}")
        return
    
    # Authenticate
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        print("[!] Authentication required")
        return
    
    calendar_service = build('calendar', 'v3', credentials=creds)
    print("[+] Authenticated with Google Calendar API")
    
    # The specific event we're looking for
    event_id = "4s2bel5l1vq74qs7cm3q5tct5g"
    calendar_id = config['calendar_id_1']
    
    try:
        event = calendar_service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        print(f"\n[+] Event Details:")
        print(f"    ID: {event.get('id')}")
        print(f"    Title: {event.get('summary')}")
        print(f"    Description: {event.get('description', 'None')}")
        print(f"    Start: {event.get('start')}")
        print(f"    End: {event.get('end')}")
        print(f"    Location: {event.get('location', 'None')}")
        print(f"    Status: {event.get('status')}")
        print(f"    Visibility: {event.get('visibility', 'default')}")
        
        # Check extended properties
        extended_props = event.get('extendedProperties', {})
        if extended_props:
            print(f"    Extended Properties: {extended_props}")
        
        return event
        
    except Exception as e:
        print(f"[!] Error getting event details: {e}")
        return None

if __name__ == "__main__":
    get_event_details()