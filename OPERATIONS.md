# Operations

## Canonical Workflow

After every large or important change:

1. Run local checks that match the changed area.
2. Commit the project state to Git.
3. Push the current branch to GitHub.
4. If backend files changed, redeploy the server and restart the container.
5. Update the project docs and plan if the runtime flow, deployment flow, or product behavior changed.

## GitHub Repository

- Repository: `https://github.com/NNFall/apptaro`
- Local root: `D:\papka for all\work\PMapptaro`

## Backend Runtime

- Server IP: `185.171.83.116`
- SSH user: `root`
- Remote app dir: `/root/PMapptaro`
- Public backend endpoint: `http://185.171.83.116:8022`
- Docker services: `pmapptaro_backend`, `pmapptaro_admin_bot`
- SQLite database: `/root/PMapptaro/data/pmapptaro.db`

## Standard Git Flow

```powershell
git status -sb
git add .
git commit -m "short meaningful message"
git push -u origin main
```

If work is already on an existing branch:

```powershell
git status -sb
git add .
git commit -m "short meaningful message"
git push
```

## Standard Backend Deploy

```powershell
python scripts\deploy\deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password <SERVER_PASSWORD> `
  --port 22 `
  --remote-dir /root/PMapptaro
```

The deploy script:

- uploads `backend/`, `telegram_admin_bot/`, tarot runtime assets, `docker-compose.yml` and `.env`
- keeps persistent data outside the container
- rebuilds and restarts Docker Compose
- installs host-side cron watchdog for `pmapptaro_admin_bot`
- expects the public port to remain `8022`

## Backend-Only Deploy

Use this only while the Google Play admin bot does not have a unique Telegram token yet, or when intentionally updating only the API service:

```powershell
python scripts\deploy\deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password <SERVER_PASSWORD> `
  --port 22 `
  --remote-dir /root/PMapptaro `
  --google-play-service-account-file <GOOGLE_PLAY_SERVICE_ACCOUNT_JSON> `
  --backend-only
```

This uploads backend/runtime assets, writes `/root/PMapptaro/.env`, uploads the Google Play service-account JSON when provided, rebuilds only `pmapptaro_backend`, and checks `/v1/health`. It does not start `pmapptaro_admin_bot` and does not install or update the admin-bot watchdog.

## Local Validation Before Push

### Backend

```powershell
python -m unittest discover -s backend/tests -v
python -m compileall backend/src
```

### Admin Telegram Bot

```powershell
python -m compileall telegram_admin_bot
python -c "import telegram_admin_bot.main; print('admin bot import ok')"
```

### Flutter App

```powershell
& 'C:\Users\User\develop\flutter\bin\flutter.bat' pub get
& 'C:\Users\User\develop\flutter\bin\flutter.bat' analyze
& 'C:\Users\User\develop\flutter\bin\flutter.bat' test
& 'C:\Users\User\develop\flutter\bin\flutter.bat' build web
& 'C:\Users\User\develop\flutter\bin\flutter.bat' build apk
```

## Notes

- The mobile/web client is hard-wired to `http://185.171.83.116:8022`.
- Local backend URL switching inside the app is intentionally disabled.
- Google Play Billing is the active payment provider for this branch; purchases are verified server-side through `POST /v1/billing/google-play/verify`.
- The Google Play service-account JSON should be stored at `/root/PMapptaro/data/google-play-service-account.json`.
- `GOOGLE_PLAY_PACKAGE_NAME` must be `com.nexwit.tarot`.
- The separate `telegram_admin_bot/` works against the same SQLite database as the backend and uses `client_id` for subscription commands.
- The production compose stack now includes both `pmapptaro_backend` and `pmapptaro_admin_bot`.
- The admin bot now writes heartbeat file `/tmp/admin_bot.heartbeat` after successful `getUpdates`; server cron restarts the container if heartbeat gets stale.
