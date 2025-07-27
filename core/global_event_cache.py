#!/usr/bin/env python3
"""
Global Event Cache for Mail2Cal
Provides intelligent duplicate prevention across all emails and calendar sources
"""

import json
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import re


@dataclass
class CachedEvent:
    """Represents a cached event with all relevant deduplication data"""
    title: str
    date: str  # YYYY-MM-DD format
    calendar_id: str
    event_id: str
    source_email_id: Optional[str]
    normalized_title: str
    keywords: Set[str]
    created_at: str
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['keywords'] = list(data['keywords'])  # Convert set to list for JSON
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CachedEvent':
        data['keywords'] = set(data['keywords'])  # Convert list back to set
        return cls(**data)


class GlobalEventCache:
    """
    Manages a global cache of all events across calendars and emails
    Provides intelligent duplicate detection and prevention
    """
    
    def __init__(self, cache_file: str = "global_event_cache.json"):
        self.cache_file = cache_file
        self.events: Dict[str, CachedEvent] = {}
        self.load_cache()
    
    def load_cache(self):
        """Load cached events from file"""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.events = {
                    event_id: CachedEvent.from_dict(event_data)
                    for event_id, event_data in data.items()
                }
        except (FileNotFoundError, json.JSONDecodeError):
            self.events = {}
    
    def save_cache(self):
        """Save cached events to file"""
        try:
            data = {
                event_id: event.to_dict()
                for event_id, event in self.events.items()
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Warning: Could not save event cache: {e}")
    
    def normalize_title(self, title: str) -> str:
        """
        Normalize event title for better duplicate detection
        """
        # Convert to lowercase and remove extra whitespace
        normalized = re.sub(r'\s+', ' ', title.lower().strip())
        
        # Remove common variations and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # Normalize common school event terms
        replacements = {
            'dia de la familia': 'familia',
            'celebracion de': 'celebracion',
            'actividad de': 'actividad',
            'reunion de': 'reunion',
            'feriado nacional': 'feriado',
            'virgen del carmen': 'feriado',
            'semana de las ciencias': 'ciencias',
            'laboratorio creativo': 'laboratorio',
        }
        
        for original, replacement in replacements.items():
            if original in normalized:
                normalized = replacement
                break
        
        return normalized
    
    def extract_keywords(self, title: str) -> Set[str]:
        """Extract key identifying words from event title"""
        # Important school event keywords
        important_keywords = {
            'feriado', 'vacaciones', 'suspension', 'familia', 'reunion',
            'evaluacion', 'presentacion', 'entrevista', 'celebracion',
            'actividad', 'laboratorio', 'ciencias', 'after', 'school',
            'academias', 'inscripcion', 'inicio', 'termino'
        }
        
        words = set(re.findall(r'\w+', title.lower()))
        return words.intersection(important_keywords)
    
    def add_event(self, title: str, date: str, calendar_id: str, 
                  event_id: str, source_email_id: Optional[str] = None) -> bool:
        """
        Add event to cache, returns False if duplicate detected
        """
        normalized_title = self.normalize_title(title)
        keywords = self.extract_keywords(title)
        
        # Check for duplicates before adding
        if self.is_duplicate(title, date, calendar_id):
            return False
        
        cached_event = CachedEvent(
            title=title,
            date=date,
            calendar_id=calendar_id,
            event_id=event_id,
            source_email_id=source_email_id,
            normalized_title=normalized_title,
            keywords=keywords,
            created_at=datetime.now().isoformat()
        )
        
        self.events[event_id] = cached_event
        self.save_cache()
        return True
    
    def is_duplicate(self, title: str, date: str, calendar_id: str) -> bool:
        """
        Intelligent duplicate detection - Fixed to handle legitimate multi-calendar events
        """
        normalized_title = self.normalize_title(title)
        keywords = self.extract_keywords(title)
        
        for existing_event in self.events.values():
            # FIXED: Only check for duplicates within the SAME calendar
            # Multi-calendar events are legitimate and should not be considered duplicates
            # unless they are truly identical events created from the same source
            if existing_event.calendar_id != calendar_id:
                # Skip cross-calendar duplicate checking - events can legitimately exist in both calendars
                continue
            
            # Check date match (same day)
            if existing_event.date != date:
                continue
            
            # Method 1: Exact normalized title match
            if existing_event.normalized_title == normalized_title:
                return True
            
            # Method 2: Keyword overlap for same date (reduced threshold for same calendar)
            if len(keywords.intersection(existing_event.keywords)) >= 2:
                return True
            
            # Method 3: High string similarity (85%+)
            similarity = self._calculate_similarity(
                normalized_title, existing_event.normalized_title
            )
            if similarity >= 0.85:
                return True
            
            # Method 4: Special school event patterns
            if self._are_same_school_event(title, existing_event.title, date):
                return True
        
        return False
    
    def _is_global_event(self, keywords: Set[str]) -> bool:
        """Check if event should apply to all calendars"""
        # School-wide events that legitimately appear in multiple calendars
        global_keywords = {
            'feriado', 'vacaciones', 'suspension', 'familia',
            'after', 'school', 'academias', 'reunion', 'evaluacion',
            'actividad', 'celebracion', 'laboratorio', 'ciencias'
        }
        return bool(keywords.intersection(global_keywords))
    
    def should_exist_in_both_calendars(self, title: str) -> bool:
        """
        Check if an event should legitimately exist in both calendars
        Used to identify events that were incorrectly deleted due to over-aggressive duplicate detection
        """
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
    
    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate string similarity using word overlap"""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _are_same_school_event(self, title1: str, title2: str, date: str) -> bool:
        """Check for same school event with different naming"""
        t1, t2 = title1.lower(), title2.lower()
        
        # Common event patterns that should be unique per date
        patterns = [
            ('feriado', 'holiday'),
            ('dia de la familia', 'family day'),
            ('reunion', 'meeting'),
            ('evaluacion', 'evaluation'),
            ('after school', 'afterschool'),
            ('semana de', 'week of'),
        ]
        
        for pattern1, pattern2 in patterns:
            if ((pattern1 in t1 or pattern2 in t1) and 
                (pattern1 in t2 or pattern2 in t2)):
                return True
        
        return False
    
    def refresh_from_calendars(self, calendar_service, calendar_ids: List[str]):
        """
        Refresh cache from actual calendar events
        (Run this periodically or when starting processing)
        """
        print("[*] Refreshing global event cache from calendars...")
        
        # Clear existing cache
        self.events.clear()
        
        for calendar_id in calendar_ids:
            try:
                # Get events from last 3 months to 6 months ahead
                time_min = (datetime.now() - timedelta(days=90)).isoformat() + 'Z'
                time_max = (datetime.now() + timedelta(days=180)).isoformat() + 'Z'
                
                result = calendar_service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=200,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = result.get('items', [])
                
                for event in events:
                    title = event.get('summary', '')
                    if not title:
                        continue
                    
                    # Extract date
                    start = event.get('start', {})
                    if 'date' in start:
                        date = start['date']
                    elif 'dateTime' in start:
                        date = start['dateTime'][:10]
                    else:
                        continue
                    
                    # Add to cache (force add, don't check duplicates during refresh)
                    normalized_title = self.normalize_title(title)
                    keywords = self.extract_keywords(title)
                    
                    cached_event = CachedEvent(
                        title=title,
                        date=date,
                        calendar_id=calendar_id,
                        event_id=event['id'],
                        source_email_id=None,
                        normalized_title=normalized_title,
                        keywords=keywords,
                        created_at=event.get('created', datetime.now().isoformat())
                    )
                    
                    self.events[event['id']] = cached_event
                
                print(f"[+] Cached {len(events)} events from calendar {calendar_id}")
                
            except Exception as e:
                print(f"[!] Warning: Could not refresh cache from calendar {calendar_id}: {e}")
        
        self.save_cache()
        print(f"[+] Global event cache refreshed with {len(self.events)} total events")
    
    def find_missing_multi_calendar_events(self, calendar_ids: List[str]) -> List[Dict]:
        """
        Find events that should exist in both calendars but are missing from one
        Returns list of events that need to be restored
        """
        missing_events = []
        
        # Group events by date and normalized title
        events_by_key = {}
        for event in self.events.values():
            if event.calendar_id not in calendar_ids:
                continue
                
            key = f"{event.date}_{event.normalized_title}"
            if key not in events_by_key:
                events_by_key[key] = []
            events_by_key[key].append(event)
        
        # Find events that should be in both calendars but are only in one
        for key, events in events_by_key.items():
            if len(events) == 1:  # Only in one calendar
                event = events[0]
                if self.should_exist_in_both_calendars(event.title):
                    # This event should exist in both calendars but is missing from one
                    missing_calendar_ids = [cid for cid in calendar_ids if cid != event.calendar_id]
                    for missing_calendar_id in missing_calendar_ids:
                        missing_events.append({
                            'title': event.title,
                            'date': event.date,
                            'source_calendar_id': event.calendar_id,
                            'missing_calendar_id': missing_calendar_id,
                            'original_event_id': event.event_id
                        })
        
        return missing_events
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache"""
        total_events = len(self.events)
        
        # Count by calendar
        calendar_counts = {}
        for event in self.events.values():
            calendar_counts[event.calendar_id] = calendar_counts.get(event.calendar_id, 0) + 1
        
        # Count by date range
        today = datetime.now().date()
        future_events = sum(1 for e in self.events.values() 
                          if datetime.fromisoformat(e.date).date() >= today)
        
        return {
            'total_events': total_events,
            'calendar_distribution': calendar_counts,
            'future_events': future_events,
            'cache_file': self.cache_file
        }


if __name__ == "__main__":
    # Test the cache system
    cache = GlobalEventCache("test_cache.json")
    
    # Test duplicate detection
    print("Testing duplicate detection...")
    
    # Add first event
    result1 = cache.add_event("Feriado Nacional", "2025-07-16", "cal1", "event1")
    print(f"Added 'Feriado Nacional': {result1}")
    
    # Try to add duplicate
    result2 = cache.add_event("Feriado Virgen del Carmen", "2025-07-16", "cal1", "event2")
    print(f"Added 'Feriado Virgen del Carmen' (should be False): {result2}")
    
    # Add different event
    result3 = cache.add_event("Reunión de Apoderados", "2025-07-17", "cal1", "event3")
    print(f"Added 'Reunión de Apoderados': {result3}")
    
    print(f"\nCache stats: {cache.get_cache_stats()}")