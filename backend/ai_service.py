from openai import OpenAI
from typing import List, Dict
import os

class AIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
    def summarize_emails(self, emails: List[Dict]) -> str:
        """Generate a summary of recent emails using OpenAI"""
        try:
            if not emails:
                return "No recent emails to summarize."
            
            # Prepare email content for summarization
            email_content = ""
            for email in emails[:10]:  # Limit to 10 most recent for token efficiency
                email_content += f"""
                From: {email['sender']}
                Subject: {email['subject']}
                Date: {email['date']}
                Content: {email['body'][:300]}...
                ---
                """
            
            prompt = f"""
            Please provide a concise summary of these recent emails. Focus on:
            1. Key topics and important information
            2. Action items or urgent matters
            3. Important communications from specific people
            4. Overall email activity overview
            
            Emails to summarize:
            {email_content}
            
            Please format the summary in a clear, organized way with bullet points.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful email assistant that provides clear, concise summaries of email content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Failed to generate email summary: {str(e)}")
    
    def compose_email(self, prompt: str, recipient: str = None) -> Dict[str, str]:
        """Compose an email based on a natural language prompt"""
        try:
            system_prompt = """
            You are an email composition assistant. Given a user's request, compose a professional email.
            
            Instructions:
            1. Generate an appropriate subject line
            2. Write a professional email body
            3. Keep the tone appropriate for the context
            4. Be concise but complete
            5. If no recipient is specified, suggest "RECIPIENT_NEEDED" as the recipient
            
            Return your response in this exact format:
            SUBJECT: [subject line]
            RECIPIENT: [email address or RECIPIENT_NEEDED]
            BODY: [email body]
            """
            
            user_prompt = f"""
            Compose an email based on this request: {prompt}
            {f"Send to: {recipient}" if recipient else ""}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=400,
                temperature=0.5
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse the response
            lines = content.split('\n')
            subject = ""
            suggested_recipient = ""
            body = ""
            
            current_section = None
            for line in lines:
                if line.startswith('SUBJECT:'):
                    subject = line.replace('SUBJECT:', '').strip()
                elif line.startswith('RECIPIENT:'):
                    suggested_recipient = line.replace('RECIPIENT:', '').strip()
                elif line.startswith('BODY:'):
                    current_section = 'body'
                    body = line.replace('BODY:', '').strip()
                elif current_section == 'body':
                    body += '\n' + line
            
            return {
                'subject': subject,
                'recipient': suggested_recipient if suggested_recipient != 'RECIPIENT_NEEDED' else '',
                'body': body.strip()
            }
            
        except Exception as e:
            raise Exception(f"Failed to compose email: {str(e)}")
    
    def analyze_email_sentiment(self, email_content: str) -> str:
        """Analyze the sentiment and importance of an email"""
        try:
            prompt = f"""
            Analyze this email and provide:
            1. Sentiment (Positive/Neutral/Negative)
            2. Urgency level (High/Medium/Low)
            3. Brief category (Work/Personal/Marketing/etc.)
            
            Email content: {email_content[:500]}
            
            Respond in format: Sentiment: X | Urgency: Y | Category: Z
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an email analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return "Unable to analyze email sentiment"
    
    def generate_quick_replies(self, email_content: str) -> List[str]:
        """Generate quick reply suggestions for an email"""
        try:
            prompt = f"""
            Given this email, suggest 3 brief, professional reply options:
            
            Email: {email_content[:300]}
            
            Provide 3 short reply suggestions (one line each):
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an email assistant that suggests quick professional replies."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.5
            )
            
            content = response.choices[0].message.content.strip()
            replies = [line.strip() for line in content.split('\n') if line.strip()]
            
            return replies[:3]  # Ensure we return max 3 replies
            
        except Exception as e:
            return ["Thank you for your email.", "I'll get back to you soon.", "Noted, thanks!"] 