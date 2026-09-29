# Vocal dashboard

Next.js 16 app for the Vocal voice agent: browser voice demo, live call monitor, call history,
knowledge base management and the demo customer list.

```bash
cp .env.example .env.local   # points at the FastAPI backend (default http://localhost:8000)
npm install
npm run dev
```

| Route | What it shows |
| --- | --- |
| `/` | Talk to the agent from the browser (ElevenLabs WebRTC) with a live transcript and tool trace |
| `/live` | Calls in progress, streamed over Server-Sent Events |
| `/calls`, `/calls/[id]` | Call history, stats, the agent trace and the ElevenLabs transcript |
| `/knowledge` | Upload and re-index PDFs, and test retrieval |
| `/customers` | Mock Lauki accounts to try the account lookups with |

See the [root README](../README.md) for the full setup.
