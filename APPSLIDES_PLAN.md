# AppSlides Plan

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
  - app dir `/root/appslides`
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


## Статус

- Проект: `appslides`
- Последнее обновление: `2026-04-26`
- Текущий этап: `Этап 1 backend MVP стабилизирован + Этап 3/7 Flutter MVP с Telegram-style UI polish`
- Текущий фокус: `приближать chat UX к Telegram 1-в-1: размеры кнопок, пузыри, file cards, wallpaper и затем YooKassa paywall в чате`

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
