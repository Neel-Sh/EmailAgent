import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re
from typing import List, Dict
import os
import html2text
from bs4 import BeautifulSoup

class EmailService:
    def __init__(self, email_address: str, password: str):
        self.email_address = email_address
        self.password = password
        self.imap_server = "imap.gmail.com"
        self.smtp_server = "smtp.gmail.com"
        self.imap_port = 993
        self.smtp_port = 587
        
    def connect_imap(self):
        """Connect to Gmail IMAP server"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.password)
            return mail
        except Exception as e:
            raise Exception(f"Failed to connect to IMAP: {str(e)}")
    
    def connect_smtp(self):
        """Connect to Gmail SMTP server"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_address, self.password)
            return server
        except Exception as e:
            raise Exception(f"Failed to connect to SMTP: {str(e)}")
    
    def get_recent_emails(self, hours: int = 24, max_emails: int = 20) -> List[Dict]:
        """Fetch recent emails from Gmail"""
        try:
            mail = self.connect_imap()
            mail.select('INBOX')
            
            # Calculate date for search
            since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
            
            # Search for recent emails
            status, messages = mail.search(None, f'SINCE {since_date}')
            email_ids = messages[0].split()
            
            # Get the most recent emails
            email_ids = email_ids[-max_emails:] if len(email_ids) > max_emails else email_ids
            
            emails = []
            for email_id in reversed(email_ids):  # Most recent first
                try:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract email details
                    subject = email_message.get('Subject', 'No Subject')
                    sender = email_message.get('From', 'Unknown Sender')
                    date_str = email_message.get('Date', '')
                    
                    # Get email body
                    body = self._extract_body(email_message)
                    
                    emails.append({
                        'id': email_id.decode(),
                        'subject': subject,
                        'sender': sender,
                        'date': date_str,
                        'body': body[:500] + '...' if len(body) > 500 else body,  # Truncate for display
                        'full_body': body
                    })
                except Exception as e:
                    print(f"Error processing email {email_id}: {str(e)}")
                    continue
            
            mail.logout()
            return emails
            
        except Exception as e:
            raise Exception(f"Failed to fetch emails: {str(e)}")
    
    def _extract_body(self, email_message) -> str:
        """Extract body text from email message using proper parsing"""
        plain_text = ""
        html_content = ""
        
        # Initialize html2text converter with Gmail-like settings
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0  # Don't wrap lines
        h.single_line_break = True
        
        try:
            if email_message.is_multipart():
                # Handle multipart messages
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # Skip attachments
                    if "attachment" in content_disposition.lower():
                        continue
                    
                    # Get the payload
                    try:
                        payload = part.get_payload(decode=True)
                        if not payload:
                            continue
                            
                        # Try different encodings
                        text_content = ""
                        for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                            try:
                                text_content = payload.decode(encoding)
                                break
                            except:
                                continue
                        
                        if not text_content:
                            continue
                        
                        # Store based on content type
                        if content_type == "text/plain":
                            plain_text = text_content
                            break  # Prefer plain text
                        elif content_type == "text/html":
                            html_content = text_content
                            
                    except Exception as e:
                        continue
            else:
                # Handle single part message
                try:
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        # Try different encodings
                        for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                            try:
                                content = payload.decode(encoding)
                                content_type = email_message.get_content_type()
                                
                                if content_type == "text/plain":
                                    plain_text = content
                                else:
                                    html_content = content
                                break
                            except:
                                continue
                except:
                    pass
            
            # Process the content
            if plain_text:
                # Clean up plain text
                body = plain_text.strip()
                
                # Remove excessive whitespace but preserve structure
                body = re.sub(r'\r\n', '\n', body)
                body = re.sub(r'\n{3,}', '\n\n', body)  # Max 2 consecutive newlines
                body = re.sub(r'[ \t]+', ' ', body)  # Normalize spaces
                
            elif html_content:
                # Convert HTML to clean text using html2text
                try:
                    # First clean the HTML with BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "meta", "link"]):
                        script.extract()
                    
                    # Get text using html2text for better formatting
                    body = h.handle(str(soup))
                    
                    # Clean up the converted text
                    body = body.strip()
                    
                    # Remove markdown artifacts that don't look good
                    body = re.sub(r'\*\*([^*]+)\*\*', r'\1', body)  # Remove bold markdown
                    body = re.sub(r'\*([^*]+)\*', r'\1', body)      # Remove italic markdown
                    body = re.sub(r'_([^_]+)_', r'\1', body)        # Remove underscore emphasis
                    body = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', body)  # Remove markdown links
                    
                    # Clean up excessive newlines and spaces
                    body = re.sub(r'\n{3,}', '\n\n', body)
                    body = re.sub(r'[ \t]+', ' ', body)
                    
                except Exception as e:
                    # Fallback to basic HTML stripping
                    body = BeautifulSoup(html_content, 'html.parser').get_text()
                    body = re.sub(r'\s+', ' ', body).strip()
            else:
                return "No readable content found"
            
            # Final cleanup
            if not body or len(body.strip()) < 3:
                return "No readable content found"
            
            # Truncate very long emails but preserve readability
            if len(body) > 400:
                # Try to cut at a sentence boundary
                truncated = body[:400]
                last_period = truncated.rfind('. ')
                last_newline = truncated.rfind('\n')
                
                if last_period > 250:
                    body = truncated[:last_period + 1]
                elif last_newline > 200:
                    body = truncated[:last_newline]
                else:
                    body = truncated.rsplit(' ', 1)[0] + '...'
            
            return body.strip()
            
        except Exception as e:
            return f"Error extracting email content: {str(e)}"
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """Send an email via Gmail SMTP"""
        try:
            server = self.connect_smtp()
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")
    
    def get_email_summary_data(self, hours: int = 24) -> Dict:
        """Get summary data for email analysis"""
        try:
            emails = self.get_recent_emails(hours=hours, max_emails=50)
            
            return {
                'total_emails': len(emails),
                'emails': emails,
                'timeframe': f"Last {hours} hours"
            }
            
        except Exception as e:
            raise Exception(f"Failed to get email summary data: {str(e)}")
    
    def search_emails(self, 
                     keywords: List[str] = None, 
                     sender: str = None, 
                     subject_keywords: List[str] = None,
                     days_back: int = 30, 
                     max_results: int = 20,
                     search_body: bool = True) -> List[Dict]:
        """
        Search emails with multiple criteria
        
        Args:
            keywords: List of keywords to search for in subject/body
            sender: Email address or name to search for
            subject_keywords: Keywords to search specifically in subject
            days_back: How many days back to search
            max_results: Maximum number of results to return
            search_body: Whether to search in email body content
        """
        try:
            mail = self.connect_imap()
            mail.select('INBOX')
            
            # Build search criteria
            search_criteria = []
            
            # Date range
            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            search_criteria.append(f'SINCE {since_date}')
            
            # Sender filter - make it more flexible
            if sender:
                # Don't add sender to IMAP search criteria - we'll filter manually for better fuzzy matching
                pass
            
            # Subject keywords - Don't use IMAP SUBJECT search as it's too strict
            # We'll do manual filtering instead for better accuracy
            # if subject_keywords:
            #     for keyword in subject_keywords:
            #         search_criteria.append(f'SUBJECT "{keyword}"')
            
            # Combine criteria (just date range now, manual filtering for everything else)
            search_query = ' '.join(search_criteria) if search_criteria else 'ALL'
            
            print(f"📧 IMAP search query: {search_query}")  # Debug log
            
            # Search for emails
            status, messages = mail.search(None, search_query)
            email_ids = messages[0].split()
            
            print(f"📧 IMAP returned {len(email_ids)} email IDs")  # Debug log
            
            # Get the most recent matches first
            email_ids = email_ids[-max_results*2:] if len(email_ids) > max_results*2 else email_ids  # Get more to filter
            
            emails = []
            for email_id in reversed(email_ids):  # Most recent first
                try:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract email details
                    subject = email_message.get('Subject', 'No Subject')
                    sender_field = email_message.get('From', 'Unknown Sender')
                    date_str = email_message.get('Date', '')
                    body = self._extract_body(email_message)
                    
                    # Manual sender filtering for fuzzy matching
                    if sender:
                        sender_match = self._check_sender_match(sender_field, sender)
                        if not sender_match:
                            continue
                    
                    # **ENHANCED MANUAL FILTERING** - more reliable than IMAP search
                    if keywords or subject_keywords:
                        match_found = False
                        
                        # Check subject keywords FIRST (highest priority)
                        if subject_keywords:
                            for kw in subject_keywords:
                                if kw.lower() in subject.lower():
                                    match_found = True
                                    print(f"✅ Subject match: '{kw}' found in '{subject}'")  # Debug
                                    break
                        
                        # Check subject for general keywords (if no subject keyword match)
                        if not match_found and keywords:
                            for keyword in keywords:
                                if keyword.lower() in subject.lower():
                                    match_found = True
                                    print(f"✅ Subject keyword match: '{keyword}' in '{subject}'")  # Debug
                                    break
                        
                        # Check body only if no subject match and body search enabled
                        if not match_found and search_body and keywords:
                            for keyword in keywords:
                                if keyword.lower() in body.lower():
                                    match_found = True
                                    print(f"✅ Body match: '{keyword}' found in body")  # Debug
                                    break
                        
                        # If we have search terms but no match found, skip this email
                        if (keywords or subject_keywords) and not match_found:
                            continue
                    
                    # Create email result with enhanced content
                    email_result = {
                        'id': email_id.decode(),
                        'subject': subject,
                        'sender': sender_field,
                        'date': date_str,
                        'body': body[:350] + '...' if len(body) > 350 else body,
                        'full_body': body,
                        'relevance_score': self._calculate_relevance(subject, body, keywords, subject_keywords),
                        'content_length': len(body),
                        'has_attachments': 'attachment' in str(email_message).lower()
                    }
                    
                    # Add content summary for better relevance
                    if keywords:
                        email_result['matched_keywords'] = self._find_matched_keywords(subject + ' ' + body, keywords)
                    
                    emails.append(email_result)
                    
                    # Stop if we have enough results
                    if len(emails) >= max_results:
                        break
                    
                except Exception as e:
                    print(f"Error processing email {email_id}: {str(e)}")
                    continue
            
            print(f"📧 Final filtered results: {len(emails)}")  # Debug log
            
            # Sort by relevance score (highest first)
            emails.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            mail.logout()
            return emails
            
        except Exception as e:
            raise Exception(f"Failed to search emails: {str(e)}")
    
    def _calculate_relevance(self, subject: str, body: str, keywords: List[str] = None, subject_keywords: List[str] = None) -> float:
        """Calculate relevance score for search results with enhanced subject line priority"""
        score = 0.0
        
        if keywords:
            for keyword in keywords:
                keyword_lower = keyword.lower()
                subject_lower = subject.lower()
                body_lower = body.lower()
                
                # HEAVILY PRIORITIZE SUBJECT LINE MATCHES
                if keyword_lower in subject_lower:
                    if keyword_lower == subject_lower.strip():
                        score += 10.0  # Exact subject match (increased from 5.0)
                    elif subject_lower.startswith(keyword_lower) or subject_lower.endswith(keyword_lower):
                        score += 8.0   # Keyword at start/end of subject
                    else:
                        score += 6.0   # Partial subject match (increased from 3.0)
                    
                    # Extra bonus for payment/financial terms in subject
                    if keyword_lower in ['charge', 'payment', 'receipt', 'invoice', 'transaction', 'billing']:
                        score += 3.0  # Financial terms in subject are highly relevant
                
                # Body matches are secondary now
                body_matches = body_lower.count(keyword_lower)
                if body_matches > 0:
                    score += min(body_matches * 0.3, 1.5)  # Reduced from 0.5 and 2.0 (body less important)
                
                # Keyword appears near beginning of email
                if keyword_lower in body_lower[:200]:
                    score += 0.3  # Reduced from 0.5
        
        if subject_keywords:
            for keyword in subject_keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in subject.lower():
                    score += 8.0  # Increased from 4.0 for specific subject searches
        
        # Check for common subject patterns that indicate receipts/payments
        subject_lower = subject.lower()
        if any(pattern in subject_lower for pattern in ['receipt', 'payment', 'charge', 'invoice', 'your order', 'transaction', 'billing']):
            score += 2.0  # Bonus for payment-related subjects
        
        if any(pattern in subject_lower for pattern in ['from x', 'from twitter', 'x corp', 'x premium']):
            score += 1.5  # Bonus for X/Twitter subjects
        
        # Boost score for emails with substantial content (but less important now)
        if len(body.strip()) > 100:
            score += 0.1  # Reduced from 0.2
        
        return round(score, 2)
    
    def search_by_sender(self, sender: str, days_back: int = 30, max_results: int = 20) -> List[Dict]:
        """Search emails from a specific sender"""
        return self.search_emails(sender=sender, days_back=days_back, max_results=max_results)
    
    def search_by_subject(self, subject_keywords: List[str], days_back: int = 30, max_results: int = 20) -> List[Dict]:
        """Search emails by subject keywords"""
        return self.search_emails(subject_keywords=subject_keywords, days_back=days_back, max_results=max_results)
    
    def search_recent_by_keywords(self, keywords: List[str], days_back: int = 7, max_results: int = 10) -> List[Dict]:
        """Quick search for recent emails with keywords"""
        return self.search_emails(keywords=keywords, days_back=days_back, max_results=max_results)
    
    def _check_sender_match(self, email_sender: str, search_query: str) -> bool:
        """Check if email sender matches search query with precise fuzzy matching"""
        if not email_sender or not search_query:
            return False
        
        # Use a threshold score for matching
        match_score = self._calculate_sender_match_score(email_sender, search_query)
        return match_score >= 4.0  # Require a reasonable match quality
    
    def _calculate_sender_match_score(self, email_sender: str, query: str) -> float:
        """Calculate how well a sender matches the query (0-10 score) - matches conversational agent logic"""
        if not email_sender or not query:
            return 0
        
        sender_lower = email_sender.lower()
        query_lower = query.lower()
        
        # Exact match gets highest score
        if query_lower == sender_lower:
            return 10
        
        # Extract name and email parts
        sender_name = ""
        sender_email = ""
        
        if '<' in email_sender and '>' in email_sender:
            parts = email_sender.split('<')
            sender_name = parts[0].strip().strip('"').lower()
            sender_email = parts[1].split('>')[0].lower()
        else:
            if '@' in email_sender:
                sender_email = sender_lower
                sender_name = sender_email.split('@')[0]
            else:
                sender_name = sender_lower
        
        score = 0
        
        # High score for exact name or email match
        if query_lower == sender_name or query_lower == sender_email:
            score += 8
        
        # Good score for substring matches
        elif query_lower in sender_name or query_lower in sender_email:
            score += 6
        
        # Medium score for word matches
        query_words = query_lower.split()
        sender_words = sender_name.replace('.', ' ').replace('_', ' ').split()
        
        word_matches = 0
        for q_word in query_words:
            if len(q_word) > 2:
                for s_word in sender_words:
                    if q_word == s_word or q_word in s_word or s_word in q_word:
                        word_matches += 1
                        break
        
        if word_matches > 0:
            score += (word_matches / len(query_words)) * 4
        
        # Handle common nickname patterns
        nickname_mappings = {
            'dad': ['father', 'papa', 'pop'],
            'papa': ['dad', 'father', 'pop'],
            'mom': ['mother', 'mama', 'ma'],
            'mama': ['mom', 'mother', 'ma'],
        }
        
        for nickname, alternatives in nickname_mappings.items():
            if query_lower == nickname:
                for alt in alternatives:
                    if alt in sender_lower:
                        score += 7
                        break
            elif query_lower in alternatives and nickname in sender_lower:
                score += 7
                break
        
        # Lower score for very partial matches (only if query is reasonably long)
        if len(query_lower) > 3:
            for q_word in query_words:
                if len(q_word) > 2:
                    if q_word in sender_lower:
                        score += 0.5
        
        return min(score, 10)  # Cap at 10
    
    def _find_matched_keywords(self, content: str, keywords: List[str]) -> List[str]:
        """Find which keywords actually matched in the content"""
        if not keywords:
            return []
        
        content_lower = content.lower()
        matched = []
        
        for keyword in keywords:
            if keyword.lower() in content_lower:
                matched.append(keyword)
        
        return matched 