#!/usr/bin/env python3
"""
Simple Event Analysis Tool
Analyzes the global cache to identify missing multi-calendar events without requiring full authentication
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List

def load_cache(cache_file: str = "global_event_cache.json") -> Dict:
    """Load the global event cache"""
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[!] Error loading cache: {e}")
        return {}

def should_exist_in_both_calendars(title: str) -> bool:
    """Check if an event should legitimately exist in both calendars"""
    title_lower = title.lower()
    
    # School-wide activities that should appear in both calendars
    both_calendar_patterns = [
        'dia de la familia', 'family day',
        'after school', 'academias', 'talleres',
        'juegos recreativos', 'recreational games',
        'juegos de rincones', 'corner games', 
        'juegos de motricidad', 'motor skills',
        'actividad fisica', 'physical activity',
        'semana de las ciencias', 'science week',
        'reunion de apoderados', 'parent meeting',
        'vacunacion', 'vaccination',
        'evaluacion', 'evaluation',
        'entrega de fotografia', 'photo delivery',
        'campana de', 'campaign'
    ]
    
    return any(pattern in title_lower for pattern in both_calendar_patterns)

def normalize_title(title: str) -> str:
    """Normalize event title for comparison"""
    import re
    normalized = re.sub(r'\s+', ' ', title.lower().strip())
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return normalized

def analyze_missing_events(cache_data: Dict) -> List[Dict]:
    """Analyze cache for missing multi-calendar events"""
    # Group events by date and normalized title
    events_by_key = {}
    calendar_ids = set()
    
    for event_id, event_data in cache_data.items():
        calendar_id = event_data['calendar_id']
        calendar_ids.add(calendar_id)
        
        normalized_title = normalize_title(event_data['title'])
        date = event_data['date']
        key = f"{date}_{normalized_title}"
        
        if key not in events_by_key:
            events_by_key[key] = []
        events_by_key[key].append(event_data)
    
    calendar_ids = list(calendar_ids)
    print(f"[*] Found {len(calendar_ids)} calendars in cache:")
    for i, cal_id in enumerate(calendar_ids):
        print(f"    Calendar {i+1}: {cal_id}")
    
    missing_events = []
    
    # Find events that should be in both calendars but are only in one
    for key, events in events_by_key.items():
        if len(events) == 1:  # Only in one calendar
            event = events[0]
            if should_exist_in_both_calendars(event['title']):
                # This event should exist in both calendars but is missing from one
                missing_calendar_ids = [cid for cid in calendar_ids if cid != event['calendar_id']]
                for missing_calendar_id in missing_calendar_ids:
                    missing_events.append({
                        'title': event['title'],
                        'date': event['date'],
                        'source_calendar_id': event['calendar_id'],
                        'missing_calendar_id': missing_calendar_id,
                        'original_event_id': event['event_id']
                    })
    
    return missing_events

def main():
    """Main analysis function"""
    print("[*] Event Analysis Tool - Identifying Missing Multi-Calendar Events")
    print("=" * 70)
    
    # Change to the correct directory
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(script_dir)
    
    # Load the cache
    cache_data = load_cache()
    
    if not cache_data:
        print("[!] No cache data found")
        return 1
    
    print(f"[*] Loaded {len(cache_data)} events from cache")
    
    # Analyze for missing events
    missing_events = analyze_missing_events(cache_data)
    
    if not missing_events:
        print("[+] No missing multi-calendar events found!")
        return 0
    
    print(f"\n[!] Found {len(missing_events)} missing events:")
    print("-" * 50)
    
    # Group by date for better display
    events_by_date = {}
    for event in missing_events:
        date = event['date']
        if date not in events_by_date:
            events_by_date[date] = []
        events_by_date[date].append(event)
    
    # Focus on the problematic date range (July 28 - August 1)
    target_dates = ['2025-07-28', '2025-07-29', '2025-07-30', '2025-07-31', '2025-08-01']
    
    print(f"\nFOCUS: Events missing from July 28 - August 1, 2025:")
    print("=" * 50)
    
    found_target_events = False
    for date in target_dates:
        if date in events_by_date:
            found_target_events = True
            print(f"\n{date}:")
            for event in events_by_date[date]:
                cal1_id = "1e8f6e5f6ea0e6096efce8714aba2fc2450e988d44ec14c9265da1f9a10225e6@group.calendar.google.com"
                source_cal = "Calendar 1" if event['source_calendar_id'] == cal1_id else "Calendar 2"
                missing_cal = "Calendar 2" if event['missing_calendar_id'] != cal1_id else "Calendar 1"
                print(f"   * {event['title']}")
                print(f"     Exists in: {source_cal}")
                print(f"     Missing from: {missing_cal}")
    
    if found_target_events:
        print(f"\nSOLUTION:")
        print("These events were likely deleted due to over-aggressive duplicate detection.")
        print("The GlobalEventCache.is_duplicate() method has been fixed to prevent cross-calendar")
        print("duplicate removal for legitimate multi-calendar events.")
        print(f"\nTo restore these events, run:")
        print("  python run_mail2cal.py --recover-events")
        print("  (or use option 9 in interactive mode)")
    else:
        print(f"\nNo missing events found in the target date range (July 28 - August 1)")
    
    # Show all missing events if any
    if events_by_date:
        print(f"\nALL MISSING EVENTS:")
        print("-" * 30)
        for date, events in sorted(events_by_date.items()):
            print(f"\n{date}: {len(events)} missing events")
            for event in events:
                print(f"   * {event['title']}")
    
    return 0

if __name__ == "__main__":
    exit(main())