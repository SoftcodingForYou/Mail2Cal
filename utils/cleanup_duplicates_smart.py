#!/usr/bin/env python3
"""
AI-Enhanced duplicate cleanup using the Smart Event Merger
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.smart_event_merger import SmartEventMerger
from core.event_tracker import EventTracker
from auth.secure_credentials import get_secure_credential

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

def get_all_mail2cal_events(service):
    """Get all Mail2Cal events from both calendars"""
    
    # Load calendar IDs
    calendar_id_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')
    calendar_id_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')
    
    all_events = []
    
    # Search time range (today and future only - no point deduping past events)
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'  # Today onwards (no past events)
    time_max = (now + timedelta(days=730)).isoformat() + 'Z'  # 2 years ahead
    
    for calendar_name, calendar_id in [("Calendar 1", calendar_id_1), ("Calendar 2", calendar_id_2)]:
        print(f"[*] Scanning {calendar_name} for Mail2Cal events...")
        
        try:
            result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2000,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = result.get('items', [])
            mail2cal_events = []
            
            for event in events:
                # Check if event was created by Mail2Cal
                extended_props = event.get('extendedProperties', {}).get('private', {})
                if extended_props.get('mail2cal_created_at'):
                    event['_calendar_id'] = calendar_id
                    event['_calendar_name'] = calendar_name
                    mail2cal_events.append(event)
            
            print(f"    Found {len(mail2cal_events)} Mail2Cal events in {calendar_name}")
            all_events.extend(mail2cal_events)
            
        except HttpError as error:
            print(f"[-] Error accessing {calendar_name}: {error}")
    
    print(f"\n[+] Total Mail2Cal events found: {len(all_events)}")
    return all_events

def find_ai_duplicates(events):
    """Use AI to find semantic duplicates across all events"""
    print("\n[AI] Analyzing events for intelligent duplicates...")
    print("=" * 60)

    # Initialize AI components
    ai_config = {
        'provider': 'anthropic',
        'api_key_env_var': 'ANTHROPIC_API_KEY',
        'model': get_secure_credential('AI_MODEL'),
        'model_cheap': get_secure_credential('AI_MODEL_CHEAP')
    }

    event_tracker = EventTracker('event_mappings.json')
    smart_merger = SmartEventMerger(ai_config, event_tracker)

    duplicates = []
    processed_events = set()

    # Pre-filtering: Group events by calendar and date first
    print("[*] Pre-filtering: Grouping events by calendar and date...")
    events_by_calendar_date = {}

    for event in events:
        calendar_id = event.get('_calendar_id', 'unknown')

        # Get event date
        start = event.get('start', {})
        event_date = start.get('date') or (start.get('dateTime', '')[:10] if start.get('dateTime') else '')

        if not event_date:
            continue

        # Create key: calendar_id + date
        key = f"{calendar_id}_{event_date}"

        if key not in events_by_calendar_date:
            events_by_calendar_date[key] = []

        events_by_calendar_date[key].append(event)

    # Count how many comparison pairs we'll actually make
    total_comparisons = 0
    for group_events in events_by_calendar_date.values():
        if len(group_events) > 1:
            total_comparisons += len(group_events) * (len(group_events) - 1) // 2

    print(f"[*] Pre-filtering complete:")
    print(f"    Total events: {len(events)}")
    print(f"    Unique calendar+date groups: {len(events_by_calendar_date)}")
    print(f"    AI comparisons needed (after pre-filtering): {total_comparisons}")
    print(f"    Comparisons saved: {len(events) * (len(events) - 1) // 2 - total_comparisons}")

    if total_comparisons == 0:
        print("[+] No duplicate candidates found after pre-filtering!")
        return []

    current_comparison = 0

    # Now compare events only within same calendar+date groups
    for group_key, group_events in events_by_calendar_date.items():
        if len(group_events) <= 1:
            continue  # No duplicates possible with single event

        print(f"\n[*] Checking group: {group_key} ({len(group_events)} events)")

        for i, event1 in enumerate(group_events):
            if event1['id'] in processed_events:
                continue

            event1_data = {
                'summary': event1.get('summary', ''),
                'description': event1.get('description', ''),
                'start_time': event1.get('start', {}).get('dateTime', event1.get('start', {}).get('date', '')),
                'source_email_subject': f"Calendar Event {event1['id']}",
                'source_email_sender': 'Calendar System',
                'source_email_date': event1.get('created', '')
            }

            # Compare with other events in the same group (same calendar + date)
            for event2 in group_events[i+1:]:
                if event2['id'] in processed_events:
                    continue

                current_comparison += 1
                if current_comparison % 50 == 0:
                    print(f"    Progress: {current_comparison}/{total_comparisons} comparisons...")

                # Create candidate info for comparison
                candidate = {
                    'event_data': {
                        'summary': event2.get('summary', ''),
                        'description': event2.get('description', ''),
                        'start_time': event2.get('start', {}).get('dateTime', event2.get('start', {}).get('date', '')),
                        'calendar_event_id': event2['id']
                    },
                    'source_email': {
                        'id': f"calendar_event_{event2['id']}",
                        'subject': f"Calendar Event {event2['id']}",
                        'sender': 'Calendar System',
                        'date': event2.get('created', '')
                    }
                }

                # Use AI to analyze similarity
                similarity_score, merge_recommendation = smart_merger._analyze_event_similarity(
                    event1_data, candidate, {'subject': 'AI Duplicate Analysis', 'sender': 'System'}
                )

                if similarity_score > 0.7:  # 70% similarity threshold
                    duplicate_info = {
                        'event1': event1,
                        'event2': event2,
                        'similarity_score': similarity_score,
                        'merge_recommendation': merge_recommendation,
                        'action': 'merge' if similarity_score > 0.85 else 'review'
                    }
                    duplicates.append(duplicate_info)

                    print(f"\n[DUPLICATE] Found duplicate events (similarity: {similarity_score:.2f}):")
                    print(f"  Event 1: {event1.get('summary', 'Untitled')[:50]}... ({event1['_calendar_name']})")
                    print(f"  Event 2: {event2.get('summary', 'Untitled')[:50]}... ({event2['_calendar_name']})")
                    print(f"  Recommendation: {duplicate_info['action'].upper()}")
    
    print(f"\n[+] AI Analysis Complete!")
    print(f"[+] Found {len(duplicates)} potential duplicate pairs")
    
    return duplicates

def cleanup_ai_duplicates(service, duplicates):
    """Clean up duplicates using AI recommendations"""
    print(f"\n[*] CLEANING UP AI-DETECTED DUPLICATES")
    print("=" * 60)
    
    auto_merged = 0
    manual_review = 0
    errors = 0
    
    for duplicate_info in duplicates:
        event1 = duplicate_info['event1']
        event2 = duplicate_info['event2']
        similarity = duplicate_info['similarity_score']
        action = duplicate_info['action']
        
        print(f"\n[PROCESSING] {event1.get('summary', 'Untitled')[:40]}...")
        print(f"  Similarity: {similarity:.2f}")
        print(f"  Action: {action.upper()}")
        
        if action == 'merge' and similarity > 0.85:
            # Auto-merge high confidence duplicates
            try:
                # Keep the event with more information (longer description)
                event1_desc_len = len(event1.get('description', ''))
                event2_desc_len = len(event2.get('description', ''))
                
                if event1_desc_len >= event2_desc_len:
                    keep_event = event1
                    delete_event = event2
                else:
                    keep_event = event2
                    delete_event = event1
                
                # Delete the less informative event
                service.events().delete(
                    calendarId=delete_event['_calendar_id'],
                    eventId=delete_event['id']
                ).execute()
                
                print(f"  [MERGED] Deleted duplicate, kept more detailed version")
                auto_merged += 1
                
            except Exception as e:
                print(f"  [ERROR] Failed to merge: {e}")
                errors += 1
                
        else:
            # Flag for manual review
            print(f"  [REVIEW] Similarity {similarity:.2f} requires manual review")
            print(f"    Event 1: {event1.get('summary', '')} ({event1['_calendar_name']})")
            print(f"    Event 2: {event2.get('summary', '')} ({event2['_calendar_name']})")
            manual_review += 1
    
    print(f"\n[*] AI CLEANUP SUMMARY:")
    print(f"    Auto-merged: {auto_merged}")
    print(f"    Manual review needed: {manual_review}")
    print(f"    Errors: {errors}")
    
    return auto_merged, manual_review, errors

def main():
    """Main AI-enhanced duplicate cleanup function"""
    print("[*] AI-ENHANCED DUPLICATE CLEANUP")
    print("=" * 60)
    print("Using Claude AI for intelligent duplicate detection")
    print()
    
    # Authenticate
    service = authenticate()
    print("[+] Authenticated with Google Calendar")
    
    # Get all Mail2Cal events
    events = get_all_mail2cal_events(service)
    
    if not events:
        print("[!] No Mail2Cal events found")
        return
    
    # Find AI duplicates
    duplicates = find_ai_duplicates(events)
    
    if not duplicates:
        print("\n[+] No duplicates detected by AI analysis!")
        return
    
    # Ask for confirmation
    print(f"\n[?] Proceed with AI-guided cleanup? (y/n): ", end="")
    try:
        response = input().lower().strip()
        if response not in ['y', 'yes']:
            print("[!] Cleanup cancelled")
            return
    except:
        print("[!] Cleanup cancelled")
        return
    
    # Clean up duplicates
    auto_merged, manual_review, errors = cleanup_ai_duplicates(service, duplicates)
    
    print(f"\n[+] AI-Enhanced duplicate cleanup completed!")
    if manual_review > 0:
        print(f"[!] {manual_review} potential duplicates need manual review")

if __name__ == "__main__":
    main()