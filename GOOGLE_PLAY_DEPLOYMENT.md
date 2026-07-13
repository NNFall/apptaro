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
GOOGLE_PLAY_PACKAGE_NAME=com.nexwit.tarot
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

The admin bot also logs this case explicitly at runtime:

```text
Admin bot polling conflict: another getUpdates polling process is using the same ADMIN_BOT_TOKEN.
```

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

The script uploads backend, admin bot, compatibility templates, tarot runtime assets, generates remote `.env`, runs Docker Compose, installs an admin-bot heartbeat watchdog, and checks `/v1/health`.

## Health Check

```powershell
Invoke-RestMethod http://185.171.83.116:8022/v1/health
```

Expected:

```json
{"status":"ok"}
```

## Current Server State

Verified on 2026-07-07:

- `/root/PMapptaro` exists.
- `pmapptaro_backend` is running on `0.0.0.0:8022->8000/tcp`.
- `/root/PMapptaro/data/pmapptaro.db` exists.
- `/root/PMapptaro/data/google-play-service-account.json` exists.
- `GET http://185.171.83.116:8022/v1/health` returns `PMapptaro Backend`.
- `pmapptaro_admin_bot` is not running correctly because the configured Telegram bot token is also used by the old `apptaro_admin_bot` container.
- The admin bot logs showed `Conflict: terminated by other getUpdates request`.

Rechecked later on 2026-07-07:

- `pmapptaro_backend` is still running and `/v1/health` returns `{"status":"ok","service":"PMapptaro Backend"}`.
- `pmapptaro_admin_bot` exists but is stopped: `Exited (137)`.
- `docker compose ps` in `/root/PMapptaro` lists only `pmapptaro_backend`.
- Masked token scan confirms `/root/PMapptaro/.env` and `/root/apptaro/.env` still share the same `ADMIN_BOT_TOKEN`.
- This is a deployment configuration blocker, not a backend health blocker.

Reverified on 2026-07-12 after configuring a dedicated Telegram bot token:

- full deploy completed successfully;
- `pmapptaro_backend` is running and serves `/v1/health` on port `8022`;
- `pmapptaro_admin_bot` is running with Docker health status `healthy`;
- the admin bot token uniqueness check passes across server projects;
- the Google Play service-account JSON on the server matches the selected local
  credential file.
- a Telegram delivery test succeeded for admin `7476208806`; admin `190796855`
  must open `@Tarogoogleplaybot` and send `/start` once before Telegram allows
  the bot to set commands or send notifications to that chat.

## Notes

- The Flutter Google Play client is fixed to `http://185.171.83.116:8022`.
- Google Play purchases are verified server-side through `POST /v1/billing/google-play/verify`.
- A repeated Google Play purchase token is idempotent and must not grant readings twice.
- Restore uses the same token verification path and can grant entitlement to a new local `client_id`.
