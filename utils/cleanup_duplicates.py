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
from auth.secure_credentials import get_secure_credential

GOOGLE_CALENDAR_ID_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')  # Calendar 1
GOOGLE_CALENDAR_ID_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')  # Calendar 2
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
    """Find all Mail2Cal created events from both calendars"""
    print("[*] Searching for Mail2Cal events across both calendars...")
    
    all_mail2cal_events = []
    calendar_ids = [GOOGLE_CALENDAR_ID_1, GOOGLE_CALENDAR_ID_2]
    
    # Search for events created by Mail2Cal (today and future only)
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'  # Today onwards (no past events)
    time_max = (now + timedelta(days=730)).isoformat() + 'Z'  # 2 years ahead
    
    for calendar_id in calendar_ids:
        if not calendar_id:
            continue
            
        try:
            print(f"[*] Checking calendar: {calendar_id}")
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=1000,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Filter for Mail2Cal events (check extended properties)
            for event in events:
                # Check if event has Mail2Cal metadata or source
                source = event.get('source', {})
                extended_props = event.get('extendedProperties', {}).get('private', {})
                
                if (source.get('title', '').startswith('Mail2Cal') or 
                    any('mail2cal' in str(v).lower() for v in extended_props.values()) or
                    extended_props.get('mail2cal_source_email_id')):  # Check for Mail2Cal extended properties
                    # Add calendar info to event for tracking
                    event['_calendar_id'] = calendar_id
                    all_mail2cal_events.append(event)
            
            print(f"[*] Found {len([e for e in all_mail2cal_events if e.get('_calendar_id') == calendar_id])} Mail2Cal events in this calendar")
            
        except HttpError as error:
            print(f"[-] Error fetching events from calendar {calendar_id}: {error}")
    
    print(f"[*] Total Mail2Cal events found: {len(all_mail2cal_events)}")
    return all_mail2cal_events

def find_duplicates(events):
    """Find duplicate events using enhanced logic with email/file ID comparison (WITHIN SAME CALENDAR AND SAME DAY ONLY)"""
    print("[*] Analyzing for duplicates with enhanced email/file ID logic...")
    print("[!] IMPORTANT: Only detecting duplicates WITHIN the same calendar AND same day")
    print("[!] Cross-calendar events are intentional and will be preserved")
    print("[!] Events from same email/file on DIFFERENT days are NOT duplicates")
    
    # Group events by calendar first to ensure we only find duplicates within the same calendar
    events_by_calendar = {}
    for event in events:
        calendar_id = event.get('_calendar_id', 'unknown')
        if calendar_id not in events_by_calendar:
            events_by_calendar[calendar_id] = []
        events_by_calendar[calendar_id].append(event)
    
    print(f"[*] Events distributed across calendars:")
    for cal_id, cal_events in events_by_calendar.items():
        print(f"    {cal_id}: {len(cal_events)} events")
    
    actual_duplicates = {}
    
    # Process each calendar separately
    for calendar_id, calendar_events in events_by_calendar.items():
        print(f"\n[*] Processing calendar: {calendar_id}")
        
        duplicates = {}
        email_id_groups = {}
        
        for event in calendar_events:
            title = event.get('summary', '').lower().strip()
            start = event.get('start', {})
            extended_props = event.get('extendedProperties', {}).get('private', {})
            
            # Get date (handle both date and dateTime) - Fixed to prevent empty date grouping
            date_key = start.get('date')
            if not date_key and start.get('dateTime'):
                date_key = start.get('dateTime')[:10]
            if not date_key:
                # Skip events without valid dates to prevent incorrect grouping
                print(f"    [!] Warning: Event '{event.get('summary', 'Unknown')}' has no valid date, skipping duplicate detection")
                continue
            
            # Extract email/file IDs from extended properties
            source_email_id = extended_props.get('mail2cal_source_email_id', '')
            
            # Create basic duplicate detection key
            basic_key = f"{title}_{date_key}"
            
            # Enhanced duplicate detection: Group by email/file ID + SAME DATE (within this calendar)
            if source_email_id:
                email_key = f"email_{source_email_id}_{date_key}"
                if email_key not in email_id_groups:
                    email_id_groups[email_key] = []
                email_id_groups[email_key].append(event)
                # Debug logging for email grouping
                if len(email_id_groups[email_key]) > 1:
                    print(f"    [DEBUG] Found potential duplicate: Email ID {source_email_id}, Date {date_key}, Events: {len(email_id_groups[email_key])}")
            
            # Also maintain basic title+date grouping for events without email IDs (within this calendar)
            if basic_key not in duplicates:
                duplicates[basic_key] = []
            duplicates[basic_key].append(event)
        
        # Process email/file ID duplicates first (highest accuracy) - WITHIN THIS CALENDAR
        print(f"[*] Phase 1: Checking email/file ID duplicates in {calendar_id}...")
        
        for email_key, email_events in email_id_groups.items():
            if len(email_events) > 1:
                # Same email ID with same date = definite duplicates WITHIN SAME CALENDAR
                source_email_id = email_events[0].get('extendedProperties', {}).get('private', {}).get('mail2cal_source_email_id', '')
                # Extract date from email_key for verification
                date_from_key = email_key.split('_')[-1]
                print(f"  - Email ID {source_email_id}: {len(email_events)} duplicate events found IN SAME CALENDAR on date {date_from_key}")
                
                # Verify all events are actually on the same date
                dates_in_group = set()
                for event in email_events:
                    start = event.get('start', {})
                    event_date = start.get('date') or (start.get('dateTime', '')[:10] if start.get('dateTime') else '')
                    dates_in_group.add(event_date)
                
                if len(dates_in_group) > 1:
                    print(f"    [!] WARNING: Email group contains events from different dates: {dates_in_group}")
                    continue  # Skip this group if dates don't match
                
                # Group by title within same email ID for granular control
                title_groups = {}
                for event in email_events:
                    title = event.get('summary', '').lower().strip()
                    if title not in title_groups:
                        title_groups[title] = []
                    title_groups[title].append(event)
                
                # Add each title group as duplicates
                for title, title_events in title_groups.items():
                    if len(title_events) > 1:
                        duplicate_key = f"{calendar_id}_email_{source_email_id}_{title}_{email_key.split('_')[-1]}"
                        actual_duplicates[duplicate_key] = title_events
        
        # Process basic title+date duplicates for events without email IDs - WITHIN THIS CALENDAR
        print(f"[*] Phase 2: Checking basic title+date duplicates in {calendar_id}...")
        for basic_key, basic_events in duplicates.items():
            if len(basic_events) > 1:
                # Filter out events that already have email IDs (already processed)
                events_without_email_id = [
                    event for event in basic_events 
                    if not event.get('extendedProperties', {}).get('private', {}).get('mail2cal_source_email_id')
                ]
                
                if len(events_without_email_id) > 1:
                    print(f"  - Basic match {basic_key}: {len(events_without_email_id)} duplicate events without email IDs IN SAME CALENDAR")
                    actual_duplicates[f"{calendar_id}_basic_{basic_key}"] = events_without_email_id
    
    print(f"\n[+] Enhanced duplicate detection complete (same-calendar AND same-day only):")
    print(f"    Total duplicate groups found: {len(actual_duplicates)}")
    print(f"    Email/File ID duplicates (same day): {len([k for k in actual_duplicates.keys() if '_email_' in k])}")
    print(f"    Basic title+date duplicates (same day): {len([k for k in actual_duplicates.keys() if '_basic_' in k])}")
    
    for key, duplicate_events in actual_duplicates.items():
        # Show more detailed info about duplicates
        sample_event = duplicate_events[0]
        extended_props = sample_event.get('extendedProperties', {}).get('private', {})
        email_id = extended_props.get('mail2cal_source_email_id', 'N/A')
        calendar_id = sample_event.get('_calendar_id', 'Unknown')
        
        print(f"  - {key}: {len(duplicate_events)} duplicates WITHIN SAME CALENDAR")
        print(f"    Email ID: {email_id}")
        print(f"    Calendar: {calendar_id}")
        print(f"    Title: {sample_event.get('summary', '')[:50]}...")
    
    return actual_duplicates

def cleanup_duplicates(service, duplicates):
    """Remove duplicate events, keeping the most recent one"""
    print("[*] Cleaning up duplicates with enhanced multi-calendar support...")
    
    total_deleted = 0
    
    for key, duplicate_events in duplicates.items():
        if len(duplicate_events) <= 1:
            continue
        
        # Sort by creation time (keep most recent)
        duplicate_events.sort(key=lambda x: x.get('created', ''), reverse=True)
        
        # Keep the first (most recent), delete the rest
        events_to_delete = duplicate_events[1:]
        
        print(f"[*] Processing duplicates for: {key}")
        print(f"    Keeping: {duplicate_events[0]['id']} (Calendar: {duplicate_events[0].get('_calendar_id', 'Unknown')})")
        print(f"    Deleting: {len(events_to_delete)} events")
        
        for event in events_to_delete:
            calendar_id = event.get('_calendar_id')
            if not calendar_id:
                print(f"    [-] Warning: No calendar ID found for event {event['id']}, skipping")
                continue
                
            try:
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=event['id']
                ).execute()
                print(f"    [+] Deleted: {event['id']} from calendar {calendar_id}")
                total_deleted += 1
            except HttpError as error:
                print(f"    [-] Error deleting {event['id']} from calendar {calendar_id}: {error}")
    
    print(f"[+] Enhanced cleanup complete:")
    print(f"    Total events deleted: {total_deleted}")
    print(f"    Events processed from both calendars successfully")

def main():
    """Main cleanup function with enhanced email/file ID duplicate detection"""
    print("[*] Mail2Cal Enhanced Duplicate Cleanup Tool")
    print("[*] Features: Online calendar lookup + Email/File ID comparison")
    print("=" * 65)
    
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
    
    print("\n[+] Enhanced duplicate cleanup completed!")
    print("[*] Advanced features used:")
    print("    ✓ Online calendar event lookup across both calendars")
    print("    ✓ Email/File ID comparison for accurate duplicate detection")
    print("    ✓ Same-calendar AND same-day duplicate detection only")
    print("    ✓ Multi-calendar cleanup support")
    print("    ✓ Events from same email/file on DIFFERENT days preserved")
    print("[!] IMPORTANT: Cross-calendar events were intentionally preserved")
    print("[!] IMPORTANT: Events from same source on different days were preserved")
    print("[*] You can now run the full Mail2Cal system")

if __name__ == "__main__":
    main()