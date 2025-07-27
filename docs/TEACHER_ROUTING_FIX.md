# Teacher-to-Calendar Routing Fix

## Issue
Rosa and Karla's events are appearing in both calendars when they should only appear in their assigned calendar:
- Rosa (Teacher 1) should only create events in Calendar 1
- Karla (Teacher 2) should only create events in Calendar 2

## Root Cause
The teacher email addresses are not properly configured in the secure credentials, causing all teachers to fall through to the "other senders" default routing which sends events to both calendars.

## Diagnosis
Running the debug tool shows that all teachers are being classified as "Other school senders - DEFAULT" instead of matching their specific teacher roles.

## Solution
Configure the teacher emails correctly in your Google Sheets secure credentials:

### Required Configuration Values

Set these values in your Google Sheets (see SETUP_GUIDE.md for details):

```
TEACHER_1_EMAIL = rosa.contreras@colegiomanquecura.cl
TEACHER_2_EMAIL = karla.morales@colegiomanquecura.cl  
TEACHER_3_EMAIL = miriam.pacheco@colegiomanquecura.cl
TEACHER_4_EMAIL = (set as needed for other afterschool teacher)
```

### Expected Behavior After Fix

- **Rosa Contreras** (`rosa.contreras@colegiomanquecura.cl`) → Calendar 1 only
- **Karla Morales** (`karla.morales@colegiomanquecura.cl`) → Calendar 2 only
- **Miriam Pacheco** (`miriam.pacheco@colegiomanquecura.cl`) → Both calendars (afterschool)
- **Other senders** → Both calendars (default)

## Verification
After configuring the teacher emails:

1. Run the system and look for these log messages:
   - `[!] WARNING: Some teacher emails appear unconfigured` (should NOT appear)
   - `[!] No teacher match for [email] → routing to both calendars` (should only appear for non-teacher senders)

2. Run the debug tool:
   ```bash
   python utils/debug_teacher_routing.py
   ```

3. Check that events are created in the correct calendars:
   - Rosa's events should only appear in Calendar 1
   - Karla's events should only appear in Calendar 2
   - Miriam's events should appear in both calendars

## Code Changes Made

1. **Enhanced `get_target_calendars()` method** in `core/mail2cal.py`:
   - Added warning detection for unconfigured teacher emails
   - Added clearer logging for routing decisions
   - Made case-insensitive matching more explicit

2. **Fixed GlobalEventCache duplicate detection** to properly handle multi-calendar events

3. **Added diagnostic tools**:
   - `utils/debug_teacher_routing.py` - Analyzes current routing behavior
   - `utils/test_teacher_config.py` - Tests routing logic with proper configuration
   - `utils/analyze_missing_events.py` - Identifies missing multi-calendar events

## Related Issues Fixed

This fix also resolves the issue where legitimate multi-calendar events (like school-wide activities) were being incorrectly deleted due to over-aggressive duplicate detection.

## Files Modified

- `core/mail2cal.py` - Enhanced teacher routing logic
- `core/global_event_cache.py` - Fixed duplicate detection for multi-calendar events  
- `run_mail2cal.py` - Added recovery option for deleted events
- `utils/recover_deleted_events.py` - New recovery tool
- `utils/debug_teacher_routing.py` - New diagnostic tool