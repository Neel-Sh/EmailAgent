from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from conversational_agent import ConversationalEmailAgent
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='../frontend', static_url_path='', template_folder='../frontend')
CORS(app)

# Add static file routes manually for better control
@app.route('/styles.css')
def serve_css():
    return app.send_static_file('styles.css')

@app.route('/script.js')
def serve_js():
    return app.send_static_file('script.js')

# Store agent instances per session (in production, use Redis or similar)
agent_sessions = {}

def get_or_create_agent(session_id):
    """Get or create an agent for the session"""
    if session_id not in agent_sessions:
        try:
            agent = ConversationalEmailAgent()
            # Try to load email context, but don't fail if it doesn't work
            try:
                agent.load_email_context()
            except Exception as e:
                print(f"Warning: Could not load email context: {e}")
            agent_sessions[session_id] = agent
        except Exception as e:
            print(f"Error creating agent: {e}")
            raise e
    return agent_sessions[session_id]

@app.route('/')
def index():
    """Serve the chat interface"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get or create agent for this session
        agent = get_or_create_agent(session_id)
        
        # Process the message
        response = agent.process_message(message)
        
        # Add session_id to response
        response['session_id'] = session_id
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'type': 'error',
            'message': 'Sorry, I encountered an error processing your request. Please try again.',
            'error': str(e)
        }), 500

@app.route('/api/send-email', methods=['POST'])
def send_email():
    """Send a drafted email"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        email_draft = data.get('email_draft')
        
        if not session_id or not email_draft:
            return jsonify({'error': 'Session ID and email draft are required'}), 400
        
        if session_id not in agent_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        agent = agent_sessions[session_id]
        result = agent.send_email(email_draft)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }), 500

@app.route('/api/conversation-history', methods=['GET'])
def get_conversation_history():
    """Get conversation history for a session"""
    try:
        session_id = request.args.get('session_id')
        
        if not session_id or session_id not in agent_sessions:
            return jsonify({'history': []})
        
        agent = agent_sessions[session_id]
        history = agent.get_conversation_history()
        
        return jsonify({'history': history})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh-context', methods=['POST'])
def refresh_context():
    """Refresh email context"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id or session_id not in agent_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        agent = agent_sessions[session_id]
        success = agent.load_email_context()
        
        return jsonify({
            'success': success,
            'message': 'Email context refreshed successfully' if success else 'Failed to refresh email context'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error refreshing context: {str(e)}'
        }), 500

@app.route('/api/get-full-email', methods=['POST'])
def get_full_email():
    """Get full email content by ID"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        email_id = data.get('email_id')
        
        if not session_id or not email_id:
            return jsonify({'error': 'Session ID and email ID are required'}), 400
        
        if session_id not in agent_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        agent = agent_sessions[session_id]
        result = agent.get_full_email(email_id)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving email: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Conversational Email Agent is running',
        'active_sessions': len(agent_sessions)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5011))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"🚀 Starting Conversational Email Agent on port {port}")
    print(f"📧 Make sure your .env file has GMAIL_EMAIL, GMAIL_PASSWORD, and OPENAI_API_KEY")
    print(f"💬 Chat interface will be available at http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 