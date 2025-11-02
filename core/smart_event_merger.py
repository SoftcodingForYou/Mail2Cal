"""
AI-powered smart event merger for detecting and merging duplicate events across emails
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import anthropic
import os
import time
from auth.secure_credentials import get_secure_credential


class SmartEventMerger:
    """Detects and merges duplicate events from different emails using AI analysis"""

    def __init__(self, ai_config: Dict, event_tracker, token_tracker=None):
        self.ai_config = ai_config
        self.event_tracker = event_tracker
        self.token_tracker = token_tracker
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

            if not candidates:
                continue

            # BATCH PROCESSING: Compare against multiple candidates in one API call
            # Process in batches of 5 to avoid overwhelming the prompt
            batch_size = 5
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i + batch_size]

                # Analyze all candidates in this batch with a single AI call
                batch_results = self._analyze_multiple_similarities(new_event, batch, source_email)

                # Process results
                for candidate, (similarity_score, merge_recommendation) in zip(batch, batch_results):
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

    def _analyze_multiple_similarities(self, new_event: Dict, candidates: List[Dict], source_email: Dict) -> List[Tuple[float, Dict]]:
        """Use AI to analyze if one new event matches multiple existing events (BATCHED)"""

        # Build prompt for batch comparison
        candidates_text = ""
        for idx, candidate in enumerate(candidates, 1):
            candidates_text += f"""
CANDIDATE {idx}:
Title: {candidate['event_data'].get('summary', 'No title')}
Date/Time: {candidate['event_data'].get('start_time', 'No date')}
Source Email: {candidate['source_email'].get('subject', '')} from {candidate['source_email'].get('sender', '')}
"""

        prompt = f"""Analyze if this new school event matches any of the existing events below:

NEW EVENT:
Title: {new_event.get('summary', 'No title')}
Date/Time: {new_event.get('start_time', 'No date')}
Description: {new_event.get('description', 'No description')}
Source Email: {source_email.get('subject', '')} from {source_email.get('sender', '')}

EXISTING EVENTS TO COMPARE:
{candidates_text}

For EACH candidate, determine:
1. Are they the same real-world event? (same activity, same date, same context)
2. Similarity score (0.0 to 1.0)
3. If duplicate, how to merge them?

Respond with ONLY valid JSON in this exact format (no other text):
{{
  "comparisons": [
    {{
      "candidate_number": 1,
      "is_duplicate": true/false,
      "similarity_score": 0.85,
      "reasoning": "brief explanation",
      "merge_strategy": {{
        "keep_title": "event1|event2|combine",
        "keep_description": "event1|event2|combine",
        "combine_notes": true/false,
        "preferred_time": "event1|event2"
      }}
    }}
  ]
}}"""

        # Retry logic with exponential backoff for transient errors
        max_retries = 10
        base_delay = 2  # Start with 2 seconds

        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.ai_config['model_cheap'],  # Use cheap model for duplicate detection
                    max_tokens=800,  # Reduced from 1500 (batch JSON response)
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                response_text = message.content[0].text.strip()

                # Log token usage
                if self.token_tracker:
                    self.token_tracker.log_call(
                        operation='duplicate_detection_batch',
                        model=self.ai_config['model_cheap'],
                        input_tokens=message.usage.input_tokens,
                        output_tokens=message.usage.output_tokens,
                        metadata={'batch_size': len(candidates)}
                    )

                # Extract JSON with robust handling
                response_text = self._extract_json_from_response(response_text)

                # Parse JSON response
                try:
                    analysis = json.loads(response_text)
                    comparisons = analysis.get('comparisons', [])

                    # Build results list matching the order of candidates
                    results = []
                    for idx in range(len(candidates)):
                        # Find comparison for this candidate (1-indexed in response)
                        comparison = next((c for c in comparisons if c.get('candidate_number') == idx + 1), None)

                        if comparison:
                            similarity_score = comparison.get('similarity_score', 0.0)
                            results.append((similarity_score, comparison))
                        else:
                            # No match found for this candidate
                            results.append((0.0, {}))

                    return results

                except json.JSONDecodeError as e:
                    # Retry if this isn't the last attempt
                    if attempt < max_retries - 1:
                        print(f"[!] JSON parse error (attempt {attempt + 1}/{max_retries}): {str(e)[:50]}, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[!] AI response not valid JSON after {max_retries} attempts")
                        print(f"[!] JSON Error: {str(e)}")
                        print(f"[!] Response preview: {response_text[:300]}...")
                        print(f"[!] Skipping duplicate detection for this batch")
                        return [(0.0, {}) for _ in candidates]

            except anthropic.RateLimitError as e:
                # Handle rate limit errors (429, 529)
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                    print(f"[!] API rate limit/overload (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"[!] API overloaded after {max_retries} attempts. Skipping AI analysis for this batch.")
                    return [(0.0, {}) for _ in candidates]

            except anthropic.APIError as e:
                # Handle other API errors
                if attempt < max_retries - 1 and hasattr(e, 'status_code') and e.status_code >= 500:
                    # Server errors - retry
                    delay = base_delay * (2 ** attempt)
                    print(f"[!] API error {e.status_code} (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"[!] API error in AI similarity analysis: {e}")
                    return [(0.0, {}) for _ in candidates]

            except Exception as e:
                print(f"[!] Error in AI batch similarity analysis: {e}")
                return [(0.0, {}) for _ in candidates]

        # Should not reach here, but just in case
        return [(0.0, {}) for _ in candidates]

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

You must respond with ONLY valid JSON in this exact format (no other text):
{{
    "is_duplicate": true,
    "similarity_score": 0.85,
    "reasoning": "brief explanation",
    "merge_strategy": {{
        "keep_title": "event1",
        "keep_description": "combine",
        "combine_notes": true,
        "preferred_time": "event2"
    }}
}}"""

        # Retry logic with exponential backoff for transient errors
        max_retries = 10
        base_delay = 2  # Start with 2 seconds

        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.ai_config['model_cheap'],  # Use cheap model for duplicate detection
                    max_tokens=500,  # Reduced from 1500 (only need small JSON)
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                response_text = message.content[0].text.strip()

                # Log token usage
                if self.token_tracker:
                    self.token_tracker.log_call(
                        operation='duplicate_detection_single',
                        model=self.ai_config['model_cheap'],
                        input_tokens=message.usage.input_tokens,
                        output_tokens=message.usage.output_tokens,
                        metadata={}
                    )

                # Extract JSON with robust handling
                response_text = self._extract_json_from_response(response_text)

                # Parse JSON response
                try:
                    analysis = json.loads(response_text)
                    similarity_score = analysis.get('similarity_score', 0.0)
                    return similarity_score, analysis
                except json.JSONDecodeError as e:
                    # Retry if this isn't the last attempt
                    if attempt < max_retries - 1:
                        print(f"[!] JSON parse error (attempt {attempt + 1}/{max_retries}): {str(e)[:50]}, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[!] AI response not valid JSON after {max_retries} attempts")
                        print(f"[!] JSON Error: {str(e)}")
                        print(f"[!] Response preview: {response_text[:300]}...")
                        return 0.0, {}

            except anthropic.RateLimitError as e:
                # Handle rate limit errors (429, 529)
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                    print(f"[!] API rate limit/overload (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"[!] API overloaded after {max_retries} attempts. Skipping AI analysis for this event pair.")
                    return 0.0, {}

            except anthropic.APIError as e:
                # Handle other API errors
                if attempt < max_retries - 1 and hasattr(e, 'status_code') and e.status_code >= 500:
                    # Server errors - retry
                    delay = base_delay * (2 ** attempt)
                    print(f"[!] API error {e.status_code} (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"[!] API error in AI similarity analysis: {e}")
                    return 0.0, {}

            except Exception as e:
                print(f"[!] Error in AI similarity analysis: {e}")
                return 0.0, {}

        # Should not reach here, but just in case
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
        from datetime import datetime, timedelta
        existing_event = existing_info['event_data']

        # Determine time format from existing event (preserve it to avoid API errors)
        # Google Calendar API requires: both date OR both dateTime, not mixed
        start_format, end_format = self._get_event_time_format(new_event, existing_event, merge_strategy)

        # Start with existing event structure
        merged = {
            'summary': self._merge_titles(new_event, existing_event, merge_strategy),
            'description': self._merge_descriptions(new_event, existing_event, existing_info, merge_strategy),
            'start': start_format,
            'end': end_format,
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

    def _get_event_time_format(self, new_event: Dict, existing_event: Dict, merge_strategy: Dict) -> tuple:
        """Get properly formatted start/end times that match (both date OR both dateTime)"""
        from datetime import datetime, timedelta

        # Decide which event's timing to use based on strategy
        preferred_time = merge_strategy.get('merge_strategy', {}).get('preferred_time', 'event2')

        # Choose source event for timing
        if preferred_time == 'event1':
            source_event = new_event
        else:
            # Default to existing event to preserve original timing
            source_event = existing_event

        # Check if source event uses all_day format
        is_all_day = source_event.get('all_day', False)

        # Get start and end times
        start_time = source_event.get('start_time')
        end_time = source_event.get('end_time')

        if is_all_day:
            # All-day event: both must use 'date' format
            if isinstance(start_time, str):
                start_date = start_time[:10]  # YYYY-MM-DD
            elif hasattr(start_time, 'date'):
                start_date = start_time.date().isoformat()
            else:
                start_date = datetime.now().date().isoformat()

            # End date is start + 1 day for all-day events
            end_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() + timedelta(days=1)
            end_date = end_date_obj.isoformat()

            return (
                {'date': start_date},
                {'date': end_date}
            )
        else:
            # Timed event: both must use 'dateTime' format
            if isinstance(start_time, str):
                start_dt = start_time
            elif hasattr(start_time, 'isoformat'):
                start_dt = start_time.isoformat()
            else:
                start_dt = datetime.now().isoformat()

            if end_time:
                if isinstance(end_time, str):
                    end_dt = end_time
                elif hasattr(end_time, 'isoformat'):
                    end_dt = end_time.isoformat()
                else:
                    # Default to 1 hour after start
                    start_datetime = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
                    end_dt = (start_datetime + timedelta(hours=1)).isoformat()
            else:
                # Default to 1 hour after start
                start_datetime = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
                end_dt = (start_datetime + timedelta(hours=1)).isoformat()

            return (
                {'dateTime': start_dt, 'timeZone': 'America/Santiago'},
                {'dateTime': end_dt, 'timeZone': 'America/Santiago'}
            )
    
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

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Robustly extract JSON from AI response, handling various formatting issues
        """
        # Method 1: Try to extract from markdown code blocks
        if '```json' in response_text:
            try:
                extracted = response_text.split('```json')[1].split('```')[0].strip()
                return extracted
            except IndexError:
                pass

        if '```' in response_text:
            try:
                extracted = response_text.split('```')[1].split('```')[0].strip()
                # Verify it looks like JSON
                if extracted.strip().startswith('{'):
                    return extracted
            except IndexError:
                pass

        # Method 2: Find JSON object boundaries (look for outermost braces)
        # This handles cases where AI adds explanatory text before/after JSON
        try:
            # Find first { and last }
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                extracted = response_text[first_brace:last_brace + 1]

                # Quick validation: count braces
                if extracted.count('{') == extracted.count('}'):
                    return extracted
        except Exception:
            pass

        # Method 3: Remove common prefixes/suffixes that Haiku might add
        cleaned = response_text

        # Remove common AI prefixes
        prefixes_to_remove = [
            "Here is the JSON response:",
            "Here's the analysis:",
            "The JSON output is:",
            "Response:",
        ]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()

        # Remove common AI suffixes
        suffixes_to_remove = [
            "Let me know if you need any clarification.",
            "Hope this helps!",
        ]
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()

        # Method 4: Use regex to extract JSON structure
        # Look for pattern: { ... "comparisons": [ ... ] ... }
        json_pattern = r'\{[^{}]*"comparisons"[^{}]*\[[^\]]*\][^{}]*\}'
        matches = re.findall(json_pattern, cleaned, re.DOTALL)
        if matches:
            # Return the longest match (most complete)
            return max(matches, key=len)

        # Method 5: If all else fails, return original (will likely fail JSON parsing, triggering retry)
        return response_text