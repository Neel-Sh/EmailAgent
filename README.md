# Email Agent

A Python/Flask prototype for Gmail reading and AI-assisted email summaries and drafts, with a static HTML/JavaScript interface.

## Current status

The backend and frontend are **not yet integrated into a working end-to-end app**. The frontend calls `/api/chat`, `/api/send-email`, and `/api/get-full-email`, while the backend provides separate `/api/emails/...` routes. The frontend also uses its own origin for API requests, and Flask does not serve its files. There is no React project, `package.json`, or `npm run dev` command in this repository.

## Backend setup

```sh
git clone https://github.com/Neel-Sh/EmailAgent.git
cd EmailAgent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/config_template.env backend/.env
```

Fill the ignored `.env` with `GMAIL_EMAIL`, `GMAIL_PASSWORD` (a Gmail app password), and `OPENAI_API_KEY`. Credential availability and account access must be configured separately. Never commit populated credentials.

Start the API bound to the local machine:

```sh
cd backend
python -m flask --app app run --host 127.0.0.1 --port 5000
```

`GET /api/health` checks that Flask is serving; it does not verify credentials or model access. AI code currently names `gpt-3.5-turbo`; availability for a particular account is not established by a successful local start.

## Frontend preview

From the repository root, in another terminal:

```sh
python3 -m http.server 3000 --bind 127.0.0.1 --directory frontend
```

Open [localhost:3000](http://localhost:3000) to inspect the interface. The route/origin mismatches above must be resolved before its email actions work.

## Data flow

Gmail access uses IMAP/SMTP, and summaries or draft prompts are sent to OpenAI. This is not an offline mail client. The backend has no application authentication layer; treat it as a local prototype. Review drafts and recipients before using any send endpoint.

## Project layout

- `backend/app.py`: Flask routes.
- `backend/email_service.py`: mailbox reads and sending.
- `backend/ai_service.py`: summary, composition, and analysis requests.
- `frontend/`: plain HTML, CSS, and JavaScript.

See [Contributing](CONTRIBUTING.md). No repository-wide license file is included.
