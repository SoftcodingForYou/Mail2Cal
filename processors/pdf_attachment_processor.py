#!/usr/bin/env python3
"""
PDF Attachment Processor for Mail2Cal
Handles detection, download, and text extraction from PDF attachments in emails
"""

import os
import base64
import tempfile
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import mimetypes

# PDF processing libraries (install with: pip install pdfplumber PyMuPDF)
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("[!] pdfplumber not available. Install with: pip install pdfplumber")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("[!] PyMuPDF not available. Install with: pip install PyMuPDF")

from googleapiclient.errors import HttpError


class PDFAttachmentProcessor:
    """Handles PDF attachment detection and processing for email events"""
    
    def __init__(self, gmail_service, config: Dict):
        self.gmail_service = gmail_service
        self.config = config
        self.temp_dir = tempfile.mkdtemp(prefix="mail2cal_pdf_")
        self.processed_attachments = {}  # Cache to avoid reprocessing
        
    def __del__(self):
        """Cleanup temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
    
    def has_pdf_attachments(self, email_message: Dict) -> bool:
        """Check if email has PDF attachments"""
        try:
            pdf_attachments = self._find_pdf_attachments(email_message['payload'])
            return len(pdf_attachments) > 0
        except Exception as e:
            print(f"[!] Error checking for PDF attachments: {e}")
            return False
    
    def process_email_with_attachments(self, email: Dict, email_message: Dict) -> str:
        """
        Process email and extract text from PDF attachments
        Returns enhanced email content with PDF text appended
        """
        enhanced_content = email['body']
        
        try:
            # Find PDF attachments
            pdf_attachments = self._find_pdf_attachments(email_message['payload'])
            
            if not pdf_attachments:
                return enhanced_content
            
            print(f"[PDF] Found {len(pdf_attachments)} PDF attachment(s)")

            # Process each PDF attachment
            for i, attachment_info in enumerate(pdf_attachments, 1):
                safe_filename = attachment_info['filename'].encode('ascii', errors='replace').decode('ascii')
                print(f"[PDF] Processing PDF {i}/{len(pdf_attachments)}: {safe_filename}")
                
                # Download and extract text
                pdf_text = self._download_and_extract_pdf(
                    email['id'], 
                    attachment_info['attachment_id'],
                    attachment_info['filename']
                )
                
                if pdf_text:
                    # Clean filename for safe display
                    safe_filename = attachment_info['filename'].encode('ascii', errors='replace').decode('ascii')
                    enhanced_content += f"\n\n=== CONTENIDO DEL ARCHIVO PDF: {safe_filename} ===\n"
                    enhanced_content += pdf_text
                    enhanced_content += f"\n=== FIN DEL ARCHIVO PDF ===\n"
                    print(f"[+] Successfully extracted {len(pdf_text)} characters from PDF")
                else:
                    safe_filename = attachment_info['filename'].encode('ascii', errors='replace').decode('ascii')
                    print(f"[-] Failed to extract text from {safe_filename}")
            
            return enhanced_content
            
        except Exception as e:
            print(f"[!] Error processing PDF attachments: {e}")
            return enhanced_content
    
    def _find_pdf_attachments(self, payload: Dict) -> List[Dict]:
        """Recursively find PDF attachments in email payload"""
        pdf_attachments = []
        
        def scan_parts(part):
            # Check if this part has subparts
            if 'parts' in part:
                for subpart in part['parts']:
                    scan_parts(subpart)
            else:
                # Check if this part is a PDF attachment
                mime_type = part.get('mimeType', '').lower()
                filename = part.get('filename', '')
                body = part.get('body', {})
                attachment_id = body.get('attachmentId')
                
                # Identify PDF files
                if (attachment_id and filename and 
                    (mime_type == 'application/pdf' or 
                     filename.lower().endswith('.pdf'))):
                    
                    pdf_attachments.append({
                        'filename': filename,
                        'attachment_id': attachment_id,
                        'mime_type': mime_type,
                        'size': body.get('size', 0)
                    })
        
        scan_parts(payload)
        return pdf_attachments
    
    def _download_and_extract_pdf(self, message_id: str, attachment_id: str, filename: str) -> Optional[str]:
        """Download PDF attachment and extract text content"""
        
        # Check cache first
        cache_key = f"{message_id}_{attachment_id}"
        if cache_key in self.processed_attachments:
            return self.processed_attachments[cache_key]
        
        try:
            # Download attachment from Gmail
            attachment = self.gmail_service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            # Decode base64 data
            file_data = base64.urlsafe_b64decode(attachment['data'])
            
            # Create safe filename for Windows (limit length and remove problematic chars)
            import re
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            safe_filename = safe_filename[:50]  # Limit to 50 chars
            if not safe_filename.endswith('.pdf'):
                safe_filename += '.pdf'
            
            # Save to temporary file with safe name
            temp_pdf_path = os.path.join(self.temp_dir, f"{attachment_id[:10]}_{safe_filename}")
            with open(temp_pdf_path, 'wb') as f:
                f.write(file_data)
            
            # Extract text from PDF
            pdf_text = self._extract_text_from_pdf(temp_pdf_path, filename)
            
            # Cache result
            self.processed_attachments[cache_key] = pdf_text
            
            # Clean up temporary file
            try:
                os.remove(temp_pdf_path)
            except:
                pass
            
            return pdf_text
            
        except HttpError as e:
            print(f"[-] Gmail API error downloading attachment: {e}")
            return None
        except Exception as e:
            print(f"[-] Error downloading/processing PDF {filename}: {e}")
            return None
    
    def _extract_text_from_pdf(self, pdf_path: str, filename: str) -> Optional[str]:
        """
        Extract text from PDF using pdfplumber (primary) and PyMuPDF (fallback)
        """
        
        # Try pdfplumber first (better for tables and Spanish text)
        if PDFPLUMBER_AVAILABLE:
            try:
                return self._extract_with_pdfplumber(pdf_path)
            except Exception as e:
                print(f"[!] pdfplumber extraction failed for {filename}: {e}")
        
        # Fallback to PyMuPDF
        if PYMUPDF_AVAILABLE:
            try:
                return self._extract_with_pymupdf(pdf_path)
            except Exception as e:
                print(f"[!] PyMuPDF extraction failed for {filename}: {e}")
        
        print(f"[-] No PDF extraction libraries available or all failed for {filename}")
        return None
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """Extract text using pdfplumber (best for tables)"""
        text_content = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract tables first (better structure preservation)
                tables = page.extract_tables()
                if tables:
                    text_content.append(f"\n--- PAGINA {page_num} (TABLAS) ---")
                    for table_num, table in enumerate(tables, 1):
                        text_content.append(f"\nTabla {table_num}:")
                        for row in table:
                            if row:  # Skip empty rows
                                # Clean and sanitize cell content
                                clean_cells = []
                                for cell in row:
                                    if cell:
                                        # Remove problematic Unicode characters
                                        clean_cell = self._clean_unicode_text(str(cell))
                                        clean_cells.append(clean_cell)
                                    else:
                                        clean_cells.append("")
                                row_text = " | ".join(clean_cells)
                                text_content.append(row_text)

                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"\n--- PAGINA {page_num} (TEXTO) ---")
                    # Clean the page text to remove problematic Unicode
                    clean_page_text = self._clean_unicode_text(page_text)
                    text_content.append(clean_page_text)

        return "\n".join(text_content)
    
    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """Extract text using PyMuPDF (faster fallback)"""
        text_content = []

        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()

            if page_text.strip():
                text_content.append(f"\n--- PAGINA {page_num + 1} ---")
                # Clean the page text to remove problematic Unicode
                clean_page_text = self._clean_unicode_text(page_text)
                text_content.append(clean_page_text)

        doc.close()
        return "\n".join(text_content)

    def _clean_unicode_text(self, text: str) -> str:
        """Clean text to remove problematic Unicode characters that cause encoding issues"""
        if not text:
            return ""

        # Replace common problematic Unicode characters
        replacements = {
            '\u2022': '•',  # Bullet point
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u00a0': ' ',  # Non-breaking space
            '\u00b0': '°',  # Degree symbol
            '\u2026': '...', # Horizontal ellipsis
        }

        # Apply replacements
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)

        # Remove emoji and other high Unicode characters that cause issues
        # Keep only ASCII and basic Latin characters
        import re
        text = re.sub(r'[^\x00-\x7F\u00C0-\u017F\u0100-\u024F\u1E00-\u1EFF]', '?', text)

        # Clean up multiple spaces and normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text
    
    def get_attachment_summary(self, email_message: Dict) -> str:
        """Get a summary of attachments for logging purposes"""
        pdf_attachments = self._find_pdf_attachments(email_message['payload'])
        
        if not pdf_attachments:
            return "No PDF attachments"
        
        summary = f"{len(pdf_attachments)} PDF attachment(s): "
        filenames = [att['filename'] for att in pdf_attachments]
        return summary + ", ".join(filenames)


def check_pdf_dependencies() -> Tuple[bool, str]:
    """Check if required PDF processing libraries are available"""
    status = []
    
    if PDFPLUMBER_AVAILABLE:
        status.append("✅ pdfplumber available")
    else:
        status.append("❌ pdfplumber missing - install with: pip install pdfplumber")
    
    if PYMUPDF_AVAILABLE:
        status.append("✅ PyMuPDF available")
    else:
        status.append("❌ PyMuPDF missing - install with: pip install PyMuPDF")
    
    available = PDFPLUMBER_AVAILABLE or PYMUPDF_AVAILABLE
    return available, "\n".join(status)


if __name__ == "__main__":
    # Test PDF dependencies
    available, status = check_pdf_dependencies()
    print("PDF Processing Dependencies:")
    print(status)
    
    if available:
        print("\n✅ PDF attachment processing is available!")
    else:
        print("\n❌ Install at least one PDF library to enable attachment processing")
        print("Recommended: pip install pdfplumber PyMuPDF")