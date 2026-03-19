# Patient-First Health Advocate Agent

A privacy-first AI health agent .

## What it does

- Monitors heart rate via Google Fit (read-only Token Vault token)
- Alerts you via SMS when vitals exceed thresholds
- Summarizes health trends using Gemini AI — **raw data never stored**
- Books appointments / shares summaries with your doctor — but only after **biometric step-up auth**
- Uses Auth0 Token Vault to manage all OAuth tokens securely

## Auth0 Token Vault usage

| Action | Token type | Step-up required? |
|--------|-----------|-------------------|
| Read heart rate | READ token | No |
| Read medical records | READ token | No |
| Book appointment | WRITE token | Yes (10-min window) |
| Send summary to doctor | WRITE token | Yes (10-min window) |



### Backend

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env
# Fill in your keys in .env
python main.py
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open 

## Project structure

```
health-advocate/
├── backend/
│   ├── main.py          # FastAPI server
│   ├── agent.py         # LLM agent loop
│   ├── vault.py         # Auth0 Token Vault client
│   ├── stepup.py        # Step-up auth (10-min window)
│   ├── watcher.py       # Heart rate polling loop
│   └── tools/
│       ├── google_fit.py
│       ├── fhir.py
│       └── notifier.py
└── frontend/
    └── pages/
        ├── index.tsx        # Dashboard + chat
        ├── settings.tsx     # Connect/disconnect services
        └── stepup/
            └── callback.tsx # Post-biometric redirect
```

## Demo flow (for your video)

1. Show dashboard, connect Google Fit via OAuth
2. Enable watcher — ask "how's my heart rate?"
3. Ask "summarize my week" — LLM responds, no raw numbers
4. Ask "book an appointment with Dr. Smith"
5. Step-up auth triggers → biometric prompt
6. Complete verification → appointment booked
7. Go to Settings → disconnect Google Fit → agent loses access immediately

