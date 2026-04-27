# Operations

## Canonical Workflow

After every large or important change:

1. Run local checks that match the changed area.
2. Commit the project state to Git.
3. Push the current branch to GitHub.
4. If backend files changed, redeploy the server and restart the container.
5. Update the project docs and plan if the runtime flow, deployment flow, or product behavior changed.

## GitHub Repository

- Repository: `https://github.com/NNFall/appslides`
- Local root: `C:\Users\User\Desktop\work\appslides`

## Backend Runtime

- Server IP: `185.171.83.116`
- SSH user: `root`
- Remote app dir: `/root/appslides`
- Public backend endpoint: `http://185.171.83.116:8010`
- Docker service: `appslides_backend`

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
  --remote-dir /root/appslides
```

The deploy script:

- uploads `backend/`, `templates/`, `docker-compose.yml` and `.env`
- keeps persistent data outside the container
- rebuilds and restarts Docker Compose
- expects the public port to remain `8010`

## Local Validation Before Push

### Backend

```powershell
python -m unittest discover -s backend/tests -v
python -m compileall backend/src
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

- The mobile/web client is hard-wired to `http://185.171.83.116:8010`.
- Local backend URL switching inside the app is intentionally disabled.
- YooKassa is currently integrated in backend test mode and driven through the chat `/balance` flow.
- Successful payment should now be reflected both on app resume and on later summary/generation checks because the backend auto-syncs unfinished payments.
