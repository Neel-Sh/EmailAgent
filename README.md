# Email Agent

A modern AI-powered email management system that can read, summarize, and compose emails using OpenAI.

## Features

- 📧 Read and display recent emails
- 📝 AI-powered email summaries
- ✍️ Compose emails from natural language prompts
- 🎨 Modern, responsive web interface
- 🔒 Secure Gmail integration

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- Gmail account
- OpenAI API key

### 1. Gmail Setup

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
   - Save this password for later

### 2. OpenAI Setup

1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Save this key for later

### 3. Installation

1. Clone and setup backend:
```bash
cd backend
pip install -r requirements.txt
```

2. Setup frontend:
```bash
cd frontend
npm install
```

3. Create environment file:
```bash
cp backend/config_template.env backend/.env
```

4. Edit `backend/.env` with your credentials:
```
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-app-password
OPENAI_API_KEY=your-openai-api-key
```

### 4. Running the Application

1. Start the backend:
```bash
cd backend
python app.py
```

2. Start the frontend:
```bash
cd frontend
npm run dev
```

3. Open http://localhost:3000 in your browser

## Project Structure

```
EmailAgent/
├── backend/           # Python Flask API
│   ├── app.py        # Main Flask application
│   ├── email_service.py  # Email handling logic
│   ├── ai_service.py     # OpenAI integration
│   └── requirements.txt  # Python dependencies
├── frontend/         # React web interface
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/       # Page components
│   │   └── styles/      # CSS styles
│   └── package.json     # Node dependencies
└── README.md
```

## Usage

1. **View Recent Emails**: See your latest emails with AI-generated summaries
2. **Compose Email**: Use natural language to compose and send emails
3. **Daily Summary**: Get an AI summary of your important emails

## Security Notes

- App passwords are stored locally in .env file
- Never commit .env file to version control
- The application runs locally on your machine 