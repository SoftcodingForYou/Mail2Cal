"""
AI-powered smart event merger for detecting and merging duplicate events across emails
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import anthropic
import os
from auth.secure_credentials import get_secure_credential


class SmartEventMerger:
    """Detects and merges duplicate events from different emails using AI analysis"""
    
    def __init__(self, ai_config: Dict, event_tracker):
        self.ai_config = ai_config
        self.event_tracker = event_tracker
        self.client = self._initialize_ai_client()
    
    def _initialize_ai_client(self):
        """Initialize AI client for semantic analysis"""
        provider = self.ai_config['provider']
        
        # Use secure credentials system like other components
        try:
            api_key = get_secure_credential('ANTHROPIC_API_KEY')
        except Exception as e:
            raise ValueError(f"API key not found in secure credentials: {e}")
        
        if provider == "anthropic":
            return anthropic.Anthropic(api_key=api_key)
        else:
            # For now, focus on Anthropic - can add OpenAI later
            raise ValueError(f"SmartEventMerger currently only supports Anthropic")
    
    def find_potential_duplicates(self, new_events: List[Dict], source_email: Dict) -> List[Dict]:
        """Find existing events that might be duplicates of new events"""
        potential_duplicates = []
        
        for new_event in new_events:
            # Get basic candidate events (same date range)
            candidates = self._get_candidate_events(new_event)
            
            for candidate in candidates:
                # Use AI to determine if they're duplicates
                similarity_score, merge_recommendation = self._analyze_event_similarity(
                    new_event, candidate, source_email
                )
                
                if similarity_score > 0.7:  # 70% similarity threshold
                    potential_duplicates.append({
                        'new_event': new_event,
                        'existing_event': candidate,
                        'similarity_score': similarity_score,
                        'merge_recommendation': merge_recommendation,
                        'action': 'merge' if similarity_score > 0.85 else 'review'
                    })
        
        return potential_duplicates
    
    def _get_candidate_events(self, new_event: Dict) -> List[Dict]:
        """Get existing events that could potentially be duplicates within a 2-week window from today"""
        from datetime import datetime, timedelta

        candidates = []
        new_date = new_event.get('start_time')

        if not new_date:
            return candidates

        # Convert to datetime for range comparison
        if isinstance(new_date, str):
            try:
                new_datetime = datetime.fromisoformat(new_date.replace('Z', '+00:00'))
            except:
                new_datetime = datetime.strptime(new_date[:10], '%Y-%m-%d')
        else:
            new_datetime = new_date

        # Define search window: TODAY to 2 weeks from now
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        two_weeks_future = today + timedelta(weeks=2)

        # Search through existing mappings within the time window
        for email_id, mapping in self.event_tracker.mappings.items():
            for stored_event in mapping['calendar_events']:
                stored_date_str = stored_event.get('start_time', '')

                if not stored_date_str:
                    continue

                try:
                    # Parse stored event date
                    if 'T' in stored_date_str:
                        stored_datetime = datetime.fromisoformat(stored_date_str.replace('Z', '+00:00'))
                    else:
                        stored_datetime = datetime.strptime(stored_date_str[:10], '%Y-%m-%d')

                    # Check if within our 2-week window from today
                    if today <= stored_datetime <= two_weeks_future:
                        candidates.append({
                            'event_data': stored_event,
                            'source_email': {
                                'id': email_id,
                                'subject': mapping.get('email_subject', ''),
                                'sender': mapping.get('email_sender', ''),
                                'date': mapping.get('email_date', '')
                            }
                        })

                except (ValueError, TypeError):
                    # Skip events with invalid date formats
                    continue

        return candidates
    
    def _analyze_event_similarity(self, new_event: Dict, candidate: Dict, source_email: Dict) -> Tuple[float, Dict]:
        """Use AI to analyze if two events are duplicates and how to merge them"""
        
        prompt = f"""Analyze these two school events to determine if they represent the same real-world event:

EVENT 1 (NEW):
Title: {new_event.get('summary', 'No title')}
Date/Time: {new_event.get('start_time', 'No date')}
Description: {new_event.get('description', 'No description')}
Source Email: {source_email.get('subject', '')} from {source_email.get('sender', '')}

EVENT 2 (EXISTING):
Title: {candidate['event_data'].get('summary', 'No title')}
Date/Time: {candidate['event_data'].get('start_time', 'No date')}
Source Email: {candidate['source_email'].get('subject', '')} from {candidate['source_email'].get('sender', '')}

Consider:
1. Are they the same real-world event? (same activity, same date, same context)
2. Do they have complementary information that should be merged?
3. Is one more detailed/complete than the other?

Respond with JSON only:
{{
    "is_duplicate": true/false,
    "similarity_score": 0.0-1.0,
    "reasoning": "explanation",
    "merge_strategy": {{
        "keep_title": "event1" or "event2" or "combine",
        "keep_description": "event1" or "event2" or "combine",
        "combine_notes": true/false,
        "preferred_time": "event1" or "event2" or "most_specific"
    }}
}}"""

        try:
            message = self.client.messages.create(
                model=self.ai_config['model'],
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            response_text = message.content[0].text.strip()
            
            # Parse JSON response
            try:
                analysis = json.loads(response_text)
                similarity_score = analysis.get('similarity_score', 0.0)
                return similarity_score, analysis
            except json.JSONDecodeError:
                print(f"[!] AI response not valid JSON: {response_text[:100]}...")
                return 0.0, {}
                
        except Exception as e:
            print(f"[!] Error in AI similarity analysis: {e}")
            return 0.0, {}
    
    def merge_events(self, duplicate_info: Dict, calendar_service, config: Dict) -> Optional[str]:
        """Merge two duplicate events into one comprehensive event"""
        new_event = duplicate_info['new_event']
        existing_info = duplicate_info['existing_event']
        merge_recommendation = duplicate_info['merge_recommendation']
        
        if not merge_recommendation:
            return None
        
        # Create merged event data
        merged_event = self._create_merged_event(new_event, existing_info, merge_recommendation)
        
        # Update the existing calendar event
        try:
            existing_event_id = existing_info['event_data']['calendar_event_id']
            calendar_id = self._get_calendar_id_for_event(existing_event_id, calendar_service, config)
            
            if calendar_id:
                # Update the existing event in Google Calendar
                updated_event = calendar_service.events().update(
                    calendarId=calendar_id,
                    eventId=existing_event_id,
                    body=merged_event
                ).execute()
                
                print(f"[+] Merged events: {merged_event['summary'][:50]}...")
                print(f"    Combined information from both sources")
                
                # Update our tracking system
                self._update_event_tracking(existing_info, new_event, merged_event)
                
                return existing_event_id
            
        except Exception as e:
            print(f"[!] Error merging events: {e}")
            return None
    
    def _create_merged_event(self, new_event: Dict, existing_info: Dict, merge_strategy: Dict) -> Dict:
        """Create a merged event with combined information"""
        existing_event = existing_info['event_data']
        
        # Start with existing event structure
        merged = {
            'summary': self._merge_titles(new_event, existing_event, merge_strategy),
            'description': self._merge_descriptions(new_event, existing_event, existing_info, merge_strategy),
            'start': new_event.get('start', {}),
            'end': new_event.get('end', {}),
            'location': new_event.get('location', existing_event.get('location', '')),
            'extendedProperties': {
                'private': {
                    'mail2cal_created_at': existing_event.get('created_at', ''),
                    'mail2cal_updated_at': datetime.now().isoformat(),
                    'mail2cal_merged_from': f"emails:{existing_info['source_email']['id']},new_source",
                    'mail2cal_merge_count': str(int(existing_event.get('mail2cal_merge_count', '1')) + 1)
                }
            }
        }
        
        return merged
    
    def _merge_titles(self, new_event: Dict, existing_event: Dict, merge_strategy: Dict) -> str:
        """Merge event titles based on strategy"""
        new_title = new_event.get('summary', '')
        existing_title = existing_event.get('summary', '')
        
        strategy = merge_strategy.get('keep_title', 'event2')  # Default to existing
        
        if strategy == 'event1':
            return new_title
        elif strategy == 'event2':
            return existing_title
        elif strategy == 'combine':
            # Choose the more detailed title
            if len(new_title) > len(existing_title):
                return new_title
            else:
                return existing_title
        
        return existing_title
    
    def _merge_descriptions(self, new_event: Dict, existing_event: Dict, existing_info: Dict, merge_strategy: Dict) -> str:
        """Merge event descriptions based on strategy"""
        new_desc = new_event.get('description', '')
        existing_desc = existing_event.get('description', '')
        
        strategy = merge_strategy.get('keep_description', 'combine')
        
        if strategy == 'event1':
            return new_desc
        elif strategy == 'event2':
            return existing_desc
        elif strategy == 'combine':
            # Combine both descriptions intelligently
            combined = []
            
            if existing_desc:
                combined.append(existing_desc)
            
            if new_desc and new_desc.lower() not in existing_desc.lower():
                combined.append(f"\n--- Información adicional ---\n{new_desc}")
            
            # Add source tracking
            combined.append(f"\n--- Fuentes combinadas ---")
            combined.append(f"Email original: {existing_info['source_email']['subject']}")
            combined.append(f"Email adicional: {new_event.get('source_email_subject', 'Email reciente')}")
            
            return '\n'.join(combined)
        
        return existing_desc or new_desc
    
    def _get_calendar_id_for_event(self, event_id: str, calendar_service, config: Dict) -> Optional[str]:
        """Find which calendar contains the given event ID"""
        # Try both calendars to find where this event exists
        calendar_ids = [
            config['calendars']['calendar_id_1'],
            config['calendars']['calendar_id_2']
        ]
        
        for calendar_id in calendar_ids:
            try:
                calendar_service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                # If we get here, the event exists in this calendar
                return calendar_id
            except:
                # Event doesn't exist in this calendar, try next
                continue
        
        return None
    
    def _update_event_tracking(self, existing_info: Dict, new_event: Dict, merged_event: Dict):
        """Update the event tracking system with merged event information"""
        # Update the existing event tracking with new information
        source_email_id = existing_info['source_email']['id']
        
        if source_email_id in self.event_tracker.mappings:
            # Find and update the specific event
            for event_info in self.event_tracker.mappings[source_email_id]['calendar_events']:
                if event_info['calendar_event_id'] == existing_info['event_data']['calendar_event_id']:
                    event_info['summary'] = merged_event['summary']
                    event_info['description'] = merged_event.get('description', '')
                    event_info['updated_at'] = datetime.now().isoformat()
                    event_info['merged_count'] = event_info.get('merged_count', 1) + 1
                    break
            
            # Save updated mappings
            self.event_tracker._save_mappings()
    
    def should_auto_merge(self, duplicate_info: Dict) -> bool:
        """Determine if events should be auto-merged or require manual review"""
        similarity_score = duplicate_info.get('similarity_score', 0.0)
        
        # Auto-merge if very high similarity and same sender
        if similarity_score > 0.9:
            new_event = duplicate_info['new_event']
            existing_info = duplicate_info['existing_event']
            
            # Check if same sender (same teacher)
            new_sender = new_event.get('source_email_sender', '').lower()
            existing_sender = existing_info['source_email'].get('sender', '').lower()
            
            # Extract email addresses for comparison
            if '@' in new_sender and '@' in existing_sender:
                new_email = new_sender.split('<')[-1].replace('>', '').strip()
                existing_email = existing_sender.split('<')[-1].replace('>', '').strip()
                
                if new_email == existing_email:
                    return True
        
        return False