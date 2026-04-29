# Quickstart: Copilot MCP Wrapper — Teams Transcript Bridge

**Branch**: `003-copilot-mcp-wrapper` | **Date**: 2026-04-05

## Prerequisites

- Python 3.12+
- An Azure Active Directory (Entra ID) app registration with:
  - `CallRecords.Read.All` application permission (granted admin consent)
  - `OnlineMeetings.Read.All` application permission (granted admin consent)
- `uv` or `pip` for dependency management

## 1. Azure App Registration

Create an app registration in the Azure portal (or via Azure CLI):

```bash
az ad app create --display-name "MeetingAgent-CopilotMCP"
az ad app permission add \
  --id <app-id> \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions df021288-bdef-4463-88db-98f22de89214=Role \  # CallRecords.Read.All
                    a7a681dc-756e-4909-b988-f160edc6655f=Role     # OnlineMeetings.Read.All
az ad app permission admin-consent --id <app-id>
az ad app credential reset --id <app-id>  # Note the clientSecret output
```

You will need: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.

## 2. Install Dependencies

```bash
# From repo root
uv sync
# or
pip install -e ".[copilot-mcp]"
```

Core additional dependencies: `msal`, `respx` (test only).

## 3. Configure Environment

```bash
cp .env.example .env
```

Add the following to `.env`:

```
# Azure app registration (required)
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret

# MCP server settings
MCP_HOST=0.0.0.0
MCP_PORT=3001
MCP_TOKEN=your-shared-secret   # Set this and COPILOT_MCP_TOKEN in Meeting Agent to same value

# Transcript lookback window
TRANSCRIPT_LOOKBACK_DAYS=7
```

## 4. Validate Connectivity

Before starting the server, verify your credentials and permissions:

```bash
python -m src.copilot_mcp --validate
```

Expected output:
```
[✓] Azure AD authentication:  OK (token acquired)
[✓] CallRecords.Read.All:      OK (permission verified)
[✓] OnlineMeetings.Read.All:   OK (permission verified)
[✓] Graph API reachability:    OK
All checks passed. Server is ready to start.
```

If a permission is missing:
```
[✗] CallRecords.Read.All:   MISSING — grant this permission in the Azure portal and re-run admin consent
```

## 5. Start the Server

```bash
python -m src.copilot_mcp
```

The server starts on `http://0.0.0.0:3001`. You should see:
```
INFO: Copilot MCP server starting on http://0.0.0.0:3001
INFO: SSE endpoint: http://0.0.0.0:3001/sse
INFO: Health endpoint: http://0.0.0.0:3001/health
```

Verify health:
```bash
curl http://localhost:3001/health
# → {"status": "ok"}
```

## 6. Configure the Meeting Agent

In the Meeting Agent's `.env`, set:

```
COPILOT_MCP_URL=http://localhost:3001
COPILOT_MCP_TOKEN=your-shared-secret   # Same value as MCP_TOKEN above
```

Run a sync to verify transcript ingestion:
```bash
python -m src.workers.sync_worker --run-once
```

Check logs for lines like:
```
INFO: CopilotMCPClient connected to http://localhost:3001/sse
INFO: Ingested transcript for meeting <meeting-id>
```

## 7. Run Tests

```bash
# Unit tests (no credentials required)
pytest tests/unit/copilot_mcp/ -v

# Integration tests (requires real Azure credentials in environment)
COPILOT_MCP_INTEGRATION=1 pytest tests/integration/copilot_mcp/ -v
```

## Troubleshooting

**`[✗] Azure AD authentication: FAILED — AADSTS70011`**: Client secret is wrong or expired. Reset the secret in the Azure portal.

**`[✗] CallRecords.Read.All: MISSING`**: Admin consent was not granted. Go to Azure portal → App registrations → API permissions → Grant admin consent.

**`list_meetings` returns empty list**: Check `TRANSCRIPT_LOOKBACK_DAYS` — if set too low, no meetings fall in window. Also verify the tenant has Teams meetings with recording enabled.

**`get_transcript` always returns null**: Transcription must be explicitly enabled per-meeting or via tenant policy in Teams Admin Center.

**`get_meeting_summary` always returns null**: Requires Microsoft 365 Copilot licence and meeting intelligence enabled. This is expected for unlicensed tenants.
