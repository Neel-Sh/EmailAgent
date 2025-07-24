import openai
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from email_service import EmailService

class ConversationalEmailAgent:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize email service with credentials from environment
        email_address = os.getenv('GMAIL_EMAIL')
        email_password = os.getenv('GMAIL_PASSWORD')
        
        if email_address and email_password:
            self.email_service = EmailService(email_address, email_password)
            self.has_email_service = True
        else:
            self.email_service = None
            self.has_email_service = False
            
        self.conversation_history = []
        self.email_context = {}
        self.user_profile = {
            "name": "",
            "email": "",
            "writing_style": "professional",
            "common_contacts": {}
        }
    
    def load_email_context(self, hours=48):
        """Load recent emails and extract context"""
        if not self.has_email_service:
            return False
            
        try:
            print(f"🔄 Loading email context from last {hours} hours...")
            # Get more recent emails for better context
            recent_emails = self.email_service.get_recent_emails(hours=hours, max_emails=150)  # Increased from 100
            
            if not recent_emails:
                print("⚠️ No recent emails found")
                return False
                
            print(f"📧 Loaded {len(recent_emails)} recent emails")
            self.email_context = {
                "recent_emails": recent_emails,
                "contacts": self._extract_contacts(recent_emails),
                "conversations": self._identify_conversations(recent_emails),
                "last_updated": datetime.now().isoformat()
            }
            
            return True
        except Exception as e:
            print(f"Error loading email context: {e}")
            return False
    
    def _extract_contacts(self, emails):
        """Extract and analyze contacts from recent emails"""
        contacts = {}
        for email in emails:
            sender = email.get('sender', '')
            if sender and '@' in sender:
                name = self._extract_name_from_email(sender)
                if name not in contacts:
                    contacts[name] = {
                        "email": sender,
                        "last_contact": email.get('date'),
                        "relationship": "colleague"  # Could be enhanced with AI analysis
                    }
        return contacts
    
    def _extract_name_from_email(self, email_address):
        """Extract name from email address"""
        if '<' in email_address:
            name = email_address.split('<')[0].strip().strip('"')
            return name if name else email_address.split('@')[0]
        return email_address.split('@')[0]
    
    def _identify_conversations(self, emails):
        """Group emails into conversation threads"""
        conversations = {}
        for email in emails:
            subject = email.get('subject', '').lower()
            # Simple conversation grouping by subject similarity
            base_subject = subject.replace('re:', '').replace('fwd:', '').strip()
            if base_subject:
                if base_subject not in conversations:
                    conversations[base_subject] = []
                conversations[base_subject].append(email)
        return conversations
    
    def process_message(self, user_message: str) -> Dict:
        """Process user's natural language message and return response"""
        
        # Add user message to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Analyze the user's intent
        intent_analysis = self._analyze_intent(user_message)
        
        if intent_analysis["action"] == "draft_email":
            return self._handle_email_draft(user_message, intent_analysis)
        elif intent_analysis["action"] == "check_inbox":
            return self._handle_inbox_check(user_message)
        elif intent_analysis["action"] == "search_emails":
            return self._handle_email_search(user_message, intent_analysis)
        else:
            return self._handle_general_conversation(user_message)
    
    def _analyze_intent(self, message: str) -> Dict:
        """Analyze user intent using OpenAI"""
        
        system_prompt = """You are an AI assistant that analyzes email-related requests. 
        Classify the user's intent and extract relevant information.
        
        Possible actions:
        - draft_email: User wants to compose/draft an email
        - check_inbox: User wants to see recent emails or inbox status
        - search_emails: User wants to find specific emails
        - reply_email: User wants to reply to a specific email
        - general_conversation: General chat or clarification
        
        Extract for drafting:
        - recipient: who to send to (if drafting)
        - subject_hint: what the email should be about
        - tone: professional, casual, friendly, formal, etc.
        - urgency: high, medium, low
        
        Extract for searching:
        - search_keywords: words to search for in emails
        - search_sender: specific sender to find emails from
        - search_subject: keywords specifically for subject line
        - search_timeframe: recent, last week, last month, etc.
        
        Respond with JSON only."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback simple intent detection
            message_lower = message.lower()
            if any(word in message_lower for word in ["draft", "write", "compose", "send", "email to"]):
                return {
                    "action": "draft_email",
                    "recipient": "",
                    "tone": "professional",
                    "urgency": "medium"
                }
            elif any(word in message_lower for word in ["find", "search", "look for", "show me emails", "emails from", "emails about"]):
                return {
                    "action": "search_emails",
                    "search_keywords": [],
                    "search_sender": "",
                    "search_timeframe": "recent"
                }
            elif any(word in message_lower for word in ["inbox", "recent emails", "new emails", "check email"]):
                return {"action": "check_inbox"}
            return {"action": "general_conversation"}
    
    def _handle_email_draft(self, user_message: str, intent: Dict) -> Dict:
        """Handle email drafting requests"""
        
        # Build context for email drafting
        context_prompt = self._build_email_context_prompt(intent)
        
        system_prompt = f"""You are a professional email assistant. Help the user draft emails based on their natural language requests.

        Context about user's recent emails and contacts:
        {context_prompt}

        Guidelines:
        - Write clear, well-structured emails
        - Match the requested tone
        - Use appropriate greetings and closings
        - Include relevant context if needed
        - Keep it concise but complete

        Respond with JSON containing:
        - "to": recipient email address (guess from context if not specified)
        - "subject": appropriate subject line
        - "body": full email body
        - "tone": detected tone
        - "confidence": how confident you are about the recipient (0-1)
        - "summary": brief summary of what the email is about
        """
        
        conversation_context = self._get_recent_conversation_context()
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Previous conversation: {conversation_context}\n\nNew request: {user_message}"}
                ],
                temperature=0.3
            )
            
            email_draft = json.loads(response.choices[0].message.content)
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": f"I've drafted an email about: {email_draft.get('summary', 'your request')}",
                "timestamp": datetime.now().isoformat(),
                "email_draft": email_draft
            })
            
            return {
                "type": "email_draft",
                "message": f"I've drafted an email for you: **{email_draft.get('summary', 'Email draft ready')}**",
                "email_draft": email_draft,
                "can_send": self.has_email_service
            }
            
        except Exception as e:
            return {
                "type": "error",
                "message": f"Sorry, I had trouble drafting that email. Could you provide more details about who you want to email and what you want to say?",
                "error": str(e)
            }
    
    def _build_email_context_prompt(self, intent: Dict) -> str:
        """Build context about user's emails and contacts"""
        context_parts = []
        
        if self.email_context.get("contacts"):
            contacts_info = []
            for name, info in list(self.email_context["contacts"].items())[:10]:  # Limit to recent contacts
                contacts_info.append(f"- {name}: {info['email']}")
            context_parts.append(f"Recent contacts:\n" + "\n".join(contacts_info))
        
        if self.email_context.get("recent_emails"):
            recent_subjects = []
            for email in self.email_context["recent_emails"][:5]:
                recent_subjects.append(f"- {email.get('subject', 'No subject')} (from {email.get('sender', 'Unknown')})")
            context_parts.append(f"Recent email subjects:\n" + "\n".join(recent_subjects))
        
        return "\n\n".join(context_parts) if context_parts else "No recent email context available."
    
    def _get_recent_conversation_context(self) -> str:
        """Get recent conversation context"""
        recent_messages = self.conversation_history[-5:]  # Last 5 messages
        context = []
        for msg in recent_messages:
            role = "You" if msg["role"] == "user" else "Assistant"
            context.append(f"{role}: {msg['content']}")
        return "\n".join(context)
    
    def _handle_inbox_check(self, user_message: str) -> Dict:
        """Handle requests to check inbox"""
        if not self.has_email_service:
            return {
                "type": "info",
                "message": "📧 I can't access your inbox right now because email credentials aren't configured. Please add your GMAIL_EMAIL and GMAIL_PASSWORD to the backend/.env file to enable inbox access."
            }
            
        if not self.email_context.get("recent_emails"):
            self.load_email_context()
        
        recent_emails = self.email_context.get("recent_emails", [])
        email_summaries = []
        
        for email in recent_emails[:5]:  # Show top 5
            summary = f"**{email.get('subject', 'No Subject')}**\nFrom: {email.get('sender', 'Unknown')}\n_{email.get('date', 'Unknown date')}_"
            email_summaries.append(summary)
        
        inbox_summary = "\n\n".join(email_summaries) if email_summaries else "No recent emails found."
        
        self.conversation_history.append({
            "role": "assistant", 
            "content": f"Here are your recent emails: {len(recent_emails)} total",
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "type": "inbox_summary",
            "message": f"📧 **Your Recent Emails** ({len(recent_emails)} total)\n\n{inbox_summary}",
            "email_count": len(recent_emails)
        }
    
    def _handle_email_search(self, user_message: str, intent: Dict) -> Dict:
        """Handle email search requests with intelligent fuzzy matching"""
        if not self.has_email_service:
            return {
                "type": "info",
                "message": "🔍 I can't search your emails right now because email credentials aren't configured. Please add your GMAIL_EMAIL and GMAIL_PASSWORD to the backend/.env file to enable email search."
            }
        
        try:
            # **REMOVED AUTO-REFRESH FOR SPEED** - only refresh if context is very old
            last_update = self.email_context.get('last_updated')
            if not last_update:
                print("🔄 No email context - loading initial context...")
                self.load_email_context(hours=24)  # Reduced from 72 hours
            else:
                # Only refresh if context is older than 4 hours
                from datetime import datetime, timedelta
                last_update_time = datetime.fromisoformat(last_update)
                if datetime.now() - last_update_time > timedelta(hours=4):
                    print("🔄 Context is old - refreshing...")
                    self.load_email_context(hours=24)
                else:
                    print("✅ Using existing context (fresh enough)")
            
            # Use AI to parse the search request more intelligently
            search_params = self._parse_search_request(user_message, intent)
            
            # **ENHANCED SEARCH WITH STREAMLINED STRATEGIES**
            search_results = self._perform_comprehensive_search(search_params, user_message)
            
            # **FILTER OUT IRRELEVANT RESULTS** for payment queries
            if any(word in user_message.lower() for word in ['charge', 'cost', 'receipt', 'payment', 'how much']):
                search_results = self._filter_payment_relevant_results(search_results, user_message)
            
            if not search_results:
                # Try alternative search strategies
                search_results = self._try_fallback_searches(search_params, user_message)
                if search_results and any(word in user_message.lower() for word in ['charge', 'cost', 'receipt', 'payment']):
                    search_results = self._filter_payment_relevant_results(search_results, user_message)
            
            # **CHECK FOR DIRECT ANSWER REQUESTS**
            direct_answer = self._extract_direct_answer(user_message, search_results)
            
            if not search_results:
                # Create a more specific message based on what was searched
                no_results_msg = "🔍 I couldn't find any emails matching your search"
                suggestions = []
                
                if search_params.get('sender'):
                    no_results_msg += f" from '{search_params['sender']}'"
                    suggestions.extend([
                        f"• Check if '{search_params['sender']}' appears differently in your emails",
                        "• Try searching by their email address instead",
                        "• Try 'show me recent emails' to browse your latest messages"
                    ])
                
                if search_params.get('keywords'):
                    keywords_str = "', '".join(search_params['keywords'])
                    no_results_msg += f" containing '{keywords_str}'"
                    suggestions.extend([
                        "• Try more general keywords",
                        "• Check spelling of search terms", 
                        "• Try searching in a broader timeframe"
                    ])
                
                if not suggestions:
                    suggestions = [
                        "• Try 'show me recent emails' to see your latest messages",
                        "• Use more general terms like 'emails about payments'",
                        "• Check your email credentials are properly configured"
                    ]
                
                suggestion_text = "\n".join(suggestions[:3])  # Limit to 3 suggestions
                
                return {
                    "type": "search_results", 
                    "message": f"{no_results_msg}.\n\n**Suggestions:**\n{suggestion_text}",
                    "results": [],
                    "search_query": search_params
                }
            
            # Format results with summaries and full email capability
            result_summaries = []
            for i, email in enumerate(search_results[:5], 1):  # Reduced from 8 to 5 for better quality
                # Generate unique email ID for full view
                email_id = f"email_{hash(str(email.get('id', i)))}"
                email['view_id'] = email_id  # Store for later retrieval
                
                relevance = email.get('relevance_score', 0)
                relevance_indicator = "🔥" if relevance > 6 else "⭐" if relevance > 3 else "📧"
                
                # Generate AI summary
                summary_text = self._summarize_email(email)
                
                summary = f"{relevance_indicator} **{email.get('subject', 'No Subject')}**\n"
                summary += f"From: {self._clean_sender_name(email.get('sender', 'Unknown'))}\n"
                summary += f"Date: {self._format_email_date(email.get('date', ''))}\n"
                summary += f"Summary: _{summary_text}_\n"
                summary += f"<button class='view-email-btn' data-email-id='{email_id}'>📖 View Full Email</button>"
                
                result_summaries.append(summary)
            
            # Store search results for later retrieval
            self._last_search_results = search_results[:5]
            
            search_summary = self._generate_search_summary(search_params, len(search_results))
            results_text = "\n\n".join(result_summaries)
            
            # **PRIORITIZE DIRECT ANSWER IF FOUND**
            if direct_answer:
                # Clean, direct response first
                response_message = f"✅ **{direct_answer}**\n\n"
                response_message += f"<details><summary>📧 View search details ({len(search_results)} emails found)</summary>\n\n"
                response_message += f"🔍 {search_summary}\n\n{results_text}\n\n</details>"
            else:
                # Standard detailed search results
                response_message = f"🔍 **{search_summary}**\n\n"
                response_message += f"Found {len(search_results)} emails:\n\n{results_text}"
            
            self.conversation_history.append({
                "role": "assistant",
                "content": f"Found {len(search_results)} emails matching search criteria",
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "type": "search_results",
                "message": response_message,
                "results": search_results,
                "search_query": search_params,
                "direct_answer": direct_answer
            }
            
        except Exception as e:
            return {
                "type": "error",
                "message": f"Sorry, I encountered an error while searching your emails: {str(e)}. Please try again with different search terms.",
                "error": str(e)
            }
    
    def _perform_comprehensive_search(self, search_params: Dict, user_message: str) -> List[Dict]:
        """Streamlined fast search with focus on effectiveness"""
        try:
            all_results = []
            print(f"🔍 Fast search with params: {search_params}")
            
            # **PRIORITY Strategy: Today's payment subjects (if user mentions "today" + payment)**
            is_today_payment = (
                any(word in user_message.lower() for word in ['today', 'charged me today']) and
                any(word in user_message.lower() for word in ['charge', 'payment', 'receipt'])
            )
            
            if is_today_payment:
                print("🚀 PRIORITY: Today's payment subject search")
                today_payment_results = self.email_service.search_emails(
                    subject_keywords=['receipt', 'payment', 'charge', 'your receipt', 'transaction'],
                    days_back=1,
                    max_results=10
                )
                print(f"📧 Found {len(today_payment_results)} payment emails in today's subjects")
                # Highest priority boost
                for email in today_payment_results:
                    email['relevance_score'] = email.get('relevance_score', 0) + 10
                all_results.extend(today_payment_results)
                
                # If we found payment results today, also try sender + today combination
                if search_params.get('sender') and today_payment_results:
                    sender_variations = self._get_sender_variations(search_params.get('sender'))
                    for sender_variant in sender_variations[:3]:  # Only try top 3
                        today_sender_results = self.email_service.search_emails(
                            sender=sender_variant,
                            days_back=1,
                            max_results=5
                        )
                        if today_sender_results:
                            print(f"📧 Found {len(today_sender_results)} from '{sender_variant}' today")
                            for email in today_sender_results:
                                email['relevance_score'] = email.get('relevance_score', 0) + 8
                            all_results.extend(today_sender_results)
                            break  # Stop after first successful sender match
            
            # **Strategy 1: Keywords in recent emails (simplified)**
            if search_params.get('keywords') and not is_today_payment:
                print(f"🔍 Keyword search: {search_params.get('keywords')[:3]}")  # Limit logged keywords
                keyword_results = self.email_service.search_emails(
                    keywords=search_params.get('keywords'),
                    days_back=min(search_params.get('days_back', 7), 7),  # Max 1 week for speed
                    max_results=10
                )
                print(f"📧 Found {len(keyword_results)} keyword matches")
                all_results.extend(keyword_results)
            
            # **Strategy 2: Sender search (simplified)**
            if search_params.get('sender') and not is_today_payment:
                print(f"🔍 Sender search: '{search_params.get('sender')}'")
                sender_variations = self._get_sender_variations(search_params.get('sender'))
                
                for sender_variant in sender_variations[:5]:  # Limit to top 5 for speed
                    results = self.email_service.search_emails(
                        sender=sender_variant,
                        days_back=min(search_params.get('days_back', 7), 14),  # Max 2 weeks
                        max_results=8
                    )
                    if results:  # Stop after first successful match
                        print(f"📧 Found {len(results)} from '{sender_variant}'")
                        all_results.extend(results)
                        break
            
            print(f"🔍 Total results: {len(all_results)}")
            
            # Quick deduplication and ranking
            unique_results = self._deduplicate_and_rank(all_results)
            
            print(f"✅ Final results: {len(unique_results)}")
            if unique_results:
                top_result = unique_results[0]
                print(f"📧 Top: '{top_result.get('subject', 'No subject')}' (score: {top_result.get('relevance_score', 0)})")
            
            return unique_results[:10]  # Return top 10 for speed
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def _get_sender_variations(self, sender_query: str) -> List[str]:
        """Get streamlined sender variations - faster and more targeted"""
        variations = [sender_query]
        
        # Streamlined variations for common services
        sender_lower = sender_query.lower()
        
        if sender_lower in ['x', 'twitter']:
            # Only the most common X/Twitter email patterns
            variations = ['X', 'noreply@x.com', 'noreply@twitter.com', 'x.com', 'twitter.com']
        elif sender_lower in ['apple']:
            variations = ['Apple', 'noreply@apple.com', 'apple.com']
        elif sender_lower in ['google']:
            variations = ['Google', 'noreply@google.com', 'google.com']
        else:
            # For other senders, just try a few basic patterns
            if '@' not in sender_query:
                variations.extend([f"noreply@{sender_query.lower()}.com"])
        
        print(f"🔍 Trying {len(variations)} sender variations: {variations}")
        return variations
    
    def _deduplicate_and_rank(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicates and rank by relevance"""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            # Create a unique identifier for the email
            email_id = result.get('id') or f"{result.get('subject', '')}_{result.get('sender', '')}_{result.get('date', '')}"
            
            if email_id not in seen_ids:
                seen_ids.add(email_id)
                unique_results.append(result)
        
        # Sort by relevance score (highest first)
        unique_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return unique_results
    
    def _try_fallback_searches(self, original_params: Dict, user_message: str) -> List[Dict]:
        """Try intelligent fallback search strategies"""
        try:
            # If this was a sender-specific search that failed, don't fall back to keywords
            # The user specifically asked for emails from someone - we shouldn't show random emails
            if original_params.get('sender') and not original_params.get('keywords'):
                # Only try broader timeframe for sender searches
                if original_params.get('days_back', 60) < 120:
                    broader_params = original_params.copy()
                    broader_params['days_back'] = 180  # Expand to 6 months
                    broader_params['max_results'] = 5
                    # Remove search_intent before passing to EmailService
                    broader_params.pop('search_intent', None)
                    fallback_results = self.email_service.search_emails(**broader_params)
                    if fallback_results:
                        return fallback_results
                
                # If still no results, don't fall back to general search
                return []
            
            # For keyword searches, try broader strategies
            if original_params.get('keywords') or original_params.get('subject_keywords'):
                # Strategy 1: Broader timeframe
                if original_params.get('days_back', 30) < 90:
                    broader_params = original_params.copy()
                    broader_params['days_back'] = 120  # Expand to 4 months
                    # Remove search_intent before passing to EmailService
                    broader_params.pop('search_intent', None)
                    fallback_results = self.email_service.search_emails(**broader_params)
                    if fallback_results:
                        return fallback_results
                
                # Strategy 2: Extract alternative keywords from user message
                alt_words = self._extract_searchable_words(user_message)
                if alt_words and alt_words != original_params.get('keywords'):
                    fallback_results = self.email_service.search_emails(
                        keywords=alt_words,
                        days_back=90,
                        max_results=8
                    )
                    if fallback_results:
                        return fallback_results
            
            return []
            
        except Exception as e:
            print(f"Error in fallback searches: {e}")
            return []
    
    def _extract_searchable_words(self, message: str) -> List[str]:
        """Extract meaningful words from user message for broad search"""
        # Remove common words and extract potential keywords
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'for', 'of', 'with', 'by', 'what', 'did', 'he', 'she', 'it', 'sent', 'send', 'me', 'from', 'last', 'week', 'month', 'day', 'find', 'search', 'show', 'emails', 'email', 'anything', 'can', 'you', 'there', 'any'}
        
        # Important travel/business keywords that should always be included
        important_keywords = {'booking', 'details', 'travel', 'flight', 'hotel', 'reservation', 'ticket', 'invoice', 'receipt', 'confirmation', 'itinerary'}
        
        # Common location names (major cities) and specific travel terms
        locations = {'milan', 'paris', 'london', 'tokyo', 'york', 'angeles', 'chicago', 'miami', 'boston', 'seattle', 'francisco', 'rome', 'berlin', 'madrid', 'amsterdam', 'dublin', 'zurich', 'geneva', 'barcelona', 'vienna', 'prague', 'budapest', 'athens', 'istanbul', 'mumbai', 'delhi', 'bangkok', 'singapore', 'sydney', 'toronto', 'montreal', 'vancouver', 'frankfurt'}
        
        # Specific travel and booking terms that should always be included
        travel_terms = {'booking details', 'departure', 'arrival', 'lufthansa', 'booking confirmation', 'itinerary', 'flight confirmation', 'July 2025'}
        
        words = []
        message_text = message.lower()
        
        # First, check for multi-word travel terms
        for term in travel_terms:
            if term in message_text:
                words.append(term)
        
        # Then process individual words
        for word in message_text.split():
            # Clean the word
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word and len(clean_word) > 2:
                # Always include important keywords and locations
                if clean_word in important_keywords or clean_word in locations:
                    words.append(clean_word)
                # Include other meaningful words
                elif clean_word not in common_words:
                    words.append(clean_word)
        
        return words[:5]  # Return top 5 meaningful words (increased from 3)
    
    def _parse_search_request(self, user_message: str, intent: Dict) -> Dict:
        """Enhanced AI-powered search request parsing with better payment/charge detection"""
        
        system_prompt = f"""You are an expert email search assistant. Parse this user request to extract search parameters.

Focus on:
- sender: Extract company/person names (X, Twitter, Apple, Google, etc.)
- keywords: Extract meaningful search terms
- timeframe: Detect urgency indicators like "today", "recent", "this week"
- search intent: Understand what they're looking for

IMPORTANT PATTERNS TO RECOGNIZE:
- "X charged me today" → sender: "X", keywords: ["charge", "payment", "receipt"], days_back: 1
- "How much was the charge" → keywords: ["charge", "payment", "amount", "receipt"], days_back: 3
- "Receipt from Apple" → sender: "Apple", keywords: ["receipt", "payment"], days_back: 14
- "Payment email" → keywords: ["payment", "receipt", "charge", "transaction"], days_back: 7

TIMEFRAME DETECTION:
- "today", "charged me today" → days_back: 1
- "recent", "recently" → days_back: 7  
- "this week" → days_back: 7
- "last week" → days_back: 14
- No timeframe mentioned → days_back: 30

PAYMENT/CHARGE KEYWORDS:
Always include these when user mentions: charge, payment, receipt, invoice, transaction, billing, subscription

Respond with JSON:
{{
    "keywords": ["word1", "word2"],
    "sender": "Company Name or empty",
    "days_back": number,
    "max_results": 15,
    "search_intent": "description"
}}

EXAMPLES:
"X charged me today. How much was the Charge." → {{"sender": "X", "keywords": ["charge", "payment", "receipt", "transaction"], "days_back": 1, "max_results": 15, "search_intent": "find today's charge from X"}}
"emails from ElevenLabs" → {{"sender": "ElevenLabs", "keywords": [], "days_back": 60, "max_results": 15, "search_intent": "find emails from ElevenLabs"}}
"booking details to Milan" → {{"sender": "", "keywords": ["booking details", "Milan", "departure", "Lufthansa"], "days_back": 90, "max_results": 15, "search_intent": "find booking emails about Milan"}}
"flight to Milan" → {{"sender": "", "keywords": ["booking details", "departure", "FRA-LIN", "lufthansa", "july 2025"], "days_back": 120, "max_results": 15, "search_intent": "find flight booking emails to Milan"}}
"when is my flight to Milan" → {{"sender": "Papa", "keywords": ["booking details", "departure", "July", "Lufthansa", "FRA-LIN"], "days_back": 120, "max_results": 15, "search_intent": "find forwarded flight booking emails about Milan"}}

Be generous with keywords extraction, especially for location-based or travel-related searches like "booking details to Milan" should extract ["booking details", "departure", "Milan", "Lufthansa", "FRA-LIN"] and include specific phrases and airline names when relevant
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1
            )
            
            parsed = json.loads(response.choices[0].message.content)
            
            # Enhanced post-processing for better defaults
            if not parsed.get('days_back') or parsed.get('days_back') < 1:
                # Detect timeframe from user message
                message_lower = user_message.lower()
                if any(word in message_lower for word in ['today', 'charged me today', 'received today']):
                    parsed['days_back'] = 1
                elif any(word in message_lower for word in ['recent', 'recently', 'this week']):
                    parsed['days_back'] = 7
                elif any(word in message_lower for word in ['last week']):
                    parsed['days_back'] = 14
                else:
                    parsed['days_back'] = 30  # Default to 1 month
            
            # Ensure we include payment-related keywords for charge/payment queries
            if any(word in user_message.lower() for word in ['charge', 'charged', 'payment', 'receipt', 'invoice', 'billing']):
                payment_keywords = ['charge', 'payment', 'receipt', 'transaction', 'billing', 'invoice']
                existing_keywords = parsed.get('keywords', [])
                for keyword in payment_keywords:
                    if keyword not in existing_keywords:
                        existing_keywords.append(keyword)
                parsed['keywords'] = existing_keywords[:5]  # Limit to 5 keywords
            
            if not parsed.get('max_results'):
                parsed['max_results'] = 15
            
            print(f"🔍 Parsed search: {parsed}")
            return parsed
            
        except Exception as e:
            print(f"Error parsing search request: {e}")
            # Enhanced fallback parsing
            message_lower = user_message.lower()
            
            # Detect timeframe with special handling for travel queries
            days_back = 30
            if any(word in message_lower for word in ['today', 'charged me today']):
                days_back = 1
            elif any(word in message_lower for word in ['recent', 'recently', 'this week']):
                days_back = 7
            elif any(word in message_lower for word in ['last week']):
                days_back = 14
            elif any(word in message_lower for word in ['flight', 'booking', 'travel', 'itinerary', 'milan', 'lin', 'fra']):
                days_back = 120  # 4 months for travel queries
            
            # Extract potential sender names
            sender = ""
            words = user_message.split()
            for i, word in enumerate(words):
                clean_word = ''.join(c for c in word if c.isalnum())
                if clean_word and len(clean_word) > 1:
                    # Check for common company names
                    if clean_word.lower() in ['x', 'twitter', 'apple', 'google', 'meta', 'facebook', 'amazon', 'microsoft', 'paypal', 'stripe', 'lufthansa']:
                        sender = clean_word
                        break
                    # For travel queries, also check for forwarded emails or family names
                    elif clean_word.lower() in ['papa', 'mom', 'dad'] and any(travel_word in message_lower for travel_word in ['flight', 'milan', 'booking']):
                        sender = clean_word
                        break
                    # Check for proper nouns (capitalized)
                    elif word[0].isupper() and clean_word not in {'How', 'What', 'Where', 'When', 'Why', 'The', 'And', 'But'}:
                        sender = clean_word
                        break
            
            # Extract keywords with payment and travel focus
            keywords = self._extract_searchable_words(user_message)
            if any(word in message_lower for word in ['charge', 'charged', 'payment', 'receipt']):
                payment_keywords = ['charge', 'payment', 'receipt', 'transaction']
                for keyword in payment_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                keywords = keywords[:5]
            elif any(word in message_lower for word in ['milan', 'flight', 'booking', 'travel']):
                # Add specific travel keywords for Milan flight queries
                travel_keywords = []
                if 'milan' in message_lower and 'flight' in message_lower:
                    travel_keywords.extend(['booking details', 'departure', 'Lufthansa', 'July 2025', 'FRA-LIN'])
                elif 'milan' in message_lower:
                    travel_keywords.extend(['booking details', 'Milan', 'departure', 'Lufthansa'])
                elif 'flight' in message_lower:
                    travel_keywords.extend(['flight', 'booking details', 'departure', 'Lufthansa'])
                for keyword in travel_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                keywords = keywords[:7]  # Allow more keywords for travel
            
            return {
                "keywords": keywords,
                "sender": sender,
                "days_back": days_back,
                "max_results": 15,
                "search_intent": "fallback search with payment focus" if any(word in message_lower for word in ['charge', 'payment']) else "general search"
            }
    
    def _clean_sender_name(self, sender: str) -> str:
        """Clean up sender name for display"""
        if '<' in sender and '>' in sender:
            # Extract name part before email
            name_part = sender.split('<')[0].strip().strip('"')
            if name_part:
                return name_part
            # Extract email part
            email_part = sender.split('<')[1].split('>')[0]
            return email_part
        return sender
    
    def _format_email_date(self, date_str: str) -> str:
        """Format email date for display"""
        if not date_str:
            return "Unknown date"
        
        try:
            # Try to parse and format the date
            from email.utils import parsedate_to_datetime
            parsed_date = parsedate_to_datetime(date_str)
            
            # Calculate relative time
            now = datetime.now(parsed_date.tzinfo) if parsed_date.tzinfo else datetime.now()
            diff = now - parsed_date
            
            if diff.days == 0:
                return "Today"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            else:
                return parsed_date.strftime("%b %d, %Y")
                
        except:
            return date_str[:20] + "..." if len(date_str) > 20 else date_str
    
    def _generate_search_summary(self, search_params: Dict, result_count: int) -> str:
        """Generate a summary of the search performed"""
        parts = []
        
        if search_params.get('sender'):
            parts.append(f"from {search_params['sender']}")
        
        if search_params.get('keywords'):
            keywords_str = ", ".join(search_params['keywords'])
            parts.append(f"containing '{keywords_str}'")
        
        if search_params.get('subject_keywords'):
            subject_str = ", ".join(search_params['subject_keywords'])
            parts.append(f"with '{subject_str}' in subject")
        
        days_back = search_params.get('days_back', 30)
        if days_back <= 7:
            parts.append("from the last week")
        elif days_back <= 30:
            parts.append("from the last month")
        else:
            parts.append(f"from the last {days_back} days")
        
        search_desc = "Search " + " ".join(parts) if parts else "Email search"
        return f"{search_desc} - {result_count} results"
    
    def _handle_general_conversation(self, user_message: str) -> Dict:
        """Handle general conversation"""
        
        system_prompt = """You are a helpful email assistant. You can help users:
        - Draft and compose emails with natural language prompts
        - Check their inbox and see recent emails  
        - Search and find specific emails by keywords, sender, subject, or timeframe
        - Send emails after review and confirmation
        - Manage email communication efficiently
        
        Examples of what you can do:
        - "Draft an email to John about the project deadline"
        - "Find emails from Sarah about the budget"
        - "Show me recent emails with 'meeting' in the subject"
        - "Search for emails from last week about invoices"
        
        Be friendly and helpful. If they ask about something outside email management, 
        gently guide them back to email-related tasks while being conversational."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            
            assistant_response = response.choices[0].message.content
            
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "type": "conversation",
                "message": assistant_response
            }
            
        except Exception as e:
            return {
                "type": "conversation",
                "message": "Hi! I'm your email assistant. I can help you draft emails, check your inbox, and manage your communications. What would you like to do?"
            }
    
    def send_email(self, email_draft: Dict) -> Dict:
        """Send the drafted email"""
        if not self.has_email_service:
            return {"success": False, "message": "❌ Email sending not available. Please add your GMAIL_EMAIL and GMAIL_PASSWORD to the backend/.env file."}
            
        try:
            success = self.email_service.send_email(
                to_email=email_draft["to"],
                subject=email_draft["subject"],
                body=email_draft["body"]
            )
            
            if success:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": f"✅ Email sent successfully to {email_draft['to']}",
                    "timestamp": datetime.now().isoformat()
                })
                return {"success": True, "message": f"✅ Email sent successfully to {email_draft['to']}!"}
            else:
                return {"success": False, "message": "❌ Failed to send email. Please check your configuration."}
                
        except Exception as e:
            return {"success": False, "message": f"❌ Error sending email: {str(e)}"}
    
    def get_conversation_history(self) -> List[Dict]:
        """Get the conversation history for the frontend"""
        return self.conversation_history[-20:]  # Return last 20 messages
    
    def _summarize_email(self, email: Dict) -> str:
        """Generate an AI-powered summary of an email with focus on key details"""
        try:
            subject = email.get('subject', 'No Subject')
            body = email.get('body', '')[:500]  # Limit body for AI processing
            sender = email.get('sender', 'Unknown')
            
            # Enhanced prompt for better summarization
            prompt = f"""Create a concise 1-2 sentence summary of this email. Focus on:
- For receipts/payments: Extract the exact amount, what was purchased, and when
- For notifications: Main action required or information conveyed  
- For messages: Key purpose or request
- Always include specific numbers, dates, or amounts if present

Email Details:
Subject: {subject}
From: {sender}
Body: {body}

Return only the summary text, no additional formatting or explanations."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3  # Lower temperature for more focused summaries
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Clean up the summary
            if summary.startswith('"') and summary.endswith('"'):
                summary = summary[1:-1]
            
            # If it's a receipt/payment, make sure amount is prominent
            if any(word in subject.lower() for word in ['receipt', 'payment', 'charge', 'invoice']):
                import re
                amount_match = re.search(r'\$[\d,]+\.?\d*', subject + ' ' + body)
                if amount_match and amount_match.group(0) not in summary:
                    summary = f"Payment receipt for {amount_match.group(0)} - {summary}"
            
            return summary
            
        except Exception as e:
            print(f"❌ Error summarizing email: {e}")
            # Fallback to simple extraction
            body_preview = email.get('body', '')[:150].replace('\n', ' ').strip()
            if body_preview:
                return f"{body_preview}..."
            else:
                return "Email preview not available"
    
    def get_full_email(self, email_id: str) -> Dict:
        """Get full email content by ID"""
        try:
            # Find email in recent searches
            search_results = getattr(self, '_last_search_results', [])
            for email in search_results:
                if email.get('view_id') == email_id:
                    return {
                        "success": True,
                        "email": {
                            "subject": email.get('subject', 'No Subject'),
                            "sender": self._clean_sender_name(email.get('sender', 'Unknown')),
                            "date": self._format_email_date(email.get('date', '')),
                            "body": email.get('body', 'No content available')
                        }
                    }
            
            return {
                "success": False,
                "message": "Email not found. Please search again to view emails."
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error retrieving email: {str(e)}"
            }
    
    def _extract_subject_keywords(self, user_message: str, search_params: Dict) -> List[str]:
        """Extract keywords that are particularly relevant for subject line searches"""
        subject_keywords = []
        
        # Get base keywords
        base_keywords = search_params.get('keywords', [])
        
        # Add subject-specific versions
        for keyword in base_keywords:
            subject_keywords.append(keyword)
            
            # Add subject-specific variations
            if keyword.lower() == 'charge':
                subject_keywords.extend(['charged', 'payment', 'receipt'])
            elif keyword.lower() == 'payment':
                subject_keywords.extend(['charge', 'receipt', 'invoice'])
            elif keyword.lower() == 'receipt':
                subject_keywords.extend(['payment', 'charge', 'invoice'])
        
        # Add payment-specific subject terms if user mentions financial terms
        message_lower = user_message.lower()
        if any(word in message_lower for word in ['charge', 'charged', 'payment', 'receipt', 'invoice', 'billing']):
            payment_subject_terms = ['receipt', 'payment', 'charge', 'invoice', 'transaction', 'billing', 'your order']
            for term in payment_subject_terms:
                if term not in subject_keywords:
                    subject_keywords.append(term)
        
        # Add company-specific subject terms
        if search_params.get('sender'):
            sender = search_params.get('sender').lower()
            if sender in ['x', 'twitter']:
                subject_keywords.extend(['X Premium', 'Twitter', 'subscription'])
        
        return list(set(subject_keywords))  # Remove duplicates

    def _filter_payment_relevant_results(self, results: List[Dict], user_message: str) -> List[Dict]:
        """Filter out non-payment related emails for payment queries"""
        if not results:
            return results
        
        filtered_results = []
        payment_indicators = ['receipt', 'payment', 'charge', 'invoice', 'transaction', 'billing', 'subscription', 'order', '$', 'paid', 'purchase']
        
        for email in results:
            subject = email.get('subject', '').lower()
            body = email.get('body', '').lower()
            
            # Skip emails that are clearly not payment-related
            if any(term in subject for term in ['expir', 'domain', 'renewal notice', 'security', 'login', 'verification']):
                # Unless they also have clear payment indicators
                if not any(term in subject for term in payment_indicators):
                    print(f"🚫 Filtered out non-payment email: '{email.get('subject', 'No subject')}'")
                    continue
            
            # Include if it has payment indicators
            if any(term in subject or term in body for term in payment_indicators):
                filtered_results.append(email)
            # Or if it's from a known payment sender
            elif any(sender in email.get('sender', '').lower() for sender in ['noreply@x.com', 'noreply@twitter.com', 'payments@', 'receipts@']):
                filtered_results.append(email)
        
        print(f"📧 Filtered results: {len(results)} → {len(filtered_results)}")
        return filtered_results

    def _extract_direct_answer(self, user_message: str, search_results: List[Dict]) -> str:
        """Extract direct answers to any specific question from search results using AI"""
        if not search_results:
            return ""
        
        message_lower = user_message.lower()
        
        # Check if user is asking a specific question (question words + specific info)
        question_indicators = [
            'how much', 'how many', 'what was', 'what is', 'what did', 'what time', 'when did', 'when was',
            'where is', 'where was', 'who sent', 'who is', 'which', 'why did', 'how did',
            'what\'s the', 'when\'s the', 'who\'s the', 'where\'s the'
        ]
        
        # Also check for direct questions ending with '?'
        is_question = any(indicator in message_lower for indicator in question_indicators) or user_message.strip().endswith('?')
        
        if not is_question:
            return ""
        
        try:
            # Get the most relevant email for answering
            top_result = search_results[0]
            subject = top_result.get('subject', '')
            body = top_result.get('body', '')[:800]  # More content for better answers
            sender = top_result.get('sender', '')
            date = top_result.get('date', '')
            
            # Use AI to extract the specific answer
            prompt = f"""You are answering a specific question about an email. Give a clean, direct answer like a helpful assistant.

USER'S QUESTION: "{user_message}"

EMAIL DETAILS:
Subject: {subject}
From: {sender}
Date: {date}
Content: {body}

Instructions:
- Provide a natural, conversational answer
- For money questions: "They added $X to your account" or "You were charged $X"
- For who questions: "X sent you..." or "The email was from X"
- For when questions: "It was sent on [date]" or "Your flight is on [date]"
- For what questions: "They sent you..." or "It's about..."
- For tracking/order numbers: "Your tracking number is X"
- Keep it conversational and helpful (1-2 sentences max)
- If the information isn't clearly available, return "INFO_NOT_FOUND"

Examples:
- "OpenAI added $5.00 to your account"
- "PacSun sent you a sale notification for 30% off"
- "Your flight to New York is on March 15th at 2:30 PM"
- "John Smith connected with you on LinkedIn"

Answer:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.1  # Very low temperature for precise extraction
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Clean up the answer
            if answer.startswith('"') and answer.endswith('"'):
                answer = answer[1:-1]
            
            # Don't return generic or unclear answers
            if answer in ["INFO_NOT_FOUND", "Not available", "Not specified"] or len(answer) < 3:
                return ""
            
            # Avoid answers that just repeat the question
            if user_message.lower().replace('?', '') in answer.lower():
                return ""
            
            return answer
            
        except Exception as e:
            print(f"❌ Error extracting direct answer: {e}")
            return "" 