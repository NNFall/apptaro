# PMapptaro Google Play Adaptation Goals

Этот документ фиксирует крупные цели для переноса Tarot Flutter app из RuStore-контура в Google Play-контур.

## Цель 1. Зафиксировать отдельный контур PMapptaro

Результат:

- Все работы ведутся только в текущем проекте `PMapptaro`.
- RuStore/YooKassa версия не ломается случайными правками.
- Google Play версия получает отдельную ветку, отдельный backend и отдельную серверную папку.

Что проверить:

- Текущий git status и ветку.
- Какие файлы уже изменены до начала этапа.
- Какие старые документы относятся к RuStore, а какие можно использовать как общую архитектурную памятку.

## Цель 2. Подготовить Google Play branding и Android package

Результат:

- Название приложения, иконка, splash/launcher assets и package id соответствуют Google Play версии.
- `versionCode` повышается при каждой новой сборке.
- Сборка выпускается как `AAB` для Google Play и как `APK` только для ручного теста.
- Release signing использует нормальный upload key, а не debug signing.
- Production backend URL для Google Play по возможности работает через HTTPS, без `usesCleartextTraffic=true`.

Что нужно будет уточнить у заказчика:

- Финальное английское название приложения.
- Package name для Google Play.
- Иконка 512x512 и featured graphic для страницы Google Play.
- Краткое и полное описание на английском.

Стартовое состояние из handoff:

- Текущий Android package: `com.apptaro.app`.
- Текущая версия Flutter: `0.1.0+6`.
- Старый backend URL: `http://185.171.83.116:8010`.

## Цель 3. Перевести MVP на английский язык

Результат:

- Все видимые тексты Flutter-клиента переведены на английский.
- Все bot-style сообщения в чате переведены на английский.
- Ошибки сети, оплаты, генерации, лимитов, promo и файлов переведены на английский.
- Backend-generated тексты и prompts генерируют английские ответы.
- Admin bot может остаться русским для администраторов, если заказчик не попросит обратное.

Ключевые зоны:

- `app/lib/features/chat/chat_screen.dart`
- `app/lib/features/home/`
- `app/lib/features/settings/`
- `app/lib/features/subscription/`
- `app/lib/core/config/`
- `backend/src/domain/presentation_prompts.py`
- `backend/src/api/`
- `backend/src/domain/billing_service.py`
- `backend/src/integrations/admin_notifier.py`

## Цель 4. Заложить нормальную архитектуру локализации

Результат:

- Тексты не должны оставаться набором случайных hardcoded строк.
- Должен появиться слой локализации для Flutter UI.
- Backend должен понимать язык пользователя и отдавать ответы/prompts на нужном языке.
- Язык по умолчанию берется из языка устройства.
- Пользователь может вручную сменить язык в приложении.

MVP-решение:

- Минимум 2 языка: English + Russian или English + второй язык по решению заказчика.
- В клиенте хранить выбранный язык локально.
- В каждый backend request передавать language/locale.
- На backend использовать language-aware prompts и language-aware тексты ошибок.

Будущее расширение:

- Добавление новых языков должно требовать добавления словаря/prompts, а не переписывания flow.
- Для 5 языков нужно заранее разделить UI-тексты, server-тексты и prompt-тексты.

## Цель 5. Заменить YooKassa на Google Play Billing в Google Play версии

Результат:

- В Google Play версии покупка подписок идет через Google Play Billing.
- Flutter-клиент использует Google billing package.
- Backend проверяет purchase token через Google Play Developer API.
- Подписка и лимиты хранятся server-side.
- Restore/reinstall сценарии работают: если пользователь купил подписку, приложение может восстановить ее без отдельной видимой кнопки, когда это возможно.

Важные уроки из предыдущего проекта:

- Нельзя считать покупку успешной только на клиенте.
- Backend должен получать `purchaseToken`, `productId`, `packageName` и проверять их через Google API.
- Нужен service account с правами `Управление заказами и подписками`.
- Старые покупки и восстановленные покупки нужно отправлять на backend, даже если активного pending flow уже нет.
- Для каждой новой сборки нужен повышенный `versionCode`.

## Цель 6. Развернуть отдельный backend на сервере

Результат:

- Серверная папка: `/root/PMapptaro`.
- Docker Compose не смешан с RuStore проектом.
- База, runtime-файлы, generated files и service account лежат в примонтированном `data/`.
- Backend работает на отдельном порту.
- Admin Telegram bot подключен к этой же базе и этому же backend-контуру.
- Старый RuStore remote dir `/root/apptaro` не используется для Google Play deploy.

Что нужно будет сделать:

- Подготовить `.env.example` под Google Play.
- Добавить Google Play service account config.
- Добавить отдельные Docker service names, чтобы не конфликтовать с RuStore.
- Настроить healthcheck и restart policy.
- Проверить, что admin bot не берет базу из старого проекта.

## Цель 7. Настроить Android Emulator для визуального тестирования

Результат:

- На ноутбуке есть официальный Android Emulator.
- Можно запускать приложение без телефона по USB.
- Можно делать screenshots, проверять навигацию, оплату в тестовом окружении, локализацию и поведение при перезапуске.

Рекомендуемый вариант:

- Android Studio + Android Emulator.
- Для Google Play Billing нужен emulator image с Google Play, а не просто Google APIs.
- Альтернативные эмуляторы можно использовать для обычного UI-smoke, но не как основной способ проверки Google Play Billing.

## Цель 8. Подготовить Google Play release pipeline

Результат:

- Стабильная команда сборки `AAB`.
- Стабильная команда сборки `APK` для ручного теста.
- Документирован порядок загрузки в Google Play Console.
- Есть release notes на английском.
- Есть список проверок перед отправкой на review.
- Есть privacy policy URL и disclaimer для AI/tarot entertainment content.

Минимальная проверка перед релизом:

- `flutter analyze`
- `flutter test`
- backend unit/smoke tests
- emulator smoke test
- проверка покупки/restore Google Play на тестовом треке
- проверка, что все пользовательские тексты на английском

## Ближайший рабочий маршрут

1. Создать отдельную git-ветку для Google Play версии после подтверждения.
2. Провести inventory Flutter-текстов и backend-текстов.
3. Спроектировать слой локализации.
4. Сначала перевести UI и chat flow на английский.
5. Затем перевести backend prompts и ответы.
6. После этого заменить billing с YooKassa на Google Play Billing.
7. Потом развернуть отдельный backend на `/root/PMapptaro`.
8. После backend smoke собрать `AAB` и тестовый `APK`.
9. Проверить приложение в Android Emulator.
10. Подготовить материалы Google Play.
