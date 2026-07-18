# ASapptaro: выпуск в App Store

Этот runbook относится только к Apple-ветке `codex/apple-app-store`. Он не
изменяет и не использует данные Google Play проекта `/root/PMapptaro`.

## 1. Изоляция production-стека

| Ресурс | Значение |
| --- | --- |
| Серверная папка | `/root/ASapptaro` |
| Docker Compose project | `asapptaro` |
| Backend container | `asapptaro_backend` |
| Admin bot container | `asapptaro_admin_bot` |
| Host port | `8023` |
| SQLite | `/root/ASapptaro/data/asapptaro.db` |
| Apple private key | `/root/ASapptaro/secrets/apple/AuthKey.p8` |
| Apple root certificates | `/root/ASapptaro/secrets/apple/root-certificates` |

Папки `data`, `backups`, `templates`, `tarot`, `temp`, `logs` и `secrets`
находятся вне Docker image. Пересборка контейнеров их не удаляет. Apple `.p8`
и корневые сертификаты смонтированы в backend только для чтения. Docker logs
ограничены тремя файлами по 10 MB для каждого контейнера.

## 2. Что должно быть готово в Apple

1. Активное членство Apple Developer Program.
2. Принятый Paid Applications Agreement, заполненные банковские и налоговые
   данные в App Store Connect.
3. App record с Bundle ID `com.nexwit.tarot`.
4. In-App Purchase key с `Issuer ID`, `Key ID` и единожды скачанным `.p8`.
5. Числовой Apple ID приложения из App Store Connect. Это не Team ID.
6. Одна subscription group и четыре продукта:

| Product ID | Тип | Контент приложения |
| --- | --- | --- |
| `weekly_readings` | Auto-renewable subscription, 1 week | 15 раскладов |
| `monthly_readings` | Auto-renewable subscription, 1 month | 100 раскладов |
| `one10_readings` | Consumable | 10 раскладов |
| `one40_readings` | Consumable | 40 раскладов |

Для каждого продукта нужны локализация, цена, availability и review
information. Первые подписки отправляются на проверку вместе с новой версией
приложения. Apple рекомендует одну subscription group для вариантов одной
подписки: [настройка подписок](https://developer.apple.com/help/app-store-connect/manage-subscriptions/offer-auto-renewable-subscriptions/).

## 3. HTTPS до деплоя

Нужен отдельный публичный домен, например `api.example.com`, с действующим TLS
сертификатом. Reverse proxy принимает `443` и передаёт запросы на
`http://127.0.0.1:8023`. Не используйте IP-адрес или plain HTTP в production
сборке. Порт `8023` желательно закрыть firewall от внешнего доступа и оставить
доступным только локально для reverse proxy.

Проверочный адрес:

```text
https://api.example.com/v1/health
```

URL App Store Server Notifications V2 после реализации Task 8:

```text
https://api.example.com/v1/billing/apple/notifications
```

Укажите HTTPS URL отдельно для Production и Sandbox в App Store Connect.
Apple требует HTTPS и TLS 1.2 или новее:
[App Store Server Notifications V2](https://developer.apple.com/documentation/appstoreservernotifications/app-store-server-notifications-v2).

## 4. Секреты и `.env`

Секреты не коммитятся. Создайте локальный `.env` для Apple deployment. Минимум:

```dotenv
APP_STORE_APPLE_ID=<numeric_app_apple_id>
APP_STORE_KEY_ID=<in_app_purchase_key_id>
APP_STORE_ISSUER_ID=<issuer_uuid>
APP_STORE_PRIVATE_KEY_LOCAL_FILE=<local_path_to_AuthKey.p8>
APP_STORE_ROOT_CERTIFICATES_LOCAL_DIR=<local_path_to_apple_root_certificates>

ADMIN_BOT_TOKEN=<separate_admin_bot_token>
ADMIN_IDS=<telegram_admin_ids>

KIE_API_KEY=<provider_key>
REPLICATE_API_TOKEN=<provider_key_if_used>
```

Deploy-скрипт формирует два отдельных remote-файла: `.env.backend` содержит
только allowlist переменных backend, а `.env.admin` — только параметры admin
bot. Неизвестные переменные и legacy-секреты в production не переносятся.
`ADMIN_BOT_TOKEN` должен отличаться от токенов других запущенных проектов.
Корневые Apple CA скачиваются из официального Apple PKI. Храните `.p8`, `.env`
и сертификаты вне Git, ограничьте доступ к ним владельцем файла.

Deploy-скрипт принудительно выставляет production-пути, Bundle ID,
`APP_STORE_ENABLE_ONLINE_CHECKS=1`, отключает legacy YooKassa и Google Play test
mode. Секретные значения не печатаются в dry-run.

## 5. Локальная проверка и dry-run

Офлайн-проверка структуры, без SSH и без production-секретов:

```powershell
python -m pip install paramiko
python scripts/deploy/deploy_asapptaro_remote.py --local-validate
python scripts/check_asapptaro_deployment.py --local-only
python -m pytest scripts/tests/test_deploy_asapptaro_remote.py -q
```

Dry-run проверяет `.env`, `.p8`, сертификаты и HTTPS URL, но не подключается к
серверу:

```powershell
$env:ASAPPTARO_HEALTH_URL = 'https://api.example.com/v1/health'
python scripts/deploy/deploy_asapptaro_remote.py `
  --dry-run `
  --env-file .env `
  --apple-private-key-file C:\secure\AuthKey_XXXXXXXXXX.p8 `
  --apple-root-certificates-dir C:\secure\apple-roots
```

Plain HTTP health URL в production отклоняется до подключения к серверу.

## 6. Деплой

Рекомендуется SSH key. Пароль можно передать через переменную окружения, но не
записывать в команду или репозиторий.

Сервер обязан заранее присутствовать в пользовательском `known_hosts`; скрипт
отклоняет неизвестный host key. Сначала сверьте SSH fingerprint сервера по
доверенному каналу, затем выполните обычное интерактивное подключение `ssh` и
подтвердите ключ. Не используйте автоматическое принятие неизвестного ключа.

```powershell
$env:ASAPPTARO_REMOTE_HOST = '<server_ip_or_dns>'
$env:ASAPPTARO_REMOTE_USER = 'root'
$env:ASAPPTARO_SSH_KEY_FILE = 'C:\secure\server_ed25519'
$env:ASAPPTARO_SSH_COMMAND_TIMEOUT = '600'
$env:ASAPPTARO_HEALTH_URL = 'https://api.example.com/v1/health'

python scripts/deploy/deploy_asapptaro_remote.py `
  --env-file .env `
  --apple-private-key-file C:\secure\AuthKey_XXXXXXXXXX.p8 `
  --apple-root-certificates-dir C:\secure\apple-roots
```

Скрипт выполняет только следующие действия:

1. Проверяет, что remote path канонически равен `/root/ASapptaro` и не является
   symlink в другую папку.
2. Проверяет Docker, Docker Compose, Python 3 и свободный/собственный порт 8023.
3. Загружает только `backend`, `telegram_admin_bot`, runtime templates/tarot и
   Apple Compose. Flutter app, Git, тесты, `.env` из исходников и кэши не
   загружаются.
4. Загружает явно переданные `.p8`, root certificates и раздельные production
   `.env.backend`/`.env.admin` с правами `0600`; файлы и каталоги сначала
   собираются в staging и заменяются атомарно.
5. Делает согласованный SQLite backup через `sqlite3.Connection.backup` в
   `/root/ASapptaro/backups/asapptaro.db.<UTC timestamp>.bak`.
6. Запускает `docker compose up -d --build --remove-orphans --force-recreate`, чтобы контейнеры
   заново подключили bind mounts после atomic replacements.
7. Ждёт, пока оба контейнера будут одновременно в состоянии
   `running/healthy`; завершившийся или нездоровый admin bot считается ошибкой.
8. Считает деплой успешным только после ответа production HTTPS endpoint с
   `status=ok`, `service=ASapptaro Backend`, `environment=production`.

Backup всех изменяемых deployment-артефактов сохраняются до успешных Compose и внешней HTTPS
health-проверок. В одну транзакцию входят `backend`, `telegram_admin_bot`, `templates`, `tarot`,
Apple root certificates, `docker-compose.yml`, Apple `.p8`, `.env.backend` и `.env.admin`. При
ошибке после любой замены скрипт восстанавливает весь предыдущий набор в обратном порядке и только
затем повторно запускает Compose с `--force-recreate`, чтобы старый stack использовал прежние
config, env, key и заново подключённые bind mounts. Только после полного успеха временные backup
удаляются. Таймаут каждой SSH-команды задаётся через
`ASAPPTARO_SSH_COMMAND_TIMEOUT` или `--command-timeout`; при превышении channel закрывается, а
деплой переходит в rollback.

Проверка на сервере:

```bash
cd /root/ASapptaro
docker compose ps
docker compose logs --tail=200 asapptaro_backend
docker compose logs --tail=200 asapptaro_admin_bot
ls -lh data/asapptaro.db backups/
```

## 7. Сборка на Mac и TestFlight

На Mac нужен поддерживаемый Xcode, Flutter, CocoaPods и доступ к Apple Developer
team. Apple принимает build через Xcode или Transporter; обработанный build
появляется в App Store Connect/TestFlight:
[официальная инструкция upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds).

```bash
git clone <repository-url> ASapptaro
cd ASapptaro
git checkout codex/apple-app-store
cd app
flutter pub get
cd ios && pod install && cd ..
flutter analyze
flutter test
flutter build ipa --release \
  --dart-define=APPLE_BACKEND_BASE_URL=https://api.example.com \
  --dart-define=APPLE_PRIVACY_POLICY_URL=https://example.com/privacy
```

В Xcode откройте `app/ios/Runner.xcworkspace`, выберите правильный Team и
проверьте Bundle ID `com.nexwit.tarot`. Для каждого нового upload увеличивайте
build number. Архив загрузите через Xcode Organizer или `.ipa` через
Transporter.

## 8. Обязательный Sandbox/TestFlight smoke

Проверять нужно сборку, установленную из TestFlight, а не sideload:

1. Backend HTTPS health и V2 notification URL доступны извне.
2. Все четыре продукта загружаются с локализованными ценами Apple.
3. Покупка `weekly_readings` начисляет 15 раскладов ровно один раз.
4. Покупка `monthly_readings` начисляет 100 раскладов ровно один раз.
5. Consumable-покупки 10 и 40 складываются, повторная доставка transaction ID
   не начисляет повторно.
6. Restore Purchases восстанавливает подписку после переустановки.
7. Renewal, expiration, billing retry, refund и revocation приходят через V2
   notification endpoint и корректно отражаются в backend/admin bot.
8. После force close локальная история чата сохраняется.
9. Покупка расходуется при успешном раскладе, а не при ошибке сети/генерации.

Sandbox metadata может обновляться не мгновенно. Не считать релиз готовым,
пока реальная покупка и restore из TestFlight не подтверждены серверной базой и
логами.

## 9. App Review

Перед отправкой заполните privacy labels, age rating, encryption/export
compliance, support URL, privacy URL и review contact. В Review Notes укажите:

- где открыть paywall;
- что входит в каждую подписку и consumable;
- как выполнить Restore Purchases;
- Sandbox test account или другой допустимый способ проверки;
- что расклады имеют развлекательный/информационный характер и не заменяют
  профессиональные медицинские, юридические или финансовые консультации.

## 10. Rollback

1. Не удаляйте `/root/ASapptaro/data`, `backups` или `secrets`.
2. Перед rollback сохраните ещё одну копию текущей базы.
3. Верните проверенный Git commit и повторите deploy тем же скриптом.
4. Если нужна DB rollback, сначала остановите оба контейнера, сохраните текущую
   базу под новым именем, затем восстановите выбранный backup и снова запустите
   Compose:

```bash
cd /root/ASapptaro
docker compose stop
cp -a data/asapptaro.db "backups/asapptaro.db.before-rollback.$(date -u +%Y%m%dT%H%M%SZ).bak"
cp -a backups/asapptaro.db.<UTC timestamp>.bak data/asapptaro.db
chmod 600 data/asapptaro.db
docker compose up -d
```

После rollback снова проверьте внешний HTTPS health, контейнеры, admin bot и
баланс тестового пользователя. Не копируйте БД из `/root/PMapptaro`.
