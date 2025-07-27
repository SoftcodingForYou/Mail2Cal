"""
Event tracking system for managing email-to-calendar event mappings
"""

import json
import hashlib
from typing import Dict, List, Optional, Set
from datetime import datetime
import os


class EventTracker:
    def __init__(self, storage_file: str = "event_mappings.json"):
        self.storage_file = storage_file
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """Load existing email-to-event mappings from storage"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading mappings: {e}")
                return {}
        return {}
    
    def _save_mappings(self):
        """Save mappings to storage file"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.mappings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving mappings: {e}")
    
    def generate_email_hash(self, email: Dict) -> str:
        """Generate a unique hash for email content to detect changes"""
        content = f"{email['subject']}{email['body']}{email['date']}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def generate_event_signature(self, event: Dict) -> str:
        """Generate a signature for an event to detect duplicates"""
        # Use title, date, and description snippet for signature
        title = event.get('summary', '')
        start_time = event.get('start_time', '')
        desc_snippet = (event.get('description', '') or '')[:100]
        
        signature_content = f"{title}{start_time}{desc_snippet}"
        return hashlib.md5(signature_content.encode('utf-8')).hexdigest()
    
    def track_email_processing(self, email: Dict, events: List[Dict], calendar_event_ids: List[str]):
        """Track the relationship between an email and its generated calendar events"""
        email_id = email['id']
        email_hash = self.generate_email_hash(email)
        
        self.mappings[email_id] = {
            'email_hash': email_hash,
            'email_subject': email['subject'],
            'email_date': email['date'],
            'email_sender': email['sender'],
            'processed_at': datetime.now().isoformat(),
            'calendar_events': [],
            'event_signatures': []
        }
        
        # Track each generated event
        for i, (event, cal_event_id) in enumerate(zip(events, calendar_event_ids)):
            event_signature = self.generate_event_signature(event)
            
            self.mappings[email_id]['calendar_events'].append({
                'calendar_event_id': cal_event_id,
                'event_signature': event_signature,
                'summary': event.get('summary', ''),
                'start_time': event.get('start_time').isoformat() if event.get('start_time') else None,
                'created_at': datetime.now().isoformat()
            })
            
            self.mappings[email_id]['event_signatures'].append(event_signature)
        
        self._save_mappings()
    
    def is_email_processed(self, email: Dict) -> bool:
        """Check if an email has been processed before"""
        email_id = email['id']
        return email_id in self.mappings
    
    def has_email_changed(self, email: Dict) -> bool:
        """Check if an email's content has changed since last processing"""
        email_id = email['id']
        if email_id not in self.mappings:
            return True  # New email
        
        current_hash = self.generate_email_hash(email)
        stored_hash = self.mappings[email_id]['email_hash']
        
        return current_hash != stored_hash
    
    def events_still_exist(self, email: Dict, calendar_service, calendar_ids: List[str]) -> bool:
        """Check if the tracked events for an email still exist in the calendars"""
        email_id = email['id']
        if email_id not in self.mappings:
            return False
        
        tracked_events = self.mappings[email_id]['calendar_events']
        if not tracked_events:
            return False
        
        # Check if at least one tracked event still exists
        for event_info in tracked_events:
            event_id = event_info['calendar_event_id']
            
            # Try to find this event in any of the calendars
            for calendar_id in calendar_ids:
                try:
                    calendar_service.events().get(
                        calendarId=calendar_id,
                        eventId=event_id
                    ).execute()
                    # If we get here, the event exists
                    return True
                except:
                    # Event doesn't exist in this calendar, try next
                    continue
        
        # None of the tracked events exist
        print(f"[!] Tracked events for email '{email['subject'][:40]}...' no longer exist in calendars")
        return False
    
    def get_existing_calendar_events(self, email: Dict) -> List[str]:
        """Get list of calendar event IDs for a given email"""
        email_id = email['id']
        if email_id not in self.mappings:
            return []
        
        return [
            event['calendar_event_id'] 
            for event in self.mappings[email_id]['calendar_events']
        ]
    
    def find_similar_events(self, new_events: List[Dict]) -> Dict[str, str]:
        """Find existing calendar events that are similar to new events"""
        similar_events = {}
        
        for new_event in new_events:
            new_signature = self.generate_event_signature(new_event)
            
            # Search through all existing mappings
            for email_id, mapping in self.mappings.items():
                for stored_event in mapping['calendar_events']:
                    stored_signature = stored_event['event_signature']
                    
                    # Check for exact signature match
                    if new_signature == stored_signature:
                        similar_events[new_signature] = stored_event['calendar_event_id']
                        break
                    
                    # Check for similar events (same title and date)
                    if self._events_are_similar(new_event, stored_event):
                        similar_events[new_signature] = stored_event['calendar_event_id']
                        break
        
        return similar_events
    
    def _events_are_similar(self, new_event: Dict, stored_event: Dict) -> bool:
        """Check if two events are similar enough to be considered the same"""
        # Compare titles (case-insensitive, partial match)
        new_title = (new_event.get('summary', '') or '').lower().strip()
        stored_title = (stored_event.get('summary', '') or '').lower().strip()
        
        if not new_title or not stored_title:
            return False
        
        # Check for exact date match first (very important for school events)
        new_start = new_event.get('start_time')
        stored_start = stored_event.get('start_time')
        
        date_match = False
        if new_start and stored_start:
            # Convert to date strings for comparison
            new_date = str(new_start)[:10] if isinstance(new_start, str) else str(new_start.date())
            stored_date = stored_start[:10] if stored_start else None
            date_match = (new_date == stored_date)
        
        # ENHANCED: Check for common school event keywords that should be unique per date
        school_unique_keywords = [
            'feriado', 'holiday', 'vacacion', 'suspension', 'no hay clases',
            'dia de la familia', 'reunion apoderados', 'entrevista', 'evaluacion',
            'semana de', 'actividad laboratorio', 'visita al', 'celebracion de'
        ]
        
        # If it's a school-specific event and dates match, it's very likely a duplicate
        for keyword in school_unique_keywords:
            if keyword in new_title and keyword in stored_title and date_match:
                return True
        
        # Check exact title match for same date (very strong indicator)
        if date_match and new_title == stored_title:
            return True
        
        # Calculate title similarity
        title_similarity = self._calculate_string_similarity(new_title, stored_title)
        
        if date_match:
            # Same date events - lower threshold for title similarity
            return title_similarity > 0.4  # 40% similarity if same date (more aggressive)
        else:
            # Different dates - higher threshold
            return title_similarity > 0.85  # 85% similarity for different dates
        
        return False
    
    def _calculate_string_similarity(self, s1: str, s2: str) -> float:
        """Calculate simple string similarity (Jaccard similarity on words)"""
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def mark_events_for_deletion(self, email_ids: Set[str]) -> List[str]:
        """Mark events for deletion when their source emails are no longer relevant"""
        events_to_delete = []
        
        for email_id in email_ids:
            if email_id in self.mappings:
                for event in self.mappings[email_id]['calendar_events']:
                    events_to_delete.append(event['calendar_event_id'])
                
                # Remove from mappings
                del self.mappings[email_id]
        
        self._save_mappings()
        return events_to_delete
    
    def update_event_mapping(self, email: Dict, old_calendar_event_id: str, new_calendar_event_id: str, new_event: Dict):
        """Update mapping when an event is updated"""
        email_id = email['id']
        if email_id not in self.mappings:
            return
        
        # Find and update the specific event
        for event in self.mappings[email_id]['calendar_events']:
            if event['calendar_event_id'] == old_calendar_event_id:
                event['calendar_event_id'] = new_calendar_event_id
                event['event_signature'] = self.generate_event_signature(new_event)
                event['summary'] = new_event.get('summary', '')
                event['start_time'] = new_event.get('start_time').isoformat() if new_event.get('start_time') else None
                event['updated_at'] = datetime.now().isoformat()
                break
        
        # Update email hash to reflect the change
        self.mappings[email_id]['email_hash'] = self.generate_email_hash(email)
        self.mappings[email_id]['last_updated'] = datetime.now().isoformat()
        
        self._save_mappings()
    
    def get_processing_statistics(self) -> Dict:
        """Get statistics about processed emails and events"""
        total_emails = len(self.mappings)
        total_events = sum(
            len(mapping['calendar_events']) 
            for mapping in self.mappings.values()
        )
        
        recent_emails = sum(
            1 for mapping in self.mappings.values()
            if datetime.fromisoformat(mapping['processed_at']) > datetime.now().replace(day=1)
        )
        
        return {
            'total_emails_processed': total_emails,
            'total_events_created': total_events,
            'emails_this_month': recent_emails,
            'average_events_per_email': total_events / total_emails if total_emails > 0 else 0
        }
    
    def cleanup_orphaned_mappings(self, existing_email_ids: Set[str]):
        """Remove mappings for emails that no longer exist"""
        orphaned_email_ids = set(self.mappings.keys()) - existing_email_ids
        
        if orphaned_email_ids:
            print(f"Cleaning up {len(orphaned_email_ids)} orphaned email mappings")
            events_to_delete = self.mark_events_for_deletion(orphaned_email_ids)
            return events_to_delete
        
        return []