# Google Play Backend Deployment

This file describes the separate backend stack for the Google Play version of PMapptaro.

## Target

- Remote directory: `/root/PMapptaro`
- Public backend endpoint: `http://185.171.83.116:8022`
- Docker services: `pmapptaro_backend`, `pmapptaro_admin_bot`
- Containers: `pmapptaro_backend`, `pmapptaro_admin_bot`
- Data volume: `/root/PMapptaro/data`
- SQLite database: `/root/PMapptaro/data/pmapptaro.db`
- Runtime temp files: `/root/PMapptaro/temp`
- Logs: `/root/PMapptaro/logs`

This stack must not reuse or stop any RuStore/appslides containers.

## Google Play Credentials

Place the Google Play service-account JSON on the server at:

```text
/root/PMapptaro/data/google-play-service-account.json
```

Inside Docker it is available as:

```text
/data/google-play-service-account.json
```

The backend reads it through:

```text
GOOGLE_PLAY_PACKAGE_NAME=com.apptaro.app
GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=/data/google-play-service-account.json
GOOGLE_PLAY_TEST_MODE=0
```

`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` can be used instead of a file, but the file path is preferred for production.

The deploy script can upload the JSON file safely. The file is not committed to git:

```powershell
python scripts/deploy/deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password "<server-password>" `
  --remote-dir /root/PMapptaro `
  --google-play-service-account-file "C:\path\to\service-account.json"
```

The script validates that the local file is a JSON object, uploads it to:

```text
/root/PMapptaro/data/google-play-service-account.json
```

and sets file permissions to `600`.

## Admin Bot Token

`ADMIN_BOT_TOKEN` must belong to a separate Telegram bot for this Google Play stack.

Do not reuse a token from `/root/apptaro`, `/root/appslides`, `/root/PMappslides`, or any other server project. Telegram allows only one active `getUpdates` polling loop per bot token; if two containers use the same token, the admin bot logs will show:

```text
Conflict: terminated by other getUpdates request
```

The deploy script checks `/root/*/.env` and stops deployment if the same admin bot token is already used by another project.

If the Google Play backend must be updated before a separate admin bot token is ready, use backend-only deploy. It does not start or restart `pmapptaro_admin_bot`, does not install the watchdog, and only rebuilds `pmapptaro_backend`:

```powershell
python scripts/deploy/deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password "<server-password>" `
  --remote-dir /root/PMapptaro `
  --google-play-service-account-file "C:\path\to\service-account.json" `
  --backend-only
```

This mode is temporary. Full Google Play stack completion still requires a unique `ADMIN_BOT_TOKEN` and a normal deploy without `--backend-only`.

## Deploy

From the project root:

```powershell
python scripts/deploy/deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password "<server-password>" `
  --remote-dir /root/PMapptaro
```

The script uploads backend, admin bot, templates, tarot runtime assets, generates remote `.env`, runs Docker Compose, installs an admin-bot heartbeat watchdog, and checks `/v1/health`.

## Health Check

```powershell
Invoke-RestMethod http://185.171.83.116:8022/v1/health
```

Expected:

```json
{"status":"ok"}
```

## Notes

- The Flutter Google Play client is fixed to `http://185.171.83.116:8022`.
- Google Play purchases are verified server-side through `POST /v1/billing/google-play/verify`.
- A repeated Google Play purchase token is idempotent and must not grant readings twice.
- Restore uses the same token verification path and can grant entitlement to a new local `client_id`.
