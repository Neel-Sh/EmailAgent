from flask import Flask, request, jsonify
from flask_cors import CORS
from email_service import EmailService
from ai_service import AIService
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure CORS to allow requests from frontend
CORS(app, origins=['http://localhost:3000', 'http://localhost:3001'])

# Initialize services
email_service = None
ai_service = None

def init_services():
    """Initialize email and AI services with environment variables"""
    global email_service, ai_service
    
    try:
        gmail_email = os.getenv('GMAIL_EMAIL')
        gmail_password = os.getenv('GMAIL_PASSWORD')
        openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not all([gmail_email, gmail_password, openai_api_key]):
            raise Exception("Missing required environment variables")
        
        email_service = EmailService(gmail_email, gmail_password)
        ai_service = AIService(openai_api_key)
        
        return True
    except Exception as e:
        print(f"Failed to initialize services: {str(e)}")
        return False

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Email Agent API is running'})

@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """Test email and AI service connections"""
    try:
        if not init_services():
            return jsonify({'error': 'Failed to initialize services'}), 500
        
        # Test email connection
        mail = email_service.connect_imap()
        mail.logout()
        
        return jsonify({
            'status': 'success',
            'message': 'All services connected successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Connection test failed: {str(e)}'}), 500

@app.route('/api/emails/recent', methods=['GET'])
def get_recent_emails():
    """Get recent emails"""
    try:
        if not email_service:
            if not init_services():
                return jsonify({'error': 'Services not initialized'}), 500
        
        hours = request.args.get('hours', 24, type=int)
        max_emails = request.args.get('max', 20, type=int)
        
        emails = email_service.get_recent_emails(hours=hours, max_emails=max_emails)
        
        return jsonify({
            'status': 'success',
            'emails': emails,
            'count': len(emails),
            'timeframe': f'Last {hours} hours'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch emails: {str(e)}'}), 500

@app.route('/api/emails/summary', methods=['GET'])
def get_email_summary():
    """Get AI-generated summary of recent emails"""
    try:
        if not all([email_service, ai_service]):
            if not init_services():
                return jsonify({'error': 'Services not initialized'}), 500
        
        hours = request.args.get('hours', 24, type=int)
        
        # Get emails
        summary_data = email_service.get_email_summary_data(hours=hours)
        
        # Generate AI summary
        summary = ai_service.summarize_emails(summary_data['emails'])
        
        return jsonify({
            'status': 'success',
            'summary': summary,
            'email_count': summary_data['total_emails'],
            'timeframe': summary_data['timeframe']
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate summary: {str(e)}'}), 500

@app.route('/api/emails/compose', methods=['POST'])
def compose_email():
    """Compose an email using AI"""
    try:
        if not ai_service:
            if not init_services():
                return jsonify({'error': 'Services not initialized'}), 500
        
        data = request.get_json()
        prompt = data.get('prompt', '')
        recipient = data.get('recipient', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Generate email using AI
        composed_email = ai_service.compose_email(prompt, recipient)
        
        return jsonify({
            'status': 'success',
            'email': composed_email
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to compose email: {str(e)}'}), 500

@app.route('/api/emails/send', methods=['POST'])
def send_email():
    """Send an email"""
    try:
        if not email_service:
            if not init_services():
                return jsonify({'error': 'Services not initialized'}), 500
        
        data = request.get_json()
        to_email = data.get('to_email', '')
        subject = data.get('subject', '')
        body = data.get('body', '')
        
        if not all([to_email, subject, body]):
            return jsonify({'error': 'to_email, subject, and body are required'}), 400
        
        # Send email
        success = email_service.send_email(to_email, subject, body)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Email sent successfully to {to_email}'
            })
        else:
            return jsonify({'error': 'Failed to send email'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Failed to send email: {str(e)}'}), 500

@app.route('/api/emails/analyze', methods=['POST'])
def analyze_email():
    """Analyze email sentiment and generate quick replies"""
    try:
        if not ai_service:
            if not init_services():
                return jsonify({'error': 'Services not initialized'}), 500
        
        data = request.get_json()
        email_content = data.get('content', '')
        
        if not email_content:
            return jsonify({'error': 'Email content is required'}), 400
        
        # Analyze email
        sentiment = ai_service.analyze_email_sentiment(email_content)
        quick_replies = ai_service.generate_quick_replies(email_content)
        
        return jsonify({
            'status': 'success',
            'analysis': sentiment,
            'quick_replies': quick_replies
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to analyze email: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Email Agent API...")
    print("Make sure to set up your .env file with:")
    print("- GMAIL_EMAIL=your-email@gmail.com")
    print("- GMAIL_PASSWORD=your-app-password")
    print("- OPENAI_API_KEY=your-openai-api-key")
    port = int(os.getenv('FLASK_PORT', 5000))
    print(f"\nAPI will be available at http://localhost:{port}")
    
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('FLASK_PORT', 5000))) 