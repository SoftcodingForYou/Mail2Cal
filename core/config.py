#!/usr/bin/env python3
"""
Centralized configuration for Mail2Cal.
All credential loading happens here - other modules import from this.
"""

from auth.secure_credentials import get_secure_credential

_config_cache = None


def _load_all():
    """Load all credentials once from Google Sheets, cache the result."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    try:
        cal_id_1 = get_secure_credential('GOOGLE_CALENDAR_ID_1')
        cal_id_2 = get_secure_credential('GOOGLE_CALENDAR_ID_2')

        teacher_1 = get_secure_credential('TEACHER_1_EMAIL')
        teacher_2 = get_secure_credential('TEACHER_2_EMAIL')
        teacher_3 = get_secure_credential('TEACHER_3_EMAIL')
        teacher_4 = get_secure_credential('TEACHER_4_EMAIL')

        gmail_address = get_secure_credential('GMAIL_ADDRESS')
        sender_filter = get_secure_credential('EMAIL_SENDER_FILTER')

        # Build enhanced sender filter combining wildcard and exact teacher emails
        # Gmail's wildcard search (from:*domain*) can be slow to index recent emails
        # Using exact email addresses ensures immediate search results
        teacher_emails = [teacher_1, teacher_2, teacher_3, teacher_4]
        teacher_filter = " OR ".join([f"from:{e}" for e in teacher_emails])
        enhanced_sender_filter = f"({sender_filter} OR {teacher_filter})"

        anthropic_key = get_secure_credential('ANTHROPIC_API_KEY')
        ai_model = get_secure_credential('AI_MODEL')
        ai_model_cheap = get_secure_credential('AI_MODEL_CHEAP')
        default_months_back = float(get_secure_credential('DEFAULT_MONTHS_BACK'))

        _config_cache = {
            'calendars': {
                'calendar_id_1': cal_id_1,
                'calendar_id_2': cal_id_2,
                'teacher_1_email': teacher_1,
                'teacher_2_email': teacher_2,
                'teacher_3_email': teacher_3,
                'teacher_4_email': teacher_4,
            },
            'gmail': {
                'user_id': gmail_address,
                'sender_filter': enhanced_sender_filter,
            },
            'ai_service': {
                'provider': 'anthropic',
                'api_key_env_var': 'ANTHROPIC_API_KEY',
                'api_key': anthropic_key,
                'model': ai_model,
                'model_cheap': ai_model_cheap,
            },
            'date_range': {
                'default_months_back': default_months_back,
            },
            'event_tracking': {
                'storage_file': 'event_mappings.json',
            },
            'pdf_processing': {
                'enabled': True,
                'max_file_size_mb': 25,
                'cache_extractions': True,
            },
            'calendar_mapping': {
                'Calendar_1_Pre-Kinder_B': cal_id_1,
                'Calendar_2_Kinder_C': cal_id_2,
                'Both': 'both_calendars',
            },
        }
        print("[+] Credentials loaded securely from Google Sheets")
        print(f"[+] Enhanced filter with {len(teacher_emails)} exact teacher emails (avoids wildcard indexing delays)")
        return _config_cache

    except Exception as e:
        print(f"[!] Error loading secure credentials: {e}")
        print("[!] Please ensure your Google Apps Script is deployed and accessible")
        raise


def get_config():
    """Return the full config dict. Primary entry point for core/mail2cal.py."""
    return _load_all()


def get_calendar_ids():
    """Return (calendar_id_1, calendar_id_2) tuple.
    For utils that only need calendar IDs."""
    cfg = _load_all()
    return cfg['calendars']['calendar_id_1'], cfg['calendars']['calendar_id_2']


def get_calendar_and_teacher_config():
    """Return the calendars sub-dict (IDs + teacher emails).
    For utils that need routing info."""
    return _load_all()['calendars']


def get_ai_config():
    """Return the ai_service sub-dict."""
    return _load_all()['ai_service']


def get_calendar_mapping():
    """Return directory-name-to-calendar-ID mapping for file processors."""
    return dict(_load_all()['calendar_mapping'])
