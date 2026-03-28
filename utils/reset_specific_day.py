#!/usr/bin/env python3
"""
Reset Day's Events
Deletes Google Calendar events created at a specific day and clears their
mappings.
"""

import sys
import os
import json
import pickle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.config import get_calendar_ids

TODAY = "2026-03-27"
MAPPINGS_FILE = "event_mappings.json"

# Event IDs from the log that may not appear in the JSON (created but not tracked)
EXTRA_IDS_FROM_LOG = {}


def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        raise SystemExit("[!] No valid credentials. Run the main system first.")
    return build('calendar', 'v3', credentials=creds)


def collect_today_event_ids(mappings):
    """Return (today_email_ids, unique_cal_event_ids) from today's entries."""
    today_email_ids = []
    event_ids = set()
    for email_id, mapping in mappings.items():
        if mapping.get('processed_at', '').startswith(TODAY):
            today_email_ids.append(email_id)
            for ce in mapping.get('calendar_events', []):
                eid = ce.get('calendar_event_id')
                if eid:
                    event_ids.add(eid)
    event_ids |= EXTRA_IDS_FROM_LOG
    return today_email_ids, event_ids


def delete_event(service, calendar_id, event_id, cal_name):
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"  [+] Deleted from {cal_name}: {event_id}")
        return True
    except HttpError as e:
        if e.resp.status == 404 or e.resp.status == 410:
            return False  # Not in this calendar — silent skip
        print(f"  [!] Error deleting {event_id} from {cal_name}: {e}")
        return False


def main():
    cal_id_1, cal_id_2 = get_calendar_ids()

    with open(MAPPINGS_FILE, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    today_email_ids, event_ids = collect_today_event_ids(mappings)

    print(f"[*] Today's email entries to remove: {len(today_email_ids)}")
    print(f"[*] Unique calendar event IDs to delete: {len(event_ids)}")
    print()
    for eid in sorted(event_ids):
        print(f"  {eid}")
    print()

    confirm = input("[?] Proceed? This will delete these events from Google Calendar. (y/n): ").strip().lower()
    if confirm != 'y':
        print("[*] Aborted.")
        return

    service = authenticate()
    print("\n[*] Deleting calendar events...")
    deleted = 0
    for event_id in event_ids:
        found = delete_event(service, cal_id_1, event_id, "Calendar 1")
        if not found:
            delete_event(service, cal_id_2, event_id, "Calendar 2")
        deleted += 1

    print(f"\n[*] Removing {len(today_email_ids)} entries from {MAPPINGS_FILE}...")
    for email_id in today_email_ids:
        del mappings[email_id]
        print(f"  [-] Removed: {email_id}")

    with open(MAPPINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Done. {len(event_ids)} event IDs deleted, {len(today_email_ids)} mappings cleared.")
    print("[*] Re-run option 6 to reprocess today's emails cleanly.")


if __name__ == "__main__":
    main()
