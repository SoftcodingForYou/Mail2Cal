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
from core.token_tracker import TokenTracker
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

def _extract_source_from_description(description: str) -> dict:
    """Extract source email info from event description as fallback"""
    import re

    info = {}

    if not description:
        return info

    # Look for the source information section
    if 'INFORMACIÓN DEL EMAIL FUENTE:' in description:
        # Extract subject
        subject_match = re.search(r'Asunto:\s*(.+?)(?:\n|$)', description)
        if subject_match:
            info['email_subject'] = subject_match.group(1).strip()

        # Extract date
        date_match = re.search(r'Fecha del email:\s*(.+?)(?:\n|$)', description)
        if date_match:
            info['email_date'] = date_match.group(1).strip()

        # Extract sender
        sender_match = re.search(r'Remitente:\s*(.+?)(?:\n|$)', description)
        if sender_match:
            info['email_sender'] = sender_match.group(1).strip()

        # Extract email ID
        id_match = re.search(r'ID del email:\s*(.+?)(?:\n|$)', description)
        if id_match:
            # Use this as the key for the dict
            pass  # We already have it from extended properties

    return info

def find_ai_duplicates(events, smart_merger, event_tracker):
    """Use AI to find semantic duplicates across all events"""
    print("\n[AI] Analyzing events for intelligent duplicates...")
    print("=" * 60)

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

def cleanup_ai_duplicates(service, duplicates, smart_merger, event_tracker, calendar_ids):
    """Clean up duplicates using AI recommendations and proper event merging"""
    print(f"\n[*] CLEANING UP AI-DETECTED DUPLICATES")
    print("=" * 60)

    auto_merged = 0
    manual_review = 0
    errors = 0

    # Build config for merge_events
    config = {
        'calendars': {
            'calendar_id_1': calendar_ids[0] if len(calendar_ids) > 0 else '',
            'calendar_id_2': calendar_ids[1] if len(calendar_ids) > 1 else ''
        }
    }

    for duplicate_info in duplicates:
        event1 = duplicate_info['event1']
        event2 = duplicate_info['event2']
        similarity = duplicate_info['similarity_score']
        action = duplicate_info['action']
        merge_recommendation = duplicate_info.get('merge_recommendation', {})

        print(f"\n[PROCESSING] {event1.get('summary', 'Untitled')[:40]}...")
        print(f"  Similarity: {similarity:.2f}")
        print(f"  Action: {action.upper()}")

        if action == 'merge' and similarity > 0.85:
            # Auto-merge high confidence duplicates using proper merge method
            try:
                # Determine which event to treat as "new" and "existing"
                # Use creation time or default to event1 as existing
                event1_created = event1.get('created', '')
                event2_created = event2.get('created', '')

                if event2_created > event1_created:
                    # event2 is newer
                    new_event = event2
                    existing_event = event1
                else:
                    # event1 is newer or same age
                    new_event = event1
                    existing_event = event2

                # Extract source email info from event metadata
                existing_email_id = existing_event.get('extendedProperties', {}).get('private', {}).get('mail2cal_source_email_id', 'unknown')
                new_email_id = new_event.get('extendedProperties', {}).get('private', {}).get('mail2cal_source_email_id', 'unknown')

                # Look up source email info from event tracker
                existing_email_info = event_tracker.mappings.get(existing_email_id, {})
                new_email_info = event_tracker.mappings.get(new_email_id, {})

                # Fallback: If tracker doesn't have the email info, parse it from the event description
                if not existing_email_info:
                    existing_email_info = _extract_source_from_description(existing_event.get('description', ''))
                if not new_email_info:
                    new_email_info = _extract_source_from_description(new_event.get('description', ''))

                # Build the structure that merge_events expects
                merge_info = {
                    'new_event': {
                        'summary': new_event.get('summary', ''),
                        'description': new_event.get('description', ''),
                        'start_time': new_event.get('start', {}).get('dateTime') or new_event.get('start', {}).get('date', ''),
                        'end_time': new_event.get('end', {}).get('dateTime') or new_event.get('end', {}).get('date', ''),
                        'location': new_event.get('location', ''),
                        'all_day': 'date' in new_event.get('start', {}),
                        'source_email_subject': new_email_info.get('email_subject', 'Unknown'),
                        'source_email_sender': new_email_info.get('email_sender', 'Unknown'),
                        'source_email_date': new_email_info.get('email_date', 'Unknown'),
                        'source_email_id': new_email_id
                    },
                    'existing_event': {
                        'event_data': {
                            'summary': existing_event.get('summary', ''),
                            'description': existing_event.get('description', ''),
                            'start_time': existing_event.get('start', {}).get('dateTime') or existing_event.get('start', {}).get('date', ''),
                            'end_time': existing_event.get('end', {}).get('dateTime') or existing_event.get('end', {}).get('date', ''),
                            'location': existing_event.get('location', ''),
                            'all_day': 'date' in existing_event.get('start', {}),
                            'calendar_event_id': existing_event['id'],
                            'created_at': existing_event.get('created', ''),
                            'mail2cal_merge_count': existing_event.get('extendedProperties', {}).get('private', {}).get('mail2cal_merge_count', '1')
                        },
                        'source_email': {
                            'id': existing_email_id,
                            'subject': existing_email_info.get('email_subject', 'Unknown'),
                            'sender': existing_email_info.get('email_sender', 'Unknown'),
                            'date': existing_email_info.get('email_date', 'Unknown')
                        }
                    },
                    'merge_recommendation': merge_recommendation,
                    'similarity_score': similarity
                }

                # Use the proper merge_events method
                merged_event_id = smart_merger.merge_events(merge_info, service, config)

                if merged_event_id:
                    # Delete the duplicate event (the one we didn't update)
                    try:
                        service.events().delete(
                            calendarId=new_event['_calendar_id'],
                            eventId=new_event['id']
                        ).execute()
                        delete_msg = f"Removed duplicate event ID: {new_event['id'][:20]}..."
                    except HttpError as delete_error:
                        if delete_error.resp.status == 410:
                            # Event already deleted - that's fine, merge succeeded
                            delete_msg = "Duplicate was already deleted (merge OK)"
                        else:
                            # Some other error - re-raise
                            raise

                    print(f"  [MERGED] Successfully combined information from both events")
                    print(f"    Updated event: {existing_event.get('summary', '')[:50]}")
                    print(f"    Source 1: {existing_email_info.get('email_subject', 'Unknown')[:40]}")
                    print(f"    Source 2: {new_email_info.get('email_subject', 'Unknown')[:40]}")
                    print(f"    {delete_msg}")
                    auto_merged += 1
                else:
                    print(f"  [ERROR] Merge failed, events not combined")
                    errors += 1

            except Exception as e:
                print(f"  [ERROR] Failed to merge: {e}")
                import traceback
                traceback.print_exc()
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

    # Get calendar IDs
    calendar_id_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')
    calendar_id_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')
    calendar_ids = [calendar_id_1, calendar_id_2]

    # Initialize AI components (create once, use for both detection and merging)
    ai_config = {
        'provider': 'anthropic',
        'api_key_env_var': 'ANTHROPIC_API_KEY',
        'model': get_secure_credential('AI_MODEL'),
        'model_cheap': get_secure_credential('AI_MODEL_CHEAP')
    }
    event_tracker = EventTracker('event_mappings.json')
    token_tracker = TokenTracker()
    smart_merger = SmartEventMerger(ai_config, event_tracker, token_tracker)

    # Get all Mail2Cal events
    events = get_all_mail2cal_events(service)

    if not events:
        print("[!] No Mail2Cal events found")
        return

    # Find AI duplicates (pass smart_merger to use the same instance)
    duplicates = find_ai_duplicates(events, smart_merger, event_tracker)

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

    # Clean up duplicates using proper merge method
    auto_merged, manual_review, errors = cleanup_ai_duplicates(
        service, duplicates, smart_merger, event_tracker, calendar_ids
    )

    print(f"\n[+] AI-Enhanced duplicate cleanup completed!")
    if manual_review > 0:
        print(f"[!] {manual_review} potential duplicates need manual review")

    # Display AI token usage summary
    print("\n" + "=" * 60)
    token_tracker.print_summary()

if __name__ == "__main__":
    main()