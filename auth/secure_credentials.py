#!/usr/bin/env python3
"""
Secure Credential Manager for Mail2Cal
Fetches credentials from Google Sheets via Google Apps Script
"""

import requests
import os
import json
from functools import lru_cache
from typing import Optional, Dict

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

# Load URL from configuration file
try:
    from .secure_credentials_config import CREDENTIALS_URL
except ImportError:
    # Fallback URL - replace with your actual Google Apps Script Web App URL
    CREDENTIALS_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
    print("[!] Warning: Using fallback URL. Create 'secure_credentials_config.py' with your actual CREDENTIALS_URL")

# Fallback to environment variables if Google Sheets is unavailable
FALLBACK_CREDENTIALS = {
    'ANTHROPIC_API_KEY': 'ANTHROPIC_API_KEY',
    'GOOGLE_CALENDAR_ID_1': 'GOOGLE_CALENDAR_ID_1', 
    'GOOGLE_CALENDAR_ID_2': 'GOOGLE_CALENDAR_ID_2',
    'GMAIL_ADDRESS': 'GMAIL_ADDRESS',
    'EMAIL_SENDER_FILTER': 'EMAIL_SENDER_FILTER',
    'TEACHER_1_EMAIL': 'TEACHER_1_EMAIL',  # Teacher 1 → Calendar 1
    'TEACHER_2_EMAIL': 'TEACHER_2_EMAIL',  # Teacher 2 → Calendar 2
    'TEACHER_3_EMAIL': 'TEACHER_3_EMAIL',  # Teacher 3 (Afterschool) → Both Calendars
    'TEACHER_4_EMAIL': 'TEACHER_4_EMAIL',  # Teacher 4 (Afterschool) → Both Calendars
    'AI_MODEL': 'AI_MODEL',
    'DEFAULT_MONTHS_BACK': 'DEFAULT_MONTHS_BACK'
}

class SecureCredentialManager:
    """Manages secure credential retrieval from Google Sheets"""
    
    def __init__(self, credentials_url: str = CREDENTIALS_URL):
        self.credentials_url = credentials_url
        self._credentials_cache = {}
        self._cache_loaded = False
    
    def _load_credentials(self) -> Dict[str, str]:
        """Load all credentials from Google Sheets (cached)"""
        if self._cache_loaded:
            return self._credentials_cache
            
        try:
            print("[*] Loading credentials from secure Google Sheets...")
            response = requests.get(self.credentials_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"Server error: {data['error']}")
                
            if 'credentials' in data:
                self._credentials_cache = data['credentials']
                self._cache_loaded = True
                print(f"[+] Successfully loaded {len(self._credentials_cache)} credentials")
                return self._credentials_cache
            else:
                raise Exception("Invalid response format")
                
        except Exception as e:
            print(f"[!] Error loading credentials from Google Sheets: {e}")
            print("[!] Falling back to environment variables...")
            
            # Load from environment variables as fallback
            fallback_creds = {}
            for key, env_var in FALLBACK_CREDENTIALS.items():
                value = os.getenv(env_var, '')
                if value:
                    fallback_creds[key] = value
                    
            self._credentials_cache = fallback_creds
            self._cache_loaded = True
            return self._credentials_cache
    
    @lru_cache(maxsize=None)
    def get_credential(self, key: str) -> str:
        """Get a specific credential by key"""
        credentials = self._load_credentials()
        
        if key in credentials:
            return credentials[key]
        
        # Fallback to environment variable
        env_value = os.getenv(key, '')
        if env_value:
            print(f"[!] Using environment variable for {key}")
            return env_value
            
        raise ValueError(f"Credential '{key}' not found in secure storage or environment variables")
    
    def get_all_credentials(self) -> Dict[str, str]:
        """Get all available credentials"""
        return self._load_credentials()
    
    def test_connection(self) -> bool:
        """Test connection to credential storage"""
        try:
            credentials = self._load_credentials()
            return len(credentials) > 0
        except:
            return False
    
    def validate_required_credentials(self) -> bool:
        """Validate that all required credentials are available"""
        required_keys = [
            'ANTHROPIC_API_KEY',
            'GOOGLE_CALENDAR_ID_1', 
            'GOOGLE_CALENDAR_ID_2',
            'GMAIL_ADDRESS',
            'EMAIL_SENDER_FILTER',
            'TEACHER_1_EMAIL',
            'TEACHER_2_EMAIL',
            'TEACHER_3_EMAIL',
            'TEACHER_4_EMAIL'
        ]
        
        try:
            credentials = self._load_credentials()
            missing_keys = []
            
            for key in required_keys:
                if key not in credentials or not credentials[key]:
                    missing_keys.append(key)
            
            if missing_keys:
                print(f"[!] Missing required credentials: {missing_keys}")
                return False
                
            print("[+] All required credentials are available")
            return True
            
        except Exception as e:
            print(f"[!] Error validating credentials: {e}")
            return False

# Global credential manager instance
_credential_manager = None

def get_credential_manager(credentials_url: str = CREDENTIALS_URL) -> SecureCredentialManager:
    """Get the global credential manager instance"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = SecureCredentialManager(credentials_url)
    return _credential_manager

def get_secure_credential(key: str) -> str:
    """Convenience function to get a credential"""
    manager = get_credential_manager()
    return manager.get_credential(key)

def test_secure_credentials():
    """Test function to validate credential system"""
    print("[*] Testing Secure Credential System")
    print("=" * 50)
    
    manager = get_credential_manager()
    
    # Test connection
    if manager.test_connection():
        print("[+] Connection to credential storage: SUCCESS")
    else:
        print("[-] Connection to credential storage: FAILED")
        return False
    
    # Validate required credentials
    if manager.validate_required_credentials():
        print("[+] Required credentials validation: SUCCESS")
    else:
        print("[-] Required credentials validation: FAILED")
        return False
    
    # Test individual credential retrieval
    test_keys = ['ANTHROPIC_API_KEY', 'GOOGLE_CALENDAR_ID_1', 'GMAIL_ADDRESS']
    
    for key in test_keys:
        try:
            value = manager.get_credential(key)
            # Show only first 10 chars for security
            preview = value[:10] + "..." if len(value) > 10 else value
            print(f"[+] {key}: {preview}")
        except Exception as e:
            print(f"[-] {key}: ERROR - {e}")
            return False
    
    print("\n[+] Secure credential system is working correctly!")
    return True

if __name__ == "__main__":
    # Run tests when script is executed directly
    test_secure_credentials()