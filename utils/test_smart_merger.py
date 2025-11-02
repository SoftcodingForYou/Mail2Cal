#!/usr/bin/env python3
"""
Test the smart event merger functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Credentials will be loaded from secure system

from core.smart_event_merger import SmartEventMerger
from core.event_tracker import EventTracker
from datetime import datetime

def test_smart_merger():
    """Test the smart event merger with sample data"""
    
    # Mock AI config
    ai_config = {
        'provider': 'anthropic',
        'api_key_env_var': 'ANTHROPIC_API_KEY',
        'model': 'claude-sonnet-4-5-20250929',
        'model_cheap': 'claude-haiku-4-5-20251001'
    }
    
    # Create event tracker and smart merger
    event_tracker = EventTracker('test_event_mappings.json')
    smart_merger = SmartEventMerger(ai_config, event_tracker)
    
    print("[*] Testing Smart Event Merger")
    print("=" * 50)
    
    # Test events similar to the user's examples
    new_events = [
        {
            'summary': 'Día de la Familia',
            'description': 'Celebración del Día de la Familia para nivel Play group y Jardín. Deben asistir 2 personas significativas por estudiante y traer una foto familiar 10x13.',
            'start_time': '2025-07-30T08:30:00',
            'source_email_subject': 'Cierre de semana/ Cronograma',
            'source_email_sender': 'Rosa Paola Contreras Ulloa <rosa.contreras@colegiomanquecura.cl>',
            'source_email_date': 'Fri, 11 Jul 2025 16:38:43 +0000'
        }
    ]
    
    source_email = {
        'subject': 'Cierre de semana/ Cronograma',
        'sender': 'Rosa Paola Contreras Ulloa <rosa.contreras@colegiomanquecura.cl>',
        'date': 'Fri, 11 Jul 2025 16:38:43 +0000'
    }
    
    # Add a similar event to the tracker to simulate existing event
    existing_email = {
        'id': 'test_email_1',
        'subject': 'Cierre de semana/ Cronograma 28 de julio al 1 de agosto',
        'sender': 'Rosa Paola Contreras Ulloa <rosa.contreras@colegiomanquecura.cl>',
        'date': 'Fri, 25 Jul 2025 16:39:28 +0000',
        'body': 'Test email body'
    }
    
    existing_events = [
        {
            'summary': 'Dia de la Familia',
            'description': 'Actividad especial donde se invita a dos apoderados por niño/a para disfrutar de actividades preparadas. Los estudiantes llegan y se retiran con sus apoderados. Traer una fotografía familiar tamaño 10x15 aprox.',
            'start_time': datetime(2025, 7, 30, 8, 30)
        }
    ]
    
    calendar_event_ids = ['test_event_id_123']
    
    # Track the existing event
    event_tracker.track_email_processing(existing_email, existing_events, calendar_event_ids)
    
    print(f"[+] Added test existing event to tracker")
    print(f"[+] Testing duplicate detection for new events...")
    
    # Test duplicate detection
    try:
        potential_duplicates = smart_merger.find_potential_duplicates(new_events, source_email)
        
        print(f"\n[*] Found {len(potential_duplicates)} potential duplicate(s)")
        
        for i, duplicate_info in enumerate(potential_duplicates):
            print(f"\nDuplicate {i+1}:")
            print(f"  New Event: {duplicate_info['new_event']['summary']}")
            print(f"  Existing Event: {duplicate_info['existing_event']['event_data']['summary']}")
            print(f"  Similarity Score: {duplicate_info['similarity_score']:.2f}")
            print(f"  Action: {duplicate_info['action']}")
            
            if duplicate_info.get('merge_recommendation'):
                merge_rec = duplicate_info['merge_recommendation']
                print(f"  Merge Strategy:")
                print(f"    Keep Title: {merge_rec.get('keep_title', 'N/A')}")
                print(f"    Keep Description: {merge_rec.get('keep_description', 'N/A')}")
                print(f"    Combine Notes: {merge_rec.get('combine_notes', 'N/A')}")
        
        print(f"\n[+] Smart merger test completed successfully!")
        
    except Exception as e:
        print(f"[!] Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    # Clean up test file
    if os.path.exists('test_event_mappings.json'):
        os.remove('test_event_mappings.json')
        print(f"[+] Cleaned up test file")

if __name__ == "__main__":
    test_smart_merger()