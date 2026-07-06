# Source Handoff From RuStore Apptaro

Этот документ нормализует переданный текст из старого рабочего чата по созданию RuStore-версии `apptaro`. Он нужен как справка для Google Play этапа.

Важно: этот handoff описывает старый RuStore production-контур. В текущем этапе рабочая локальная папка другая: `D:\papka for all\work\PMapptaro`. Для Google Play backend должен быть отдельным и не должен случайно использовать старую production базу.

## Исходный проект

- Продукт: `apptaro` / `Таро Расклад`.
- GitHub: `https://github.com/NNFall/apptaro`.
- Основная ветка старого проекта: `main`.
- Последний важный commit из handoff: `ef5573e Document production database reset`.

## Старый RuStore production-контур

Эти данные нужны только как справка и как источник осторожности:

- Server IP: `185.171.83.116`.
- SSH user: `root`.
- Старый remote dir: `/root/apptaro`.
- Старый public backend URL: `http://185.171.83.116:8010`.
- Старый docker compose: `/root/apptaro/docker-compose.yml`.
- Старый backend container: `apptaro_backend`.
- Старый admin bot container: `apptaro_admin_bot`.
- Старый SQLite DB: `/root/apptaro/data/appslides.db`.

Для Google Play версии нужно использовать отдельный контур:

- Новый expected remote dir: `/root/PMapptaro`.
- Отдельный compose/service names.
- Отдельный backend port.
- Отдельная DB в `/root/PMapptaro/data/`.
- Отдельный admin bot env/config.

## Секреты

Нельзя коммитить или вставлять в публичные документы:

- SSH password.
- Telegram bot tokens.
- YooKassa secrets.
- AI provider keys.
- Google Play service account JSON.
- Keystore passwords.

Все секреты должны жить в `.env`, `key.properties`, server env или защищенных локальных файлах, которые не попадают в git.

## Старый deploy-процесс RuStore

В старом проекте deploy делался через:

```powershell
python scripts\deploy\deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password <SERVER_PASSWORD> `
  --port 22 `
  --remote-dir /root/apptaro
```

Для Google Play версии этот процесс нельзя использовать без адаптации, потому что он указывает на старый `/root/apptaro`.

Нужен отдельный deploy target:

```powershell
python scripts\deploy\deploy_backend_remote.py `
  --host 185.171.83.116 `
  --user root `
  --password <SERVER_PASSWORD> `
  --port 22 `
  --remote-dir /root/PMapptaro
```

Перед использованием deploy-скрипта нужно проверить, не перезаписывает ли он production `.env` и не переносит ли RuStore/YooKassa настройки в Google Play backend.

## Текущий продуктовый flow

- Пользователь задает вопрос в едином chat UI.
- Backend вытягивает 3 карты: текущая ситуация, препятствие, совет.
- Для нового неоплаченного `client_id` один раз доступен teaser: 1 карта + короткий разбор + предложение открыть полный расклад.
- После оплаты или entitlement показываются оставшиеся 2 карты и продолжение.
- Для пользователя с активным балансом сразу генерируется полный расклад из 3 карт.
- Результат отображается в чате: сначала изображение расклада, затем полный текст.
- TXT-файлы и кнопка файлов из пользовательского flow были убраны.
- История чата сохраняется локально на устройстве.

## Текущий billing в RuStore версии

- Billing сейчас backend-side через YooKassa.
- Flutter не содержит полноценной платежной логики, он открывает ссылку оплаты и делает polling/summary.
- Return URL: `apptaro://billing/return`.
- Offer URL из handoff: `https://dimonk95.github.io/tarobotrustore/`.

Для Google Play версии это нужно заменить:

- Покупка цифрового контента внутри приложения должна идти через Google Play Billing.
- Клиент должен получать purchase token.
- Backend должен проверять purchase token через Google Play Developer API.
- Backend начисляет entitlement/credits только после server-side validation.
- YooKassa должна остаться только для RuStore/внешней версии, не для Google Play build.

## Android состояние из RuStore handoff

- applicationId / namespace: `com.apptaro.app`.
- App label: `Таро Расклад`.
- Flutter version: `0.1.0+6`.
- Release в `build.gradle.kts` на момент handoff подписывался debug signingConfig.

Для Google Play обязательно:

- Настроить нормальный release signing / upload key.
- Не коммитить keystore и пароли.
- Собирать `AAB` через:

```powershell
cd app
flutter build appbundle --release
```

APK helper из RuStore версии:

```powershell
scripts/dev/build_apptaro_apk.ps1
```

Ожидаемые APK outputs:

- `app/build/app/outputs/flutter-apk/apptaro.apk`
- `app/build/app/outputs/flutter-apk/apptaro-v<version>+<build>.apk`

## Google Play обязательные доработки из handoff

1. Настроить release signing:
   - `key.properties`;
   - upload keystore;
   - `build.gradle.kts` release signingConfig;
   - секреты не коммитить.

2. Собрать AAB:
   - `flutter build appbundle --release`.

3. Проверить package/applicationId:
   - текущий: `com.apptaro.app`;
   - если нужен другой package, менять до первой публикации;
   - после публикации package менять нельзя.

4. Проверить Android permissions:
   - `INTERNET` нужен;
   - лишние media/storage permissions должны быть удалены или обоснованы.

5. Убрать cleartext или перейти на HTTPS:
   - текущий URL старого backend: `http://185.171.83.116:8010`;
   - `android:usesCleartextTraffic="true"` для Google Play лучше убрать;
   - production target желательно перевести на `https://...`.

6. Добавить Google Play Billing:
   - Flutter purchase flow;
   - server-side purchase token validation;
   - backend entitlement;
   - silent restore/owned purchase sync.

7. Deep links:
   - старые схемы: `apptaro://billing/return`, legacy `appslides://billing/return`;
   - для Google Play billing могут быть не нужны, но удалять без проверки нельзя.

8. Privacy/Policy:
   - privacy policy URL;
   - disclaimer для tarot/AI entertainment content;
   - отсутствие обещаний гарантированного результата;
   - актуальные ссылки поддержки Telegram/Max, если используются.

## Проверки перед публикацией

```powershell
python -m unittest discover -s backend/tests -v
python -m compileall backend/src telegram_admin_bot
cd app
flutter pub get
flutter analyze
flutter test
flutter build appbundle --release
```

После backend-изменений:

- commit;
- push;
- deploy backend;
- проверить `/v1/health`;
- проверить docker compose ps на сервере;
- проверить admin bot health.

## Что нельзя ломать

- Local transcript persistence.
- Stable `client_id` as installation/user id.
- Backend-side entitlement.
- Admin bot as separate service.
- Deploy process, после адаптации под новый remote dir.
- Tarot image generation/layout.
- Promo codes.
- Payment/entitlement sync.
- Local chat history.

## Ключевые Flutter файлы

- `app/lib/features/chat/chat_screen.dart`
- `app/lib/features/billing/billing_controller.dart`
- `app/lib/data/api/appslides_api_client.dart`
- `app/lib/data/repositories/chat_transcript_repository.dart`
- `app/lib/data/repositories/saved_files_repository.dart`
- `app/lib/app/app_scope.dart`
- `app/lib/core/config/app_config.dart`

## Ключевые backend файлы

- `backend/src/api/presentations.py`
- `backend/src/domain/presentation_outline_service.py`
- `backend/src/domain/presentation_render_service.py`
- `backend/src/domain/presentation_prompts.py`
- `backend/src/domain/tarot_deck.py`
- `backend/src/domain/tarot_layout.py`
- `backend/src/domain/billing_service.py`
- `backend/src/integrations/admin_notifier.py`
- `backend/src/integrations/text_generation.py`
- `backend/src/repositories/storage.py`

## Admin bot

- `telegram_admin_bot/main.py`
- `telegram_admin_bot/handlers/admin.py`
- `telegram_admin_bot/config.py`

## Кодировка старых документов

Часть старых README/планов может выглядеть как mojibake в PowerShell. Это не причина массово переписывать документы. Перед правками нужно проверять содержимое через редактор или git diff и не менять файл только из-за отображения терминала.
