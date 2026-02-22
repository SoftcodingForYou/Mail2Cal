#!/usr/bin/env python3
"""
Test if a specific tracked event still exists in calendars
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pickle
from googleapiclient.discovery import build
from core.config import get_calendar_ids

def test_event_existence():
    """Test if specific event exists in calendars"""

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
    
    # The specific event we're looking for from Teacher 1's email
    event_id = "4s2bel5l1vq74qs7cm3q5tct5g"
    event_title = "Experimento de Science con esfera de plumavit"
    
    print(f"\n[*] Testing existence of event: {event_title}")
    print(f"[*] Event ID: {event_id}")
    
    found_in = []
    
    # Check both calendars
    for cal_name, cal_id in [("Calendar 1", config['calendar_id_1']), 
                            ("Calendar 2", config['calendar_id_2'])]:
        try:
            event = calendar_service.events().get(
                calendarId=cal_id,
                eventId=event_id
            ).execute()
            
            print(f"[+] Found in {cal_name}:")
            print(f"    Title: {event.get('summary', 'Untitled')}")
            print(f"    Start: {event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))}")
            found_in.append(cal_name)
            
        except Exception as e:
            print(f"[-] Not found in {cal_name}: {e}")
    
    if not found_in:
        print(f"\n[!] Event '{event_title}' does not exist in any calendar!")
        print(f"[!] This confirms the event was deleted and needs to be recreated")
        return False
    else:
        print(f"\n[+] Event found in: {', '.join(found_in)}")
        return True

if __name__ == "__main__":
    test_event_existence()