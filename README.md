# Level Advisor

Flask provides the student-account and chat API. The `frontend` folder is a React/Vite interface for registration, login, profile-aware chat, and logout.

## Run locally

1. In one terminal, activate the Python environment and run the backend:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python chat.py
   ```

2. Install Node.js (LTS) if it is not already installed. In a second terminal, start the React interface:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

3. Open `http://localhost:5173`.

## Prepare a Vercel deployment

The Flask app serves the compiled React interface at the deployed root URL. Before each GitHub push that should update the live interface, run this in `frontend`:

```powershell
npm run build
```

This creates `static/react/`, which must be included in the commit. After Vercel redeploys, visit the normal project URL (not port 5173).

## Environment variables

Set these in `.env`:

```text
FLASK_SECRET_KEY=replace-with-a-long-random-value
GROQ_API_KEY=optional-groq-key
```

The local SQLite database is suitable for development. Use a managed database such as Postgres before deploying publicly.
