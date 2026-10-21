# AccessAble

Accessible smart home event history, notifications, and alert preferences. Built for deaf, hard-of-hearing, and visually impaired users to receive real-time, high-contrast, visual, and audio alerts from home doorbells and cameras.

---

## 1. Quick Start

### Prerequisites
- Python 3.11+ (Python 3.13 supported)
- PowerShell (Windows) or Bash (macOS/Linux)

### Installation
1. Clone the repository and navigate to the backend directory:
   ```powershell
   cd D:\AccessAble\backend
   ```
2. Activate your virtual environment:
   ```powershell
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### Environment Configuration
Copy `.env.example` to `.env` (optional for local SQLite development, as defaults are built in):
```powershell
# Default settings
APP_NAME="AccessAble API"
API_PREFIX="/api/v1"
DATABASE_URL="sqlite:///./accessable.db"
CORS_ORIGINS="http://localhost:5173"
```

### Database Initialization
Initialize all SQLite tables (`events`, `acknowledgements`, `source_connections`, `user_preferences`):
```powershell
python init_db.py
```
*(This script is safe and idempotent to run multiple times without data loss).*

### Starting the Server
Start the local FastAPI development server:
```powershell
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- Service Health: `http://localhost:8000/api/v1/health`

---

## 2. Running Automated Tests

Run the full pytest suite (66 tests covering unit, repository, API, and end-to-end workflows):
```powershell
pytest
```
*Tests use an isolated in-memory SQLite database and never modify the local `accessable.db` file.*

---

## 3. Testing APIs Locally

### Ingest a Demo Event
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/events `
  -H "Content-Type: application/json" `
  -d '{"source": "demo", "event_type": "motion", "occurred_at": "2026-10-21T18:00:00Z", "device_id": "porch-cam", "metadata": {"battery": 92}}'
```

### Ingest an Event with Unique ID (Duplicate Prevention)
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/events `
  -H "Content-Type: application/json" `
  -d '{"source": "ring", "external_event_id": "doorbell-ring-001", "event_type": "doorbell_press", "occurred_at": "2026-10-21T18:05:00Z"}'
```
- First call: `201 Created` (`is_duplicate: false`).
- Resubmitting same `(source, external_event_id)`: `200 OK` (`is_duplicate: true`).

### List Events (Filtered & Paginated)
```powershell
curl.exe "http://127.0.0.1:8000/api/v1/events?source=ring&limit=10"
```

### Acknowledge an Event
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/acknowledgements `
  -H "Content-Type: application/json" `
  -d '{"event_id": 1, "action": "acknowledged", "note": "Checked door feed"}'
```

### Retrieve Acknowledgement History
```powershell
curl.exe "http://127.0.0.1:8000/api/v1/acknowledgements?event_id=1"
```

### Get Accessibility Preferences
```powershell
curl.exe http://127.0.0.1:8000/api/v1/preferences
```

### Update Accessibility Preferences
```powershell
curl.exe -X PUT http://127.0.0.1:8000/api/v1/preferences `
  -H "Content-Type: application/json" `
  -d '{"visual_alerts_enabled": true, "audio_alerts_enabled": true, "high_contrast_enabled": true, "text_scale": "large"}'
```

### Check Ring Integration Status
```powershell
curl.exe http://127.0.0.1:8000/api/v1/integrations/ring/status
```

---

## 4. Documentation References

- **Canonical API Contract**: [`docs/api_contract.md`](docs/api_contract.md)
- **Frontend Integration Guide**: [`docs/frontend-integration.md`](docs/frontend-integration.md)
- **Ring Integration Guide**: [`docs/ring-integration.md`](docs/ring-integration.md)
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`