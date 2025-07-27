#!/usr/bin/env python3
"""
Recovery Tool for Deleted Multi-Calendar Events
Identifies and restores events that were incorrectly deleted due to over-aggressive duplicate detection
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mail2cal import Mail2Cal
from core.global_event_cache import GlobalEventCache
from datetime import datetime, timedelta
from typing import List, Dict

def main():
    """Main recovery function"""
    print("[*] Event Recovery Tool - Fixing Deleted Multi-Calendar Events")
    print("=" * 70)
    
    try:
        # Initialize Mail2Cal system
        app = Mail2Cal()
        app.authenticate()
        
        # Get calendar IDs
        calendar_ids = [
            app.config['calendars']['calendar_id_1'],
            app.config['calendars']['calendar_id_2']
        ]
        
        print(f"[*] Checking calendars:")
        print(f"    Calendar 1: {calendar_ids[0]}")
        print(f"    Calendar 2: {calendar_ids[1]}")
        
        # Refresh the global cache to get current state
        print(f"\n[*] Refreshing global event cache...")
        app.global_cache.refresh_from_calendars(app.calendar_service, calendar_ids)
        
        # Find missing events
        print(f"\n[*] Analyzing for missing multi-calendar events...")
        missing_events = app.global_cache.find_missing_multi_calendar_events(calendar_ids)
        
        if not missing_events:
            print(f"[+] No missing multi-calendar events found!")
            return
        
        print(f"\n[!] Found {len(missing_events)} missing events:")
        print("-" * 50)
        
        # Group by date for better display
        events_by_date = {}
        for event in missing_events:
            date = event['date']
            if date not in events_by_date:
                events_by_date[date] = []
            events_by_date[date].append(event)
        
        for date, events in sorted(events_by_date.items()):
            print(f"\n📅 {date}:")
            for event in events:
                source_cal = "Calendar 1" if event['source_calendar_id'] == calendar_ids[0] else "Calendar 2"
                missing_cal = "Calendar 2" if event['missing_calendar_id'] == calendar_ids[1] else "Calendar 1"
                print(f"   • {event['title']}")
                print(f"     Exists in: {source_cal}")
                print(f"     Missing from: {missing_cal}")
        
        # Ask for confirmation
        print(f"\n[?] Restore these missing events? (y/n): ", end="")
        try:
            response = input().lower().strip()
            if response not in ['y', 'yes']:
                print("[!] Recovery cancelled")
                return
        except:
            print("[!] Recovery cancelled")
            return
        
        # Restore missing events
        print(f"\n[*] Restoring missing events...")
        restored_count = 0
        
        for event in missing_events:
            try:
                # Get the original event from the source calendar
                original_event = app.calendar_service.events().get(
                    calendarId=event['source_calendar_id'],
                    eventId=event['original_event_id']
                ).execute()
                
                # Create a copy for the missing calendar
                new_event = {
                    'summary': original_event['summary'],
                    'start': original_event['start'],
                    'end': original_event['end'],
                    'description': original_event.get('description', ''),
                    'location': original_event.get('location', ''),
                    'extendedProperties': {
                        'private': {
                            'mail2cal_restored': 'true',
                            'mail2cal_restored_at': datetime.now().isoformat(),
                            'mail2cal_source_event': event['original_event_id']
                        }
                    }
                }
                
                # Create the event in the missing calendar
                result = app.calendar_service.events().insert(
                    calendarId=event['missing_calendar_id'],
                    body=new_event
                ).execute()
                
                # Add to cache
                app.global_cache.add_event(
                    title=event['title'],
                    date=event['date'],
                    calendar_id=event['missing_calendar_id'],
                    event_id=result['id']
                )
                
                missing_cal_name = "Calendar 1" if event['missing_calendar_id'] == calendar_ids[0] else "Calendar 2"
                print(f"[+] Restored '{event['title']}' ({event['date']}) to {missing_cal_name}")
                restored_count += 1
                
            except Exception as e:
                print(f"[!] Error restoring '{event['title']}' ({event['date']}): {e}")
        
        print(f"\n[+] Recovery completed!")
        print(f"[+] Successfully restored {restored_count} out of {len(missing_events)} events")
        
        if restored_count > 0:
            print(f"\n[*] Global event cache has been updated with restored events")
            print(f"[*] The duplicate detection logic has been fixed to prevent this issue in the future")
        
    except Exception as e:
        print(f"[!] Error during recovery: {e}")
        return 1

if __name__ == "__main__":
    exit(main())