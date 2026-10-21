# AccessAble Backend

FastAPI backend service for AccessAble.

See the root documentation for full setup and development guides:
- [Root README](../README.md)
- [Canonical API Contract](../docs/api_contract.md)
- [Frontend API Integration Guide](../docs/frontend-integration.md)
- [Ring Integration Guide](../docs/ring-integration.md)

### Quick Commands (from `backend/` directory)
```powershell
# Run all tests
pytest

# Initialize SQLite database
python init_db.py

# Run development server
uvicorn app.main:app --reload
```
