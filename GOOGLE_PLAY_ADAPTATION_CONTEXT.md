# PMapptaro Google Play Adaptation Context

Дата старта этапа: 2026-07-06.

## Активная рабочая папка

Работа по новой ветке ведется только в этой папке:

`D:\papka for all\work\PMapptaro`

Внутренние ссылки в документах дальше указываются относительно корня этой папки: `app/`, `backend/`, `telegram_admin_bot/`, `telegram_taro_bot/`, `docs/`, `scripts/`.

Старые проекты `appslides`, `PMappslides` и RuStore-версия презентаций не считаются рабочим контуром для этого этапа. Их можно использовать только как справочную историю решений, но не как место для правок.

## Сохраненная вводная от заказчика

Новый этап: адаптация приложения по таро под Google Play.

Исходная папка уже создана как копия рабочего проекта. Ее можно изменять напрямую, отдельные backup-копии перед правками не требуются.

Текущее приложение:

- Flutter-приложение по таро.
- Уже было собрано и опубликовано в RuStore.
- Имеет отдельный backend, admin Telegram bot и исходный Telegram-бот `telegram_taro_bot/`, из которого бралась предметная логика.

Основная цель этапа:

- Сделать Google Play версию приложения по таро по аналогии с уже выполненной Google Play адаптацией приложения по презентациям.
- Сначала полностью перевести продукт на английский язык.
- Затем подготовить архитектуру, чтобы в будущем добавить несколько популярных языков.

Ожидаемая локализация:

- MVP: английский язык как основной для Google Play.
- Далее: несколько языков, ориентировочно 5 популярных языков.
- Приложение должно уметь выбирать язык по языку устройства.
- В интерфейсе нужна ручная смена языка, например через небольшую кнопку `Change language`.
- Переводу подлежат не только UI-тексты, но и ответы бота, prompts, ошибки, billing-тексты и backend-generated сообщения.

Ожидаемая инфраструктура:

- Для Google Play версии нужен отдельный backend на сервере.
- Рабочая папка на сервере должна быть отдельной, не смешанной с RuStore backend.
- Ожидаемая серверная папка: `/root/PMapptaro`.
- Данные backend должны храниться во внешней примонтированной папке `data/`.
- Admin Telegram bot также должен относиться к этому отдельному Google Play backend.

Ожидаемая проверка:

- Нужно настроить Android-эмулятор на ноутбуке, чтобы проверять приложение без подключения физического телефона.
- Нужна возможность устанавливать APK/AAB debug-сборки, открывать приложение визуально, делать скриншоты и смотреть поведение.
- Для Google Play Billing предпочтителен официальный Android Emulator с образом Google Play, а не сторонний эмулятор.

GitHub:

- Репозиторий или ветка для этого проекта может быть уточнена позже.
- Пока GitHub-работы не выполнять без отдельного подтверждения.
- Если репозиторий уже подключен, перед крупными правками нужно создать отдельную ветку под Google Play версию.

## Стартовые технические наблюдения

Проверено на старте этапа:

- В корне есть `app/`, `backend/`, `telegram_admin_bot/`, `telegram_taro_bot/`, `scripts/`, `docs/`.
- `app/pubspec.yaml` пока содержит `name: appslides`, `description: AppSlides mobile client scaffold`, `version: 0.1.0+6`.
- В Flutter-клиенте много русских строк прямо в `app/lib/features/chat/chat_screen.dart` и других файлах.
- Пакетов локализации в `app/pubspec.yaml` пока нет: `flutter_localizations`, `intl`, `easy_localization` не подключены.
- Backend сейчас использует YooKassa-логику.
- Текущий backend URL в Flutter: `http://185.171.83.116:8010`.
- Tarot prompts находятся в `backend/src/domain/presentation_prompts.py`.
- Backend README указывает production backend `http://185.171.83.116:8010` и SQLite `/root/apptaro/data/appslides.db`.

## Дополнительный handoff из старого RuStore-чата

Получен отдельный handoff из рабочего чата, где создавалась RuStore-версия `apptaro`.

Нормализованная версия сохранена в `SOURCE_HANDOFF_RUSTORE_APPTARO.md`.

Главные выводы из handoff:

- Старый production-контур находится в `/root/apptaro`; для Google Play он не должен использоваться как рабочая папка.
- Текущий Android package из RuStore версии: `com.apptaro.app`.
- На момент handoff release signing использовал debug signingConfig; для Google Play нужен нормальный upload key.
- Для Google Play желательно уйти от `http://185.171.83.116:8010` и `usesCleartextTraffic=true` к HTTPS.
- YooKassa нельзя оставлять как основной in-app billing для Google Play версии; нужен Google Play Billing + server-side token validation.
- Нельзя ломать local transcript persistence, stable client_id, backend entitlement, promo codes, admin bot и tarot image/layout generation.

## Правило этапа

Все новые документы, планы и правки по Google Play версии таро должны относиться к `PMapptaro`.

Если в старых файлах встречаются названия `appslides`, `PMappslides`, RuStore или YooKassa, это не значит, что они остаются целевым состоянием. Для Google Play версии их нужно проверять и постепенно заменить там, где это относится к продукту, оплате, branding, backend и публикации.
