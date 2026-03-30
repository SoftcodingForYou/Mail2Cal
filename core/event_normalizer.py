"""
Pure-Python normalization layer for extracted event dicts.
Runs immediately after _convert_ai_event_to_internal() and before
duplicate detection / calendar creation.
No AI calls — only validation, defaulting, and field enrichment.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional


def normalize_event(event: Dict) -> Dict:
    """
    Accepts the internal event dict produced by _convert_ai_event_to_internal()
    and returns it enriched with normalized/validated fields.

    Existing keys are preserved for backward compatibility.
    Scratch keys (_raw_*) are consumed and removed.
    """
    # --- 1. Consume scratch fields set by _convert_ai_event_to_internal ---
    raw_desc = event.pop('_raw_ai_description', '')
    raw_notes = event.pop('_raw_ai_notes', '')
    raw_instructions: List[str] = event.pop('_raw_instructions', [])
    raw_materials: List[str] = event.pop('_raw_materials_needed', [])
    raw_parent_info: str = event.pop('_raw_parent_info', '')
    raw_schedule_details: str = event.pop('_raw_schedule_details', '')

    # Ensure list fields are actually lists (AI may return a string or null)
    if not isinstance(raw_instructions, list):
        raw_instructions = [raw_instructions] if raw_instructions else []
    if not isinstance(raw_materials, list):
        raw_materials = [raw_materials] if raw_materials else []

    # --- 2. source_type ---
    source_id = event.get('source_email_id', '')
    source_type = 'file' if source_id.startswith('file_') else 'email'
    event['source_type'] = source_type
    event['source_id'] = source_id
    event['source_subject'] = event.get('source_email_subject', '')
    event['source_date'] = event.get('source_email_date', '')
    # source_email_sender is added by mail2cal.py after parse_events_from_email()
    # returns, so it is not available here yet. Coexists with source_email_sender later.
    event['source_sender'] = event.get('source_email_sender', '')

    # --- 3. summary whitespace cleaning ---
    summary = event.get('summary', '')
    event['summary'] = ' '.join(summary.split()).strip() or 'Evento Escolar'

    # --- 4. is_all_day — authoritative resolution ---
    ai_all_day = event.get('all_day', False)
    start_dt: Optional[datetime] = event.get('start_time')

    if start_dt is None:
        # No date/time at all — must be all-day
        is_all_day = True
    elif start_dt.hour == 0 and start_dt.minute == 0 and start_dt.second == 0 and ai_all_day:
        # Midnight + AI said all_day → all-day
        is_all_day = True
    else:
        # Either a real time, or midnight with ai_all_day=False (AI was explicit)
        is_all_day = False

    event['is_all_day'] = is_all_day
    event['all_day'] = is_all_day  # correct the existing key in-place

    # --- 5. start_date string ---
    start_date = start_dt.date().isoformat() if start_dt else ''
    event['start_date'] = start_date
    event['start_time_hm'] = (
        None if is_all_day or start_dt is None
        else start_dt.strftime('%H:%M')
    )

    # --- 6. end_time defaulting ---
    end_dt: Optional[datetime] = event.get('end_time')

    if not is_all_day and start_dt is not None:
        if end_dt is None or end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=2)
            event['end_time'] = end_dt  # mutate the backward-compat field

    # --- 7. end_date string ---
    end_date = end_dt.date().isoformat() if end_dt else start_date
    event['end_date'] = end_date
    event['end_time_hm'] = (
        None if is_all_day or end_dt is None
        else end_dt.strftime('%H:%M')
    )

    # --- 8. Structured content fields ---
    event['main_info'] = raw_desc.strip()
    event['additional_info'] = raw_notes.strip()

    # Clean and store list fields (filter out empty strings)
    event['instructions'] = [i.strip() for i in raw_instructions if str(i).strip()]
    event['materials_needed'] = [m.strip() for m in raw_materials if str(m).strip()]
    event['parent_info'] = raw_parent_info.strip()
    event['schedule_details'] = raw_schedule_details.strip()

    # important_info: union of actionable structured fields for quick access
    event['important_info'] = _build_important_info(
        event['instructions'],
        event['materials_needed'],
        event['parent_info'],
        event['schedule_details'],
        event.get('event_type', 'general'),
        raw_desc,
    )

    return event


def _build_important_info(
    instructions: List[str],
    materials: List[str],
    parent_info: str,
    schedule_details: str,
    event_type: str,
    description: str,
) -> str:
    """
    Assembles a human-readable summary of all actionable/important content.
    Used as a quick-access field; the individual structured fields remain
    available separately.
    """
    parts = []

    if instructions:
        parts.append('INSTRUCCIONES:\n' + '\n'.join(f'- {i}' for i in instructions))

    if materials:
        parts.append('MATERIALES A TRAER:\n' + '\n'.join(f'- {m}' for m in materials))
    elif event_type == 'solicitud_material' and description.strip():
        # Fallback: AI marked as material request but didn't populate the list
        parts.append(f'MATERIALES A TRAER:\n{description.strip()}')

    if parent_info:
        parts.append(f'PARA APODERADOS:\n{parent_info}')

    if schedule_details:
        parts.append(f'HORARIO Y LOGISTICA:\n{schedule_details}')

    return '\n\n'.join(parts)
