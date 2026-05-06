# APPTARO Plan

## Branding + Auto Billing Poll - 2026-05-06

- [x] Запланирован этап: обновить имя приложения на русское, усилить автопроверку оплаты, убрать ручную проверку в UI, проверить сохранение истории.
- [x] Автопроверка оплаты обновлена:
  - `BillingController`: интервал `20 сек`, таймаут `30 минут`;
  - в pending-сообщении убрана рекомендация ручной проверки.
- [x] Кнопка `🔄 Проверить оплату` удалена из pending payment keyboard (оставлены `Оплатить` и `Главное меню`).
- [x] Branding обновлен на `Таро бот`:
  - Android label: `app/android/app/src/main/AndroidManifest.xml`;
  - iOS display/bundle name: `app/ios/Runner/Info.plist`;
  - Flutter app title: `app/lib/app/app.dart`;
  - чатовый заголовок: `app/lib/features/chat/chat_screen.dart`;
  - shared config name: `app/lib/core/config/app_config.dart`.
- [x] Проверено по коду: сохранение истории чата уже активно и не отключалось (`restore` + регулярный `persist` в `chat_screen.dart` + `ChatTranscriptRepository`).
- [x] Новая аватарка подключена из файла `previewtaro.jpg`:
  - сгенерированы Android launcher-иконки `ic_launcher` и `ic_launcher_round` для `mipmap-mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi`;
  - изменения попадут в APK после rebuild.
- [x] Выполнен rebuild APK после обновления аватарки:
  - `app/build/app/outputs/flutter-apk/app-release.apk` успешно собран.

## YooKassa Return-to-App Hardening - 2026-05-06

- [x] Проверен целевой deeplink возврата оплаты: `apptaro://billing/return`.
- [x] Усилена обработка deeplink в Flutter (`/return`, `/return/`, вложенные пути после `/return/`).
- [x] В deploy-скрипт добавлен дефолт `YOOKASSA_RETURN_URL=apptaro://billing/return`, чтобы серверный `.env` всегда включал возврат в приложение.
- [x] Финальный end-to-end тест на устройстве с реальной оплатой и автопереходом обратно в приложение.
  - Скриншоты и UI-дампы: `docs/screenshots/android/2026-05-06_yookassa_return/`.

## Client ID + Image Preview UX - 2026-05-06

- [x] Новый формат `client_id` переключен на короткий вариант 3: `at_<10 hex>`.
- [x] Миграция безопасная: существующие сохраненные `client_id` не перегенерируются.
- [x] В разделе подписки скрыт текст про автопродление через YooKassa.
- [x] Тап по картинке в чате теперь открывает встроенный fullscreen-предпросмотр.
- [x] Fullscreen-предпросмотр: затемнение фона, крестик сверху справа, выход по тапу вне изображения.
- [ ] Проверить на Android устройстве жестами (tap outside / close button / zoom) и приложить скриншоты.

## Promo Redeem + Help Label - 2026-05-06

- [x] Добавлен backend endpoint активации промокода: `POST /v1/billing/promo/redeem`.
- [x] Реализовано списание/учет промокодов в БД с защитой от повторного использования одним пользователем.
- [x] Добавлена команда приложения `/promo XXXXXX` с обновлением баланса после успешной активации.
- [x] В help-флоу показан `ID пользователя` (вместо формулировки `ID устройства`).
- [x] В admin-боте `/genpromo` теперь отдает готовую строку для копирования пользователю: `/promo <code>`.
- [ ] Установить новую APK на подключенный Android и проверить `/promo` в UI.

## Android Full Check + Paid Continuation - 2026-05-06

- [x] Подключен Android-девайс `RF8Y503P4YX` по USB, выполнен повторный end-to-end прогон после последних UX-правок.
- [x] Проверена стабильность install `client_id` после `force-stop` + relaunch:
  - `apptaro_mot46wme_0ca596fdb452e4e4cb` до и после перезапуска одинаковый;
  - префикс `apptaro_`, legacy `appslides_` не используется.
- [x] Проверен first-user сценарий:
  - первый вопрос -> 1 карта + teaser-текст + CTA `🔓 Открыть полный расклад`;
  - изображение приходит сверху текста, отдельной file-плашки `.txt` нет.
- [x] Проверен шаг continuation после появления entitlement:
  - для текущего `client_id` выдан тестовый entitlement в production DB (`plan_key=manual`, `status=manual`, `remaining=15`);
  - повторный `🔓 Открыть полный расклад` запускает продолжение и возвращает 2 карты + полный текст без `Расклад готов`/`Вопрос:`.
- [x] Проверен следующий запрос у пользователя с активным entitlement:
  - сразу формируется полный расклад с изображением из 3 карт;
  - дополнительного teaser/paywall шага нет.
- [x] Скриншоты этого прогона сохранены в `docs/screenshots/android/2026-05-06_flow/` (`13...47`).

## UX Streamline + No-TXT Artifacts - 2026-05-06

- [x] Убрана кнопка `📁 Файлы` из главного меню чата.
- [x] Убрана команда `/files` из пользовательского command flow.
- [x] Убраны промежуточные кнопки `✅ Открыть расклад` / `🔄 Перетянуть` для обычного (не teaser) сценария.
- [x] Обычный сценарий теперь запускает полный рендер автоматически сразу после вопроса.
- [x] Финальное сообщение больше не содержит `✅ Расклад готов` и `Вопрос: ...`.
- [x] Отключено обрезание текста ответа (`reading_text` показывается полностью).
- [x] Удалены TXT-артефакты в backend render service (теперь только `image/jpeg`).
- [x] Убраны фразы про доступные файлы из итогового ответа и paywall-текста.
- [x] Автопроверка статуса оплаты оставлена основной; кнопка `Проверить оплату` сохранена как резервная ручная проверка.
- [x] Усилено автопродолжение teaser-сессии после успешной оплаты (в рамках того же вопроса).
- [ ] Проверить на Android USB финальный сценарий после этих правок и приложить новые скриншоты.

## Android Full Smoke (USB) - 2026-05-05

- [x] Подключен реальный девайс `SM A165F` (`RF8Y503P4YX`), выполнен полный проход на production backend.
- [x] Перезапуск с чистыми данными (`pm clear`) и проверка first-user сценария:
  - первый запрос -> 1 карта + teaser текст + CTA `🔓 Открыть полный расклад`;
  - первая карта отображается сверху текста, не перевернута;
  - отдельная рамка/подпись для картинки не показывается.
- [x] Paywall после `Открыть полный расклад` подтвержден на UI.
- [x] Для теста post-payment шага выставлен временный active entitlement в production DB для текущего `client_id`:
  - `client_id`: `apptaro_mot0xngm_57f9b6429ca05204f7`;
  - `plan_key=monthly_100`, `status=active`, `remaining=100`.
- [x] На устройстве подтвержден шаг `Проверить оплату` -> сообщение `Оплата прошла успешно`, лимит `100`.
- [x] Повторный платный запрос после активации проверен:
  - сначала приходит промежуточный блок с 3 позициями и кнопками `✅ Открыть расклад / 🔄 Перетянуть / ↩ Отмена`;
  - после `✅ Открыть расклад` приходит полный результат с горизонтальным изображением из 3 карт + полный текст и TXT-файл.
- [x] Скриншоты сохранены: `docs/screenshots/android/2026-05-05_fullcheck_valid/`.
- [ ] Расхождение с целевым UX (как в telegram reference) пока остается:
  - для платного пользователя есть промежуточный шаг `Открыть расклад` вместо сразу финального полного расклада после отправки вопроса.

## apptaro Tarot Flow Fixes - 2026-05-05

- [x] Reworked teaser -> paid continuation domain flow on backend:
  - `PresentationRenderRequest` extended with `teaser_first_text`;
  - API `/v1/presentations/render` and `/v1/presentations/jobs` pass continuation context;
  - render service now supports continuation mode when paid render starts from 1-card teaser;
  - continuation mode now draws 2 new cards (positions 2 and 3), generates continuation text, and returns image+txt artifacts.
- [x] Fixed first-card orientation for teaser:
  - teaser outline generation now forces upright first card (`rev=0`);
  - teaser single-card renderer no longer rotates image by reverse flag.
- [x] Added dedicated continuation text generation path:
  - `generate_tarot_continuation(...)` added in text generation client;
  - continuation prompt wiring uses `tarot_continuation_prompt(...)`.
- [x] Fixed prompt layer quality/parity:
  - rebuilt `backend/src/domain/presentation_prompts.py` in clean UTF-8;
  - kept Telegram-bot prompt structure (`teaser/full/followup/continuation`);
  - added strict anti-substitution constraints: model must use only provided cards/orientation.
- [x] Added server-side protection against card substitution in fallback paths:
  - tarot text output is validated against expected cards from `cards_block`;
  - if model output uses wrong cards, backend returns deterministic safe fallback bound to provided cards.
- [x] Updated Flutter chat image UX to match requested behavior:
  - tarot images render above text in message bubble;
  - removed separate framed preview card/caption block for image attachments;
  - changed image fit to `BoxFit.contain` to avoid heavy cropping of horizontal spreads.
- [x] Kept platform invariants unchanged:
  - transcript persistence untouched;
  - YooKassa billing flow untouched on client/server responsibility split;
  - separate Telegram admin bot untouched;
  - deploy/workflow files untouched by this iteration.
- [x] Validation runs:
  - `python -m compileall backend/src` (pass);
  - `python -m unittest discover -s backend/tests -v` (pass);
  - `flutter analyze` (pass);
  - `flutter test` (pass);
  - local scripted smoke for teaser/continuation/full render paths (pass).
- [x] Prompt smoke with Russian sample questions executed via current text generation client.
  - Observation: primary text endpoint intermittently returns maintenance error;
  - fallback path now enforces provided cards, preventing random-card substitutions in user output.
- [ ] Android USB screenshot smoke from this workstation is currently blocked:
  - `flutter devices` sees only Windows/Chrome/Edge;
  - `adb` is not available in PATH in this shell session.

## apptaro Hotfix - 2026-05-04 (client_id + teaser flow)

- [x] Investigate repeated admin `new user` notifications on every app reopen.
- [x] Root cause found: race in `ClientSessionRepository.restore()` could return before restore finished, causing a new `client_id` to be generated.
- [x] Fix repository restore synchronization via `_restoreFuture` and persist ID exactly once.
- [x] Switch installation key prefix from `appslides_` to `apptaro_`.
- [x] Add legacy migration: read old key `appslides.client_id.v1`, convert once, save under `apptaro.client_id.v1`, remove legacy key.
- [x] Send both headers from Flutter client: `X-Apptaro-Client-Id` (new) + `X-AppSlides-Client-Id` (legacy compatibility).
- [x] Update backend dependency parser to prefer `X-Apptaro-Client-Id` and still accept legacy header.
- [x] Align teaser UX to Telegram reference:
  - teaser mode shows CTA block with one button `🔓 Открыть полный расклад`;
  - non-teaser mode keeps full outline + `Открыть расклад`/`Перетянуть` flow.
- [x] Align LLM tarot prompts with `telegram_taro_bot/prompts/tarot_prompts.py`:
  - split `teaser` / `full` instruction styles;
  - keep Telegram-markdown output format requirement;
  - keep safety clause for medical/legal/death topics;
  - keep explicit teaser CTA instruction.
- [x] Run Flutter/backend checks after hotfix:
  - `flutter analyze` (pass)
  - `flutter test` (pass)
  - `python -m compileall backend/src` (pass)
  - `python -m unittest discover -s backend/tests -v` (pass)
  - `flutter build apk --release` (pass, artifact rebuilt)
- [~] Real Android verification in progress (`SM A165F`):
  - release/debug APK installed successfully via `flutter install`;
  - app launch + local storage probe done (`SharedPreferences DataStore` parsed from device);
  - confirmed stable value across restart: `apptaro.client_id.v1` remains identical after `force-stop` + relaunch.
  - API-level first-user mechanism verified in isolated backend smoke (`should_show_trial_teaser=True` for new client, then `False` after trial mark).
  - teaser/paywall visual smoke still recommended manually in UI.
- [x] Commit + push hotfix branch to `https://github.com/NNFall/apptaro`.
- [x] Redeploy backend on `/root/apptaro` after backend validation.
- [x] Live production smoke (`http://185.171.83.116:8010`) for first-user mechanism:
  - request #1 with fresh `client_id` -> `teaser_mode=true`, `outline=1`, teaser artifact present;
  - request #2 with same `client_id` -> `teaser_mode=false`, `outline=3`, teaser artifact absent.
- [x] Compare `backend/src/domain/presentation_prompts.py` with `telegram_taro_bot/prompts/tarot_prompts.py` and close prompt parity gaps:
  - keep platform presentation prompts (`title/outline/revise/slides`);
  - add missing telegram-style tarot prompt blocks for events (`followup`, `continuation`);
  - add helper texts (`teaser_intro_text`, `paywall_text`, `confirmation_text`) for reuse.
- [x] Validate prompt-layer refactor: `python -m compileall backend/src` and `python -m unittest discover -s backend/tests -v` passed.

## apptaro Product Adaptation - 2026-05-03

- Новый активный продукт: `apptaro`.
- Источник предметной логики: `telegram_taro_bot/`.
- Платформенный shell сохранен: Flutter chat UX, local transcript persistence, local saved files, `client_id`, FastAPI backend, YooKassa billing, Telegram admin bot, deploy workflow.
- Product mapping:
  - `presentation topic` -> вопрос пользователя к таро;
  - `outline` -> три карты: ситуация, препятствие, совет;
  - `template/design` -> скрытое compatibility-поле, не пользовательский шаг;
  - `render job` -> генерация текстового разбора и JPG/TXT artifacts;
  - `generations` -> расклады в пользовательских и admin-формулировках.
- Выполнено:
  - [x] изучены `PRODUCT_ADAPTATION_GUIDE.md`, `IMPLEMENTATION_RULES.md`, `AGENT_HANDOFF.md`, `OPERATIONS.md`, `APPTARO_PLAN.md`, `README.md`, `app/README.md`, `backend/README.md`;
  - [x] изучен `telegram_taro_bot/` как источник текстов, prompts, сценариев, платежных сущностей и tarot assets;
  - [x] адаптирован Flutter chat flow под вопрос, три карты, подтверждение, paywall и результат расклада;
  - [x] адаптирован backend domain layer под tarot deck/layout/reading generation;
  - [x] добавлены JPG/TXT artifacts и download routes;
  - [x] обновлены billing/admin формулировки под расклады;
  - [x] обновлены README-документы под `apptaro`.
- Сохраненное ограничение:
  - presentation endpoint names пока не переименованы, чтобы не ломать клиент, billing flow и deploy-интеграции.

### GitHub / Deploy Actions

- [x] Проверить текущий remote перед переносом в новый репозиторий.
- [x] Проверить реальные `.env` и tracked `.env.example` перед push.
- [x] Обновить README и backend `.env.example` под `apptaro`.
- [x] Запустить Flutter APK build после web/analyze/test; результат: timeout after 10 minutes, fresh APK не получен.
- [x] Остановить Gradle daemon после timeout.
- [x] Добавить ignore-правила для `telegram_taro_bot` runtime DB/temp и `app/android/.kotlin/`.
- [x] Повторить fresh APK build отдельно, если нужен installable артефакт именно этого commit.
- [x] Перенастроить `origin` на `https://github.com/NNFall/apptaro.git`.
- [x] Создать commit с текущим состоянием `apptaro`: `d1d6fe2 Adapt platform to apptaro`.
- [x] Push в пустой GitHub repository `NNFall/apptaro`.
- [x] Проверить возможность backend deploy по `OPERATIONS.md`.
- [x] Получен серверный пароль от владельца проекта для текущего deploy-сеанса.
- [x] Обновить deploy script под `/root/apptaro`, `telegram_taro_bot/.env`, `backend/runtime/tarot` и новые compose services `apptaro_*`.
- [x] Добавить остановку legacy контейнеров `appslides_backend` / `appslides_admin_bot` при миграции на `apptaro`.
- [x] Commit/push deploy-script обновлений перед выкладкой: `69b2f3c Update apptaro backend deploy`.
- [x] Выполнить backend deploy в `/root/apptaro`.
- [x] Проверить remote health `http://185.171.83.116:8010/v1/health`: `{"status":"ok","service":"apptaro Backend","environment":"production","version":"0.1.0"}`.
- [x] Проверить занятость порта `8010`: порт слушает `docker-proxy` для `apptaro_backend`, это ожидаемое состояние.
- [x] Live-smoke production API: `GET /v1/templates/presentation` -> `200`, `POST /v1/presentations/outline` -> `200`, paid job без баланса -> `402 Payment Required`.
- [x] Найден security issue в backend logs: `httpx` INFO-лог раскрывает полный Telegram Bot API URL.
- [x] Заглушить `httpx/httpcore` INFO logs, чтобы Telegram token не попадал в Docker logs.
- [x] Commit/push logging fix: `e76cfb4 Suppress token-bearing http client logs`.
- [x] Redeploy backend после logging fix.
- [x] Проверить production logs после live outline: `httpx` request logs и Telegram Bot API URL больше не появляются.

### Admin Bot Token / UTF-8 Follow-up - 2026-05-04

- [x] Получено указание: локальный `telegram_admin_bot/.env` обновлен владельцем проекта, production должен забрать новый `ADMIN_BOT_TOKEN`.
- [x] Проверить гипотезу по `???` в вопросе: PowerShell smoke отправлял JSON не как явный UTF-8; Python UTF-8 request возвращает корректную кириллицу от production API.
- [x] Redeploy `/root/apptaro`, чтобы production `.env` получил новый `ADMIN_BOT_TOKEN`.
- [x] Проверить production health и admin bot контейнер после redeploy: health `ok`, `apptaro_admin_bot` Up, `ADMIN_BOT_TOKEN` присутствует в remote `.env` без вывода секрета.
- [x] Fresh APK build выполнен: `app/build/app/outputs/flutter-apk/app-release.apk`, `52271468` bytes, `2026-05-04 11:29:20`.
- [x] Проверить новый admin bot token через Telegram `getMe` без вывода секрета: `ok`, username `demoliveapi_bot`.
- [x] Android device/emulator check: подключенного Android-девайса нет, `flutter emulators` не видит AVD, создать `apptaro_smoke` нельзя из-за отсутствия Android system image.
- [x] Защитить Flutter API client от повторения `???`: JSON request body теперь отправляется явными UTF-8 bytes с `Content-Type: application/json; charset=utf-8`.
- [x] Повторить Flutter analyze/test/APK build после UTF-8 fix: `flutter analyze`, `flutter test`, `flutter build apk` passed.
- [x] Финальный APK после UTF-8 fix: `app/build/app/outputs/flutter-apk/app-release.apk`, `52271468` bytes, `2026-05-04 11:35:20`.
- [x] Commit/push UTF-8 fix: `abc1006 Send Flutter API JSON as UTF-8`.
- [x] Android emulator smoke executed on AVD `apptaro_smoke` after installing `system-images;android-35;default;x86_64`; APK installed from `%TEMP%/apptaro-app-release.apk`.
- [x] Emulator launch passed: package `com.appslides.appslides` starts, app header shows `apptaro`, Russian UI renders correctly, no fatal crash in logcat.
- [x] Production outline smoke from emulator passed: chat request reaches `http://185.171.83.116:8010`, tarot outline is returned in Russian, action buttons `Открыть расклад` / `Перетянуть` / `Отмена` are shown.
- [x] Temporary Android disk cleanup performed for smoke: deleted rebuildable `app/build`/Gradle caches and uninstalled Android NDK `ndk;28.2.13676358`; reinstall NDK if future native Android builds require it.
- [x] Rename Android package/application id from legacy `com.appslides.appslides` to release id `com.apptaro.app`; keep legacy `appslides://billing/return` as a compatible billing return scheme alongside `apptaro://billing/return`.
- [x] Update Android application label to `apptaro` and remove remaining user-visible AppSlides wording from settings.
- [x] Rename iOS bundle id/display name to `com.apptaro.app` / `apptaro` and register `apptaro` + legacy `appslides` URL schemes for billing return.
- [x] Validate package rename: `flutter analyze` passed, `flutter test` passed, `flutter build apk` passed after rebuilding Gradle cache.
- [x] APK metadata verified with `aapt`: package `com.apptaro.app`, label `apptaro`, launchable activity `com.apptaro.app.MainActivity`, URL schemes `apptaro` and `appslides`.
- [x] Android NDK `28.2.13676358` was reinstalled automatically during APK build; Gradle daemon stopped and rebuildable Gradle `8.14.4` cache removed afterward to recover disk space.
- [x] Продолжить mobile smoke на устройстве или эмуляторе, когда появится Android target.
- [x] Added backend trial-teaser gating on `client_id`: one-card teaser is available once for a new unpaid client, then disabled for next questions.
- [x] Added `teaser_mode` payload to outline API response with optional `teaser_text` and teaser image artifact.
- [x] Full reading flow remains a 3-card spread image (`JPG`) + text analysis (`TXT`) after paywall and successful entitlement check.
- [x] Flutter chat now renders tarot image artifacts inline in the message feed (not only as file tiles).
- [x] Real-device Android smoke on `SM_A165F` (USB): first question returned one-card teaser + image preview; second question in the same install returned standard 3-card outline (trial consumed).
- [ ] Real-device post-payment smoke for "open full spread" is pending a completed payment or manual entitlement for that exact device `client_id`.

## Документация для повторного использования продукта - 2026-05-03

- Зафиксировано новое продуктовое требование:
  - текущий репозиторий `appslides` должен использоваться не только как один продукт, но и как переиспользуемый каркас приложения для других AI-ниш;
  - в будущем на той же платформе могут собираться продукты под Таро, генерацию изображений/видео, песни и другие chat-driven AI-сценарии;
  - следующему агенту может передаваться уже другая папка Telegram-бота как источник предметной логики, а текущий Flutter/backend/admin/deploy-каркас должен оставаться базой.
- В этом проходе задача по документации выполнена:
  - [x] вынесен отдельный адаптационный гид вместо перегрузки backend/frontend README;
  - [x] вынесен отдельный файл с правилами реализации и платформенными инвариантами;
  - [x] вынесен отдельный handoff-файл для следующей нейросети или разработчика.
- Новый handoff-пакет:
  - `PRODUCT_ADAPTATION_GUIDE.md`
  - `IMPLEMENTATION_RULES.md`
  - `AGENT_HANDOFF.md`
- Как использовать:
  - прикладывать папку нового Telegram-бота по нужной нише;
  - прикладывать новые handoff-документы из этого репозитория;
  - ставить следующему агенту задачу сохранить платформенный shell и заменить только product/domain-слои.

## Admin Telegram Bot Pivot - 2026-04-30

- Product decision is fixed:
  - admin access for `appslides` will not be built inside the Flutter app;
  - admin access will be moved into a separate Telegram bot for admins;
  - access control must stay ENV-based through Telegram user IDs;
  - runtime admin whitelist must support both:
    - static IDs from `.env`;
    - dynamic extra admins stored in the database, matching the legacy bot behavior.
- Source of truth for admin behavior is the legacy Telegram bot code, not a newly invented panel UX.
- Legacy admin command set already identified from `telegrambot/main.py` and `telegrambot/handlers/admin.py`:
  - `/botstats`
  - `/adstats`
  - `/adstats_all`
  - `/adtag`
  - `/tag`
  - `/sub_on`
  - `/sub_off`
  - `/sub_check`
  - `/sub_cancel`
  - `/genpromo`
  - `/admin_add`
  - `/admin_del`
  - `/admin_list`
  - `/templates`
  - `/template_set`
- Migration requirement:
  - preserve command names;
  - preserve command semantics;
  - preserve admin-only access checks;
  - preserve message formatting where it is still useful;
  - preserve template-management flow, including file upload state for `/template_set`;
  - preserve promo/deeplink logic for ad tags and promo codes where applicable.
- Expected admin bot scope:
  - bot statistics;
  - traffic-tag statistics;
  - manual subscription/token operations;
  - subscription inspection/cancelation;
  - promo generation;
  - admin list management;
  - template download/replacement;
  - backend-driven admin notifications from product events.
- Planned implementation shape:
  - separate `telegram_admin_bot/` package;
  - `aiogram`-based runtime;
  - isolated config via `.env`;
  - direct integration with the active `appslides` backend database/service layer;
  - no coupling to the mobile UI.
- Completed in the current pass:
  - [x] separate `telegram_admin_bot/` package created;
  - [x] ENV-based super-admin access retained through `ADMIN_IDS`;
  - [x] dynamic DB-based extra-admin support restored through `admins` table;
  - [x] legacy admin command names restored in the new bot;
  - [x] `sub_on`, `sub_off`, `sub_check`, `sub_cancel` adapted to `client_id` instead of Telegram `user_id`;
  - [x] template listing and upload-replacement flow restored;
  - [x] promo code creation restored on the new backend schema;
  - [x] ad-tag schema and tag-statistics support restored for the new backend database;
  - [x] shared admin schema added into the main `appslides` SQLite storage;
  - [x] admin bot dockerized and added into the production compose stack;
  - [x] admin bot deployed on `185.171.83.116` together with backend.
  - [x] backend event notifications restored into the admin Telegram bot for:
    - new client first seen;
    - outline created;
    - outline updated by comment;
    - YooKassa payment success;
    - manual renewal success/failure;
    - auto-renew success/failure with payment status and payment id;
    - subscription cancel;
    - presentation generation success/failure;
    - file conversion success/failure.
- Next required study before implementation:
  - inspect each admin handler end-to-end against the current `appslides` backend schema;
  - map old Telegram `user_id` logic to current mobile `client_id` world where needed;
  - decide which admin commands must operate on `client_id`, which on payment/subscription records, and which need helper lookup commands first.

## Concurrent Generation Note - 2026-04-30

- Clarified requirement:
  - the goal is not just "make one request async";
  - the real goal is to let several users generate presentations in parallel without one user waiting for the full completion of another.
- Current backend already has partial concurrency:
  - `POST /v1/presentations/jobs` creates a background job instead of blocking the client;
  - each presentation job is started in its own Python thread;
  - slide image generation inside one presentation already runs with bounded parallelism through `asyncio.gather(...)` and `Semaphore(image_concurrency)`;
  - outline generation already parallelizes `title + outline`;
  - file conversion also runs as a background job.
- Current limitation:
  - provider calls are wrapped with `asyncio.to_thread(...)`, but the provider clients themselves are still blocking `requests + polling + sleep`;
  - there is no real central worker pool/queue manager yet;
  - there is no explicit global concurrency cap per provider or per heavy local stage;
  - there is no webhook-based provider completion path yet, so provider waits still consume local worker capacity.
- Important architectural conclusion:
  - yes, `Replicate` supports async predictions by default and recommends polling or webhooks for long tasks:
    - https://replicate.com/docs/topics/predictions/create-a-prediction
    - https://replicate.com/docs/topics/predictions/lifecycle/
  - yes, `Kie.ai` documents its generation tasks as asynchronous and explicitly exposes task creation plus later status lookup/callback usage:
    - https://docs.kie.ai/index
    - https://docs.kie.ai/market/common/get-task-detail
- Therefore the correct target architecture is:
  - create provider tasks quickly;
  - release request threads quickly;
  - persist external task IDs;
  - poll or receive callbacks separately;
  - continue local assembly only when upstream AI artifacts are ready;
  - keep a bounded local worker pool for PPTX/PDF assembly and conversion.
- Practical target for MVP hardening:
  - support at least `~5` parallel end-to-end presentation generations with controlled degradation instead of full serialization;
  - avoid a model where user #5 waits for users #1-#4 to fully finish before their own AI stage even starts.
- Planned backend refactor for this:
  - remove product dependence on sync `POST /v1/presentations/render` in the client flow;
  - keep job-based API as the canonical path;
  - split one render job into stages:
    - outline/slide text creation
    - image task fan-out
    - provider status tracking
    - local PPTX build
    - local PDF conversion
  - replace ad-hoc thread spawning with a bounded worker model;
  - add explicit concurrency limits for:
    - AI text requests
    - AI image requests
    - LibreOffice conversions
  - optionally move provider completion from pure polling to callbacks/webhooks where stable.

## Design Pivot — 2026-04-26

- Product direction changed: the mobile client must imitate a Telegram bot, not a classic app with tabs and separate feature screens.
- Active UI requirement:
  - one single chat window;
  - no bottom navigation, no dashboard shell, no separate menu sections;
  - interaction through message feed, inline/reply-style buttons and free-text input;
  - Telegram-like header, wallpaper, message bubbles, keyboard area and file cards;
  - bot-first flow for presentation generation, conversion, help, history, settings and balance.
- Current design archive is saved in `old_design/flutter_ui_v1/`.
- New local design brief is saved in `instructions/design_refs/telegram_bot_ui_brief.md`.
- Business requirement updated:
  - target store for MVP is `RuStore`;
  - billing target from the product side is `YooKassa`;
  - `Telegram Stars` is dropped from the mobile roadmap.
- Important implementation note:
  - the product requirement is now `RuStore + YooKassa`, but before release we still need a separate moderation/payment validation pass against current RuStore monetization rules, because official RuStore docs as of 2026-04-26 actively promote `Pay SDK` for in-app purchases and subscriptions:
    - https://www.rustore.ru/help/en/sdk/pay
    - https://www.rustore.ru/help/en/developers/monetization/manage-subscriptions

## Runtime Lock-in — 2026-04-27

- Active backend endpoint is fixed:
  - `http://185.171.83.116:8010`
- Flutter client no longer allows changing backend URL locally.
- Remote deployment target is fixed to:
  - host `185.171.83.116`
  - app dir `/root/apptaro`
  - Docker host port `8010`
- Billing implementation direction is now concrete:
  - `YooKassa` test mode through backend billing APIs
  - `X-AppSlides-Client-Id` is the persistent client key for subscriptions, limits and payments
  - chat command `/balance` is the single entry point for plan selection, payment launch, polling and cancellation
  - unfinished YooKassa payments must auto-sync on resume/summary checks so the paywall does not depend on a manual refresh
- Operational discipline is now fixed:
  - every large/important change should be committed and pushed to GitHub
  - backend changes should be redeployed to the remote server right after validation
  - the canonical commands live in `OPERATIONS.md`

## UX Fix Pack — 2026-04-28

- Source of truth for the next pass is the latest phone QA from the user.
- This pass is not about new features first; it is about closing the current Telegram-style UX gap end-to-end before moving further.
- Mandatory fixes in this batch:
  - composer cleanup:
    - remove the idle placeholder text `Сообщение`;
    - remove the fake Telegram controls that do nothing;
    - simplify the header and composer so there are no dead icons;
    - make the input area visually closer to Telegram and easier to scan;
    - collapse the mobile keyboard automatically right after sending text;
  - process message lifecycle:
    - plan generation temporary message must disappear once the outline arrives;
    - payment creation temporary message must disappear once the invoice is created;
    - presentation render temporary messages must be reduced and cleaned up on success;
    - job id/status message must remain only when generation fails, for debugging;
  - paywall rewrite:
    - template-step paywall message must say the presentation is almost ready and ask the user to finish the final step through subscription;
    - one-time package options must be removed from the client flow;
    - success-after-payment message must be cleaner and should not show management buttons except `Главное меню`;
    - noisy transient billing transport errors must not leak into the chat feed when the flow can continue safely;
  - text rendering:
    - support richer formatting for bot messages;
    - make the offer link inline and clickable inside the message text;
    - remove the redundant offer preview block from payment success;
  - file behavior on phone:
    - presentation result files must behave like real files from the chat;
    - tapping a file card must open the file flow instead of doing nothing;
    - generated files should be downloaded locally automatically or transparently on first tap without extra friction;
  - visual polish:
    - keep moving sizes, spacing and card styling closer to the Telegram references while removing decorative but non-functional controls.

- Completed in the current pass:
  - [x] idle composer placeholder removed;
  - [x] fake Telegram icons removed from header and bottom bar;
  - [x] keyboard now collapses right after sending text;
  - [x] outline progress message is deleted when the outline arrives;
  - [x] payment creation progress message is deleted when the invoice arrives;
  - [x] render progress is reduced to meaningful messages only;
  - [x] job id/status message is cleaned up on success and intentionally preserved on failure;
  - [x] template-step paywall now uses the “presentation is almost ready” wording;
  - [x] one-time billing package buttons removed from the client paywall flow;
  - [x] markdown-style rich text enabled for bot messages;
  - [x] offer link is now inline and clickable;
  - [x] redundant offer preview block removed from the success flow;
  - [x] transient billing transport noise is suppressed from the chat feed;
  - [x] success-after-payment message now only keeps `Главное меню`;
  - [x] presentation file cards now download/open as real files on mobile;
  - [x] local auto-prefetch of generated result files is enabled for non-web platforms.

- Billing parity improvements after the QA pass:
  - [x] automatic YooKassa polling in the app is now closer to the Telegram bot logic;
  - [x] the app polls payment status every `10 seconds`;
  - [x] automatic polling now stops after `15 minutes` instead of running indefinitely;
  - [x] temporary transport errors during polling no longer terminate the whole payment-wait flow;
  - [x] when polling reaches the timeout window, the chat shows a clean follow-up message with the same payment actions.

- Local chat persistence hardening:
  - [x] transcript restore now waits correctly for the async storage read instead of racing against app startup;
  - [x] chat history restore now keeps bot/user messages, file cards, template preview blocks and inline keyboards;
  - [x] the current conversation step and pending paywall template are now stored together with the transcript;
  - [x] legacy transcript storage is migrated forward instead of being silently dropped on upgrade.
  - [x] transcript storage on mobile is moved from async prefs-only persistence to a dedicated flushed JSON file in app documents storage;
  - [x] chat snapshot now gets flushed again when the app goes to background or is being closed.
  - [x] real-device Android release check passed: after `force-stop`, relaunch restores the same chat thread without debug-only helpers.


## Статус

- Проект: `appslides`
- Последнее обновление: `2026-04-30`
- Текущий этап: `Backend/admin infrastructure expansion + separate Telegram admin bot MVP`
- Текущий фокус: `довести отдельный admin Telegram bot до полной пригодности для prod-операций`

## Что уже сделано

- [x] Изучен [telegrambot/README.md](telegrambot/README.md)
- [x] Изучен [telegrambot/agents.md](telegrambot/agents.md)
- [x] Изучены ключевые модули текущего бота:
  - `handlers/start.py`
  - `handlers/presentation_gen.py`
  - `handlers/file_converter.py`
  - `handlers/subscription.py`
  - `handlers/admin.py`
  - `services/kie_api.py`
  - `services/pptx_builder.py`
  - `services/converter.py`
  - `services/payment.py`
  - `services/auto_renew.py`
  - `services/mailer.py`
  - `database/db.py`
  - `database/models.py`
- [x] Создана базовая структура каталогов `backend/` и `app/`
- [x] Создан `FastAPI`-каркас backend
- [x] Добавлены `GET /v1/health`, `POST /v1/presentations/outline`, `POST /v1/presentations/outline/revise`
- [x] Добавлен `GET /v1/templates/presentation` для каталога дизайнов
- [x] Вынесены prompts и text-generation логика в `backend/src/`
- [x] Вынесен `converter` в `backend/src/jobs/file_converter.py`
- [x] Перенесен `pptx_builder` в `backend/src/jobs/pptx_builder.py`
- [x] Добавлен первый sync render endpoint `POST /v1/presentations/render`
- [x] Добавлен download endpoint `GET /v1/artifacts/{artifact_id}`
- [x] Добавлена in-memory job model для render/conversion задач
- [x] Добавлены async endpoints для presentation jobs
- [x] Добавлены multipart conversion job endpoints
- [x] Добавлены convenience download routes для async jobs
- [x] Добавлен `backend/.env.example` и `backend/requirements.txt`
- [x] Проверен импорт backend-приложения локально
- [x] Проверен end-to-end render: `PPTX`
- [x] Проверен end-to-end render: `PDF`
- [x] Добавлены backend smoke-тесты на `unittest`
- [x] Создан ручной Flutter-ready scaffold в `app/`
- [x] Добавлен app data/API layer под backend endpoints
- [x] Подключен экран генерации презентации к backend API
- [x] Подключен экран конвертации к backend API
- [x] Добавлена локальная persistent-history в приложении
- [x] Установлен Flutter SDK локально на ПК
- [x] `app/` переведен в настоящий Flutter-проект с platform folders
- [x] Пройдены `flutter analyze`, `flutter test`, `flutter build web`
- [x] Собран Android APK: `app/build/app/outputs/flutter-apk/app-release.apk`
- [x] Добавлено локальное сохранение download artifacts в app storage
- [x] Добавлен persistent-index локальных файлов в `app/`
- [x] Исправлен Android toolchain: `cmdline-tools` + licenses
- [x] Добавлен runtime-config backend endpoint в `app/`
- [x] Поднят локальный `backend/.venv`, установлены зависимости и проходят smoke-тесты
- [x] Добавлены PowerShell helper scripts для backend start/stop/health
- [x] Добавлено offline-открытие и удаление локальных сохраненных файлов
- [x] Активный Flutter UI переведен с tab-shell на single-screen Telegram-style chat
- [x] Сохранен архив старого дизайна в `old_design/flutter_ui_v1/`
- [x] Добавлена локальная persistent chat-лента для bot-style интерфейса
- [x] Чатовый UI подогнан ближе к Telegram по геометрии: узкая колонка, reply-кнопки, composer и document cards
- [x] Для `Баланс / Подписка` добавлен Telegram-like preview-блок оферты внутри сообщения
- [x] Добавлены bot-like карточки файлов с действиями `Открыть` / `Удалить`
- [ ] Поднять backend MVP
- [ ] Поднять Flutter MVP
- [ ] Перенести генерацию презентаций
- [ ] Перенести конвертацию файлов
- [ ] Перенести подписки и биллинг
- [ ] Собрать iOS MVP

## Что я понял по текущему `telegrambot`

Текущий бот уже содержит почти весь продуктовый backend, только завязанный на Telegram:

1. Генерация презентации:
   - пользователь вводит тему;
   - выбирает число слайдов;
   - бот генерирует title + outline через `KieClient`;
   - пользователь принимает или редактирует план;
   - выбирает один из 4 шаблонов;
   - бот генерирует тексты слайдов и изображения;
   - собирает `PPTX` через `python-pptx`;
   - конвертирует в `PDF` через LibreOffice;
   - отдает пользователю готовые файлы.

2. Конвертация файлов:
   - `PDF -> DOCX`
   - `DOCX -> PDF`
   - `PPTX -> PDF`
   - основной путь через LibreOffice, fallback для `PDF -> DOCX` через `pdf2docx`.

3. Монетизация:
   - тарифы `week`, `month`, `one10`, `one40`;
   - подписки и разовые пакеты генераций;
   - `YooKassa` и `Telegram Stars`;
   - автопродление с `payment_method_id`;
   - логика списания/переноса/expiring уже реализована.

4. Данные:
   - локальная `SQLite`;
   - пользователи, подписки, генерации, платежи, промокоды, админы, рекламные метки, состояние рассылки.

5. Операционный слой:
   - админ-команды;
   - уведомления админам;
   - авторассылка;
   - очистка временных файлов;
   - Docker-ready деплой.

Вывод: заново изобретать продуктовую логику не нужно. Нужно вынести ее из Telegram-обработчиков в отдельный backend API и дать ей новый клиент на Flutter.

## Главный архитектурный вывод

Новый проект нельзя строить как "Flutter-клиент, который сам все делает на устройстве".

Правильное разделение для MVP такое:

- `app/`:
  - UI;
  - локальная история запросов;
  - локальный список созданных файлов;
  - локальные черновики и пользовательские настройки;
  - просмотр статуса задач;
  - скачивание и хранение результатов на устройстве;
  - опционально офлайн-доступ к уже сохраненным материалам.

- `backend/`:
  - обращения к Kie/Replicate и другим AI/API;
  - генерация outline/title/slides;
  - генерация иллюстраций;
  - сборка `PPTX`;
  - конвертация `PPTX/PDF/DOCX`;
  - обработка долгих задач;
  - минимальная серверная учетная запись/entitlement;
  - биллинг, receipt validation, лимиты, антиабьюз;
  - шаблоны, промокоды, админ-функции.

Важно: "хранить все локально на устройстве" для MVP разумно только для пользовательского контента и истории. Для подписки, лимитов, проверки оплат и job-статусов минимальный серверный state все равно нужен.

## Что переносим без изменения идеи

Из текущего бота нужно сохранить почти один в один:

- сценарий генерации презентации;
- шаблонный `PPTX`-builder;
- конвертацию через LibreOffice;
- prompts и fallback-логику для AI;
- учет генераций и тарифов;
- промокоды;
- админ-уведомления;
- фоновые воркеры;
- очистку временных файлов;
- структуру продуктовых шагов: `тема -> план -> правка -> дизайн -> генерация -> выдача`.

## Что нужно изменить принципиально

### 1. Telegram FSM -> мобильные экраны и локальный state

Сейчас состояние сценария живет в `aiogram FSM`.

В новой версии:

- каждый шаг станет экраном/состоянием Flutter;
- промежуточный прогресс хранится локально;
- backend будет получать уже нормализованный payload, а не поток Telegram-сообщений.

### 2. Монолитный бот -> API + worker

Сейчас Telegram-бот сам:

- принимает ввод;
- ходит в AI;
- собирает файлы;
- ждет конвертацию;
- шлет результат.

В новой версии:

- API принимает запрос;
- создает job;
- worker выполняет тяжелую работу;
- клиент опрашивает статус или получает push/event.

### 3. Telegram-платежи -> мобильный биллинг

Схему `YooKassa + Telegram Stars` нельзя просто перенести в нативные приложения как есть.

Для мобильного MVP нужно сразу проектировать отдельный billing-layer:

- iOS: `StoreKit / In-App Purchase`;
- Android: `Google Play Billing`;
- backend: валидация receipt/purchase token и выдача entitlements.

Веб-оплата через YooKassa может остаться как отдельный канал позже, но не как основной путь для мобильных сто́ров.

Официальные источники для этого решения:

- Apple App Store Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- Apple StoreKit / In-App Purchase overview: https://developer.apple.com/storekit/
- Google Play Billing overview: https://developer.android.com/google/play/billing

## Целевая архитектура MVP

### Клиент `Flutter`

Рекомендованная структура:

```text
app/
  lib/
    bootstrap/          # запуск, конфиг окружений, DI
    app/                # App widget, router, theme
    core/               # network, storage, errors, constants
    data/               # DTO, repositories, local/remote data sources
    domain/             # entities, use cases
    features/
      home/
      presentation/
      converter/
      subscription/
      history/
      settings/
    shared/             # общие widgets, ui kit, helpers
  assets/
    images/
    icons/
  test/
```

Первый набор экранов:

1. Splash / bootstrap
2. Home
3. Create presentation
4. Outline review/edit
5. Design picker
6. Generation progress
7. Result files
8. Converter
9. Subscription / paywall
10. Local history
11. Settings / support

### Backend `Python`

Оптимальный путь миграции: оставить backend на Python, чтобы переиспользовать код из `telegrambot/services` почти напрямую.

Рекомендованная структура:

```text
backend/
  src/
    api/               # FastAPI routers
    core/              # config, security, settings, logging
    domain/            # entities, business contracts
    integrations/      # Kie, Replicate, payments, external APIs
    jobs/              # async jobs / workers
    repositories/      # DB access
    schemas/           # Pydantic models
  tests/
  runtime/
    templates/
    temp/
```

Рекомендованный стек backend:

- `FastAPI` для HTTP API;
- `Pydantic` для контрактов;
- `Redis` для очереди задач и кэша статусов;
- `PostgreSQL` для минимального серверного state;
- отдельный worker-процесс для тяжелых задач;
- Docker-деплой на ваш облачный сервер.

Почему не стоит оставлять все на серверной `SQLite`:

- пойдут параллельные mobile-запросы;
- будут фоновые задачи;
- будет биллинг и идемпотентность оплат;
- позже понадобится web и, вероятно, админ-панель.

При этом файлы, история и чаты пользователя все равно можно держать локально на устройстве, а в backend хранить только метаданные и entitlement.

## Что хранится локально, а что на сервере

### Локально в приложении

- история чатов/запросов;
- список созданных презентаций и конвертаций;
- локальные пути к файлам;
- пользовательские черновики;
- кэш шаблонов и превью;
- UI-предпочтения;
- временные файлы до/после загрузки.

### На сервере

- install/user id;
- active subscription / credits / entitlements;
- purchase receipts / payment records;
- job id, status, error, timestamps;
- шаблоны и их версии;
- промокоды;
- админская аналитика;
- техлоги.

### Не храним на сервере в MVP

- полную историю пользовательских чатов;
- архив всех результатов пользователя;
- облачную медиатеку.

## Предлагаемый API-контур MVP

### Auth / device

- `POST /v1/devices/register`
- `POST /v1/devices/refresh`
- `GET /v1/me`

### Templates

- `GET /v1/templates/presentation`

### Presentation flow

- `POST /v1/presentations/outline`
- `POST /v1/presentations/outline/revise`
- `POST /v1/presentations/jobs`
- `GET /v1/presentations/jobs/{job_id}`
- `GET /v1/presentations/jobs/{job_id}/download/pptx`
- `GET /v1/presentations/jobs/{job_id}/download/pdf`

### Conversion flow

- `POST /v1/conversions/jobs`
- `GET /v1/conversions/jobs/{job_id}`
- `GET /v1/conversions/jobs/{job_id}/download`

### Billing

- `GET /v1/plans`
- `POST /v1/billing/ios/validate`
- `POST /v1/billing/android/validate`
- `GET /v1/subscription`
- `POST /v1/promo/activate`

### Admin later

- `GET /v1/admin/stats`
- `POST /v1/admin/templates`
- `POST /v1/admin/promocodes`

## Карта миграции: старый код -> новый код

### Перенос в backend почти напрямую

- `telegrambot/services/kie_api.py`
  -> `backend/src/integrations/ai/`
- `telegrambot/services/pptx_builder.py`
  -> `backend/src/jobs/presentation_builder.py`
- `telegrambot/services/converter.py`
  -> `backend/src/jobs/file_converter.py`
- `telegrambot/services/payment.py`
  -> `backend/src/integrations/payments/legacy_reference.py`
- `telegrambot/services/auto_renew.py`
  -> `backend/src/jobs/subscription_renewal.py`
- `telegrambot/services/mailer.py`
  -> `backend/src/jobs/mailer.py`
- `telegrambot/database/models.py`
  -> `backend/src/repositories/`

### Расщепление Telegram handlers на client + backend

- `telegrambot/handlers/presentation_gen.py`
  -> `app/lib/features/presentation/...`
  + `backend/src/api/presentations.py`
  + `backend/src/jobs/presentation_generation.py`

- `telegrambot/handlers/file_converter.py`
  -> `app/lib/features/converter/...`
  + `backend/src/api/conversions.py`

- `telegrambot/handlers/subscription.py`
  -> `app/lib/features/subscription/...`
  + `backend/src/api/billing.py`

- `telegrambot/handlers/start.py`
  -> `app/lib/features/home/...`
  + onboarding/navigation/state bootstrap

- `telegrambot/handlers/admin.py`
  -> пока не в мобильное приложение;
  -> позже в отдельную internal admin panel / web admin.

## Этапы реализации

## Этап 0. Архитектурная фиксация

- [x] Изучить текущего бота
- [x] Зафиксировать план
- [x] Создать новую структуру каталогов
- [ ] Утвердить стек backend и mobile state management

## Этап 1. Вынос backend-ядра из Telegram

- [x] Создать backend-конфиг и базовый FastAPI skeleton
- [x] Перенести prompts, AI clients, pptx builder, converter
- [x] Оформить это как сервисы без зависимости от Telegram objects
- [x] Ввести job model: `queued / running / done / failed`
- [x] Настроить runtime templates/temp

Результат этапа:

- backend умеет сгенерировать презентацию и вернуть артефакты `PPTX/PDF` по API;
- backend умеет конвертировать документы;
- для долгих операций уже есть async job API со статусами;
- никакой зависимости от Telegram внутри продуктовых сервисов для нового API-контура;
- следующий шаг после стабилизации backend: подключение Flutter-клиента к этим async endpoints.

## Этап 2. Минимальная серверная модель данных

- [ ] Спроектировать `users/devices`
- [ ] Спроектировать `plans/subscriptions/entitlements`
- [ ] Спроектировать `jobs`
- [ ] Спроектировать `payments/receipts`
- [ ] Добавить промокоды

Результат этапа:

- есть минимальный серверный state без хранения пользовательских файлов и длинной истории.

## Этап 3. Flutter foundation

- [x] Создать ручной Flutter scaffold внутри `app/`
- [x] Настроить базовый shell/navigation
- [x] Настроить тему и базовые экраны
- [x] Поднять реальный Flutter SDK-проект командой `flutter pub get`
- [x] Настроить HTTP client
- [x] Настроить локальное хранилище
- [x] Настроить базовый DI/state management

Рекомендация:

- state management: `Riverpod`;
- local storage: `Drift` или `Hive/Isar` для MVP;
- networking: `Dio`.

## Этап 4. Экран генерации презентации

- [x] Экран ввода темы
- [x] Выбор количества слайдов
- [x] Preview outline
- [x] Ручное редактирование outline
- [x] Выбор дизайна
- [x] Экран прогресса job
- [x] Экран результата и скачивания файлов

## Этап 5. Экран конвертации файлов

- [x] Выбор файла
- [x] Выбор целевого формата
- [x] Загрузка на backend
- [x] Статус job
- [x] Скачивание результата
- [x] Сохранение в локальную историю

## Этап 6. Подписки и платежи

- [ ] Утвердить store-стратегию
- [ ] Реализовать `plans` API
- [ ] Реализовать paywall в приложении
- [ ] Реализовать receipt validation на backend
- [ ] Реализовать restore purchases
- [ ] Реализовать entitlement sync

Критично:

- не переносить Telegram Stars в мобильное приложение;
- не строить iOS MVP вокруг прямой YooKassa-оплаты цифрового контента внутри app.

## Этап 7. Локальная история и файловый менеджмент

- [x] Таблица локальной истории запросов
- [x] Таблица локальных файлов
- [x] Повторное открытие результата без сервера
- [x] Удаление локальных материалов
- [ ] Ограничение кэша и TTL

## Этап 8. Тестирование MVP

- [x] Smoke backend
- [ ] Smoke Flutter Android на эмуляторе/устройстве
- [ ] Smoke Flutter iOS
- [x] Smoke Flutter Web
- [x] Smoke Flutter analyze/test
- [ ] Генерация 10+ презентаций подряд
- [ ] Конвертация больших файлов
- [ ] Ошибки AI и retry
- [ ] Потеря сети в середине job
- [ ] Restore subscription после переустановки

## Этап 9. После MVP

- [ ] Web build на Flutter
- [ ] Cloud sync истории
- [ ] Облачное хранение результатов через Cloudflare
- [ ] Internal admin panel
- [ ] Аналитика событий
- [ ] Push notifications по завершению job

## Ключевые риски

### Риск 1. Платежи в mobile stores

Это не косметический вопрос, а архитектурный. Если заложить не ту платежную схему, потом придется переписывать paywall, backend entitlements и release-процесс.

### Риск 2. Смешение локального хранения и серверной подписки

Если вообще не хранить серверный entitlement, приложение легко будет ломать или рассинхронизировать.

### Риск 3. Долгие задачи

Генерация презентации и конвертация файлов не должны жить в request-response без job layer.

### Риск 4. Слишком ранний старт с web

Сейчас правильнее сначала довести mobile MVP, потом открывать web.

## Решения, которые я предлагаю зафиксировать сейчас

1. Backend делаем на Python, а не переписываем все заново на другой язык.
2. Генерация, конвертация, AI и биллинг живут на сервере.
3. История, черновики и файлы результата хранятся локально на устройстве.
4. Для мобильных оплат проектируем отдельный store billing layer.
5. `telegrambot/` не ломаем; он остается референсом и донором логики до полной миграции.

## Что делать следующим шагом

Следующий практический блок после текущего состояния:

1. Прогнать `flutter run` на Android-эмуляторе или телефоне с реальными `Presentation` / `Converter` flows поверх уже поднятого локального backend.
2. После smoke на Android перейти к подпискам, paywall и server-side entitlement model.
3. Добить ограничение кэша и TTL для локальных результатов.
4. Включить Windows Developer Mode, если понадобится полноценный `flutter build windows`.
5. После mobile MVP отдельно решать web-specific UX и cloud sync.

Это уже правильный следующий шаг, потому что backend-контур генерации и конвертации собран, имеет download routes, покрыт базовым smoke-набором, а `app/` уже имеет DI, presentation flow, converter flow, локальную persistent-history, локальный файловый индекс, рабочий Flutter runtime и подготовленный Android toolchain.
