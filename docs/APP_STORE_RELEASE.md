# ASapptaro: выпуск в App Store

## Текущее состояние App Store Connect

На 19 июля 2026 года через App Store Connect API заполнены пять
локализаций (`en-US`, `ru`, `pt-BR`, `fr-FR`, `zh-Hans`), URL политики
конфиденциальности, support/marketing URL, категории, availability во всех
175 странах, review information продуктов и три набора скриншотов:

- `APP_IPHONE_67`: 4 изображения `1320x2868`;
- `APP_IPHONE_55`: 4 изображения `1242x2208`;
- `APP_IPAD_PRO_3GEN_129`: 4 изображения `2064x2752`.

Продукты `weekly_readings`, `monthly_readings`, `one10_readings` и
`one40_readings` находятся в `READY_TO_SUBMIT`. Для каждой подписки
созданы 175 территориальных цен по рекомендованным Apple equalizations.
Первые подписки и первые consumable-покупки нужно добавить в ту же
подачу, что и первая сборка приложения.

Не автоматизируются публичным API Apple: App Privacy (privacy nutrition
labels), выбор первых In-App Purchases вместе с первой сборкой и
финальная отправка на App Review. App Review Contact нельзя создавать без
реального контактного телефона.

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
3. App record с Bundle ID `com.nexwit.tarotreaderai`.
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

Сборка и подпись iOS выполняются только на macOS. Нужны доступ к Apple
Developer team, установленный Xcode 26 или новее с iOS 26 SDK, stable Flutter,
CocoaPods и Python 3.11 или новее. Это соответствует baseline backend image
`python:3.11-slim`. Скрипты не содержат Apple ID, пароли, API keys или signing
certificates и не загружают build автоматически.

### 7.1. Первичная настройка Mac

Клонируйте репозиторий и запустите bootstrap из корня:

```bash
git clone <repository-url> ASapptaro
cd ASapptaro
git checkout codex/apple-app-store
chmod +x scripts/macos/bootstrap_ios.sh scripts/macos/build_testflight.sh
./scripts/macos/bootstrap_ios.sh
```

Bootstrap проверяет macOS, Xcode, iPhoneOS SDK, Flutter, CocoaPods и Python,
безопасно проверяет ветку `codex/apple-app-store`, выполняет `flutter pub get`,
`pod install`, `flutter analyze`, `flutter test` и backend pytest. Если требуется
переключить ветку, а рабочее дерево не чистое, скрипт остановится и ничего не
удалит. Команды `git reset` и `git clean` не используются.

Допускается только Flutter channel `stable`. Зависимости CocoaPods обязательно
фиксируются в `app/ios/Podfile.lock`. Сейчас lock-файл создаётся только на Mac:
если его ещё нет, bootstrap выполнит обычный `pod install`, остановится и
потребует проверить и закоммитить получившийся `Podfile.lock`. Повторный
bootstrap и release build используют `pod install --deployment`; изменение или
отсутствие tracked lock-файла блокирует сборку. Не создавайте `Podfile.lock`
вручную или на Windows.

Откройте `app/ios/Runner.xcworkspace` в Xcode. В `Runner` → `Signing &
Capabilities`:

1. Выберите аккаунт и Apple Developer Team владельца приложения.
2. Включите `Automatically manage signing` либо установите подходящие
   distribution certificate и provisioning profile вручную.
3. Проверьте Bundle ID `com.nexwit.tarotreaderai` для Release.
4. Выполните один запуск или Archive из Xcode, чтобы подтвердить signing.

### 7.2. Production IPA

Backend URL должен быть отдельным production HTTPS origin без пути. Privacy URL
должен открывать публичную страницу политики конфиденциальности по HTTPS. Build
number обязан быть больше `16` из `app/pubspec.yaml` и больше любого номера, уже
загруженного в App Store Connect:

```bash
export APPLE_BACKEND_BASE_URL='https://slide-maker-ai.com:8443'
export APPLE_PRIVACY_POLICY_URL='https://nnfall.github.io/apptaro/privacy.html'
./scripts/macos/build_testflight.sh --build-name 1.0.0 --build-number 22
```

Скрипт отклоняет грязные изменения внутри `app/`, проверяет HTTPS URL, версию,
монотонный build number относительно `app/pubspec.yaml`, Bundle ID, stable
Flutter и tracked `Podfile.lock`. Локальный скрипт проверяет только превышение
номера из pubspec; уникальность номера среди уже загруженных build проверяет App
Store Connect при upload.

Перед сборкой отдельный `release_url_probe.py` разрешает DNS каждого URL и
каждого HTTPS redirect, отклоняет localhost, loopback, private, link-local,
reserved, unspecified и multicast IP. Соединение закрепляется за уже проверенным
публичным IP с TLS hostname verification. Скрипт с ограниченным таймаутом
проверяет `${APPLE_BACKEND_BASE_URL}/v1/health` и требует точный production
контракт: JSON `status=ok`, `service='ASapptaro Backend'` и
`environment='production'`, затем
проверяет privacy URL. Privacy endpoint обязан вернуть 2xx, непустой документ и
документный MIME-тип (`text/html`, `text/plain`, `text/markdown`,
`application/xhtml+xml` или `application/pdf`). Пустой ответ, `204`, бинарный
поток неизвестного типа, HTTP redirect и любой HTTPS downgrade запрещены.

После `flutter pub get` и `pod install --deployment` build-скрипт повторно
проверяет `git status --porcelain -- app`. Любые новые или изменённые tracked и
untracked файлы внутри `app/` блокируют сборку до проверки и коммита зависимостей.

После чистой сборки `flutter build ipa` скрипт распаковывает IPA и сверяет
`CFBundleIdentifier`, `CFBundleShortVersionString` и `CFBundleVersion`, затем
выполняет `codesign --verify --deep --strict`. Встроенный
`embedded.mobileprovision` декодируется через `security cms`; проверяются
distribution profile, срок действия, team/application identifier и
`get-task-allow=false` как в профиле, так и в подписи приложения. Только после
этих проверок выводится сообщение об успешной верификации. Готовый signed IPA
находится в `app/build/ios/ipa/`; путь и SHA-256 печатаются в конце.

### 7.3. Upload

Apple принимает build через Xcode Organizer или приложение Transporter:
[официальная инструкция](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds).

- Xcode Organizer: `Product` → `Archive` → `Distribute App` → `App Store
  Connect` → `Upload`.
- Transporter: войдите Apple ID с доступом к App Store Connect, перетащите
  созданный `.ipa`, нажмите `Deliver`.

После upload дождитесь обработки build в App Store Connect, устраните возможные
ошибки signing/metadata и добавьте build в TestFlight. Credential upload не
автоматизирован намеренно: сессия Apple ID и signing credentials остаются только
на арендованном Mac.

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

Сохраните доказательства для каждого сценария: номер build, Apple transaction
ID, UTC-время, client ID, изменение баланса, backend log и соответствующее
сообщение admin bot. Проверяемые продукты:

| Product ID | Sandbox-доказательство |
| --- | --- |
| `weekly_readings` | Покупка и renewal дают 15 раскладов по одному разу; restore не дублирует выдачу. |
| `monthly_readings` | Покупка и renewal дают 100 раскладов по одному разу; expiration отключает продление. |
| `one10_readings` | Каждая новая consumable transaction добавляет 10; повтор transaction ID идемпотентен. |
| `one40_readings` | Каждая новая consumable transaction добавляет 40; несколько покупок суммируются. |

Внешние блокеры, которые нельзя закрыть локальными тестами Windows:

- доступ к арендованному Mac и поддерживаемому Xcode/iOS SDK;
- Apple Developer Team, distribution signing и provisioning;
- production HTTPS backend/privacy URL и App Store Server Notifications V2;
- созданные и готовые к отправке четыре IAP в App Store Connect;
- принятый Apple signed IPA и обработанный TestFlight build;
- фактические Sandbox purchase/restore/renewal/refund проверки из установки
  TestFlight, подтверждённые backend и admin bot.

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
