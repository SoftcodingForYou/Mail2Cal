#!/usr/bin/env python3
"""
Email Preview Script - Review school emails before AI processing
"""

import os
import pickle
import base64
from datetime import datetime, timedelta
from typing import List, Dict
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Secure configuration - load from environment or secure storage
import sys
sys.path.append('..')
from secure_credentials import get_secure_credential

# Load credentials securely
try:
    GMAIL_ADDRESS = get_secure_credential('GMAIL_ADDRESS')
    EMAIL_SENDER_FILTER = get_secure_credential('EMAIL_SENDER_FILTER')
    DEFAULT_MONTHS_BACK = int(get_secure_credential('DEFAULT_MONTHS_BACK'))
except Exception as e:
    print(f"[!] Error loading credentials: {e}")
    print("[!] Falling back to environment variables")
    import os
    GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS', 'your-email@gmail.com')
    EMAIL_SENDER_FILTER = os.getenv('EMAIL_SENDER_FILTER', 'from:*school*')
    DEFAULT_MONTHS_BACK = int(os.getenv('DEFAULT_MONTHS_BACK', '12'))

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class EmailPreview:
    def __init__(self):
        self.gmail_service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.gmail_service = build('gmail', 'v1', credentials=creds)
    
    def get_school_emails(self, days_back: int = None) -> List[Dict]:
        """Fetch emails from school within specified date range"""
        if days_back is None:
            days_back = DEFAULT_MONTHS_BACK * 30
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Format dates for Gmail API
        after_date = start_date.strftime('%Y/%m/%d')
        before_date = end_date.strftime('%Y/%m/%d')
        
        # Build search query
        query = f"{EMAIL_SENDER_FILTER} after:{after_date} before:{before_date}"
        
        print(f"[*] Searching with query: {query}")
        print(f"[*] Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        try:
            # Search for emails
            result = self.gmail_service.users().messages().list(
                userId=GMAIL_ADDRESS,
                q=query
            ).execute()
            
            messages = result.get('messages', [])
            emails = []
            
            print(f"[*] Found {len(messages)} matching emails")
            
            if not messages:
                return emails
            
            print("[*] Fetching email details...")
            
            for i, message in enumerate(messages, 1):
                print(f"[{i}/{len(messages)}] Processing email {message['id']}")
                
                # Get full message details
                msg = self.gmail_service.users().messages().get(
                    userId=GMAIL_ADDRESS,
                    id=message['id']
                ).execute()
                
                email_data = self._parse_email(msg)
                emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f'[-] Error fetching emails: {error}')
            return []
    
    def _parse_email(self, message: Dict) -> Dict:
        """Parse Gmail message into structured data"""
        headers = message['payload'].get('headers', [])
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Extract body
        body = self._extract_email_body(message['payload'])
        
        # Parse date
        try:
            email_date = datetime.strptime(date_str.split(' +')[0].split(' -')[0], '%a, %d %b %Y %H:%M:%S')
        except:
            try:
                email_date = datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')
            except:
                email_date = datetime.now()
        
        return {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date_str,
            'parsed_date': email_date,
            'body': body,
            'snippet': message.get('snippet', ''),
            'body_length': len(body)
        }
    
    def _extract_email_body(self, payload: Dict) -> str:
        """Extract email body from payload with improved parsing"""
        body_parts = []
        
        def extract_from_part(part):
            """Recursively extract text from email parts"""
            if 'parts' in part:
                # Multipart message, recurse into parts
                for subpart in part['parts']:
                    extract_from_part(subpart)
            else:
                # Single part, extract content
                mime_type = part.get('mimeType', '')
                body_data = part.get('body', {})
                
                if 'data' in body_data and body_data['data']:
                    try:
                        # Decode base64 content
                        decoded_data = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='ignore')
                        
                        if mime_type == 'text/plain':
                            if decoded_data.strip():
                                body_parts.append(decoded_data.strip())
                        elif mime_type == 'text/html':
                            # Parse HTML and extract text
                            soup = BeautifulSoup(decoded_data, 'html.parser')
                            # Remove script and style elements
                            for script in soup(["script", "style"]):
                                script.decompose()
                            text = soup.get_text()
                            # Clean up whitespace
                            lines = (line.strip() for line in text.splitlines())
                            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                            text = ' '.join(chunk for chunk in chunks if chunk)
                            if text.strip():
                                body_parts.append(text.strip())
                    except Exception as e:
                        print(f"[!] Error decoding part {mime_type}: {e}")
        
        # Start extraction
        extract_from_part(payload)
        
        # Combine all parts
        body = '\n\n'.join(body_parts)
        
        # If still empty, try alternative approaches
        if not body.strip():
            # Try to get snippet from message
            snippet = payload.get('snippet', '')
            if snippet:
                body = f"[SNIPPET] {snippet}"
        
        return body.strip()
    
    def display_email_summary(self, emails: List[Dict]):
        """Display a summary of found emails"""
        print(f"\n[*] EMAIL SUMMARY")
        print("=" * 80)
        print(f"Total school emails found: {len(emails)}")
        
        if not emails:
            print("[!] No emails found matching the filter")
            return
        
        # Sort by date (newest first)
        emails.sort(key=lambda x: x['parsed_date'], reverse=True)
        
        print(f"\nMost recent emails:")
        for i, email in enumerate(emails[:10], 1):
            date_str = email['parsed_date'].strftime('%Y-%m-%d %H:%M')
            subject = email['subject'][:60]
            sender_short = email['sender'].split('<')[0].strip()
            
            print(f"{i:2d}. [{date_str}] {subject}")
            print(f"    From: {sender_short}")
            print(f"    Body length: {email['body_length']} chars")
            print()
        
        if len(emails) > 10:
            print(f"... and {len(emails) - 10} more emails")
        
        # Show date range
        oldest = min(emails, key=lambda x: x['parsed_date'])
        newest = max(emails, key=lambda x: x['parsed_date'])
        
        print(f"\nDate range:")
        print(f"Oldest: {oldest['parsed_date'].strftime('%Y-%m-%d %H:%M')}")
        print(f"Newest: {newest['parsed_date'].strftime('%Y-%m-%d %H:%M')}")
    
    def display_detailed_preview(self, emails: List[Dict], max_emails: int = 5):
        """Display detailed preview of a few emails"""
        print(f"\n[*] DETAILED PREVIEW (First {min(max_emails, len(emails))} emails)")
        print("=" * 80)
        
        for i, email in enumerate(emails[:max_emails], 1):
            print(f"\nEMAIL #{i}")
            print("-" * 40)
            print(f"Subject: {email['subject']}")
            print(f"From: {email['sender']}")
            print(f"Date: {email['parsed_date'].strftime('%Y-%m-%d %H:%M')}")
            print(f"ID: {email['id']}")
            print("\nContent preview (first 300 chars):")
            print(email['body'][:300] + "..." if len(email['body']) > 300 else email['body'])
            print("\n" + "=" * 80)

def main():
    """Main preview function"""
    print("[*] School Email Preview Tool")
    print("[*] This will show you all emails BEFORE using AI tokens")
    print("=" * 60)
    
    preview = EmailPreview()
    
    # Get emails
    emails = preview.get_school_emails()
    
    # Display summary
    preview.display_email_summary(emails)
    
    # Ask if user wants detailed preview
    if emails:
        print(f"\n[?] Would you like to see detailed preview of first 5 emails? (y/n): ", end="")
        try:
            response = input().lower().strip()
            if response in ['y', 'yes']:
                preview.display_detailed_preview(emails, 5)
        except:
            pass
        
        print(f"\n[*] Ready to process with AI? You have {len(emails)} emails that will use API tokens.")
        print("[*] Run 'python mail2cal.py' when ready to process with Claude AI.")

if __name__ == "__main__":
    main()