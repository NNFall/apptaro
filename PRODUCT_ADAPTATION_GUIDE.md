# Product Adaptation Guide

## Назначение

Этот документ нужен для повторного использования текущего проекта `appslides` под другую тематику.

Речь не только про Таро. Та же схема подходит под:

- расклады и консультации;
- генерацию фото или видео;
- генерацию песен;
- подготовку отчетов;
- любые другие AI-сценарии, где пользователю удобно идти по пошаговому чат-флоу.

Главная идея: не пересобирать приложение с нуля, а сохранить готовый каркас:

- Flutter-клиент с chat UX;
- backend с платежами, лимитами, job-моделью и админ-уведомлениями;
- отдельный Telegram admin bot;
- deploy-процесс и серверную структуру.

Меняется не платформа, а предметная логика и тексты под твою тематику.

## Что считать неизменным ядром

### Flutter-каркас

Оставлять как базу:

- единый чат-экран;
- локальное сохранение истории;
- локальное сохранение файлов;
- `client_id` устройства/установки;
- billing flow через backend;
- общую механику сообщений, inline-кнопок, file cards и progress-сообщений.

Ключевые файлы:

- [app/lib/features/chat/chat_screen.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/chat/chat_screen.dart:1)
- [app/lib/features/billing/billing_controller.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/billing/billing_controller.dart:1)
- [app/lib/data/api/appslides_api_client.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/api/appslides_api_client.dart:1)
- [app/lib/data/repositories/chat_transcript_repository.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/repositories/chat_transcript_repository.dart:1)
- [app/lib/data/repositories/saved_files_repository.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/repositories/saved_files_repository.dart:1)
- [app/lib/data/repositories/client_session_repository.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/repositories/client_session_repository.dart:1)
- [app/lib/app/app_scope.dart](C:/Users/User/Desktop/work/appslides/app/lib/app/app_scope.dart:1)

### Backend-каркас

Оставлять как базу:

- `FastAPI` API-слой;
- storage/repositories;
- job-модель;
- YooKassa и subscription state;
- админ-уведомления;
- deploy через Docker;
- mounted data/templates/temp/logs на сервере.

Ключевые файлы:

- [backend/src/main.py](C:/Users/User/Desktop/work/appslides/backend/src/main.py:1)
- [backend/src/api/router.py](C:/Users/User/Desktop/work/appslides/backend/src/api/router.py:1)
- [backend/src/repositories/storage.py](C:/Users/User/Desktop/work/appslides/backend/src/repositories/storage.py:1)
- [backend/src/repositories/billing.py](C:/Users/User/Desktop/work/appslides/backend/src/repositories/billing.py:1)
- [backend/src/domain/billing_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/billing_service.py:1)
- [backend/src/integrations/yookassa_gateway.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/yookassa_gateway.py:1)
- [backend/src/integrations/admin_notifier.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/admin_notifier.py:1)
- [backend/src/repositories/jobs.py](C:/Users/User/Desktop/work/appslides/backend/src/repositories/jobs.py:1)

### Операционный каркас

Оставлять как базу:

- GitHub flow;
- deploy-скрипт;
- backend на сервере;
- отдельный admin bot;
- документацию и правила обновления.

Ключевые файлы:

- [OPERATIONS.md](C:/Users/User/Desktop/work/appslides/OPERATIONS.md:1)
- [scripts/deploy/deploy_backend_remote.py](C:/Users/User/Desktop/work/appslides/scripts/deploy/deploy_backend_remote.py:1)
- [docker-compose.backend.yml](C:/Users/User/Desktop/work/appslides/docker-compose.backend.yml:1)
- [telegram_admin_bot/main.py](C:/Users/User/Desktop/work/appslides/telegram_admin_bot/main.py:1)

## Что меняется под новую тематику

Меняются только продуктовые слои.

### Во Flutter

Под замену или адаптацию:

- приветственные тексты;
- help-тексты;
- названия кнопок;
- пошаговый чат-сценарий;
- структура пользовательского ввода;
- логика того, какие файлы или карточки результата показывать;
- брендинг, название приложения, иконка, скриншоты.

Обычно это находится в:

- [app/lib/features/chat/chat_screen.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/chat/chat_screen.dart:1)
- [app/lib/app/app.dart](C:/Users/User/Desktop/work/appslides/app/lib/app/app.dart:1)
- [app/lib/app/theme.dart](C:/Users/User/Desktop/work/appslides/app/lib/app/theme.dart:1)
- [app/android/app/src/main/AndroidManifest.xml](C:/Users/User/Desktop/work/appslides/app/android/app/src/main/AndroidManifest.xml:1)
- `app/assets/branding/*`

### На backend

Под замену или адаптацию:

- prompts;
- outline/render logic;
- тип результата;
- формирование итоговых файлов;
- шаблоны;
- тексты админ-уведомлений по продуктовым событиям;
- специфические таблицы или поля, если новой тематике нужны дополнительные сущности.

Обычно это находится в:

- [backend/src/domain/presentation_prompts.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_prompts.py:1)
- [backend/src/domain/presentation_outline_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_outline_service.py:1)
- [backend/src/domain/presentation_render_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_render_service.py:1)
- [backend/src/integrations/text_generation.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/text_generation.py:1)
- [backend/src/jobs/pptx_builder.py](C:/Users/User/Desktop/work/appslides/backend/src/jobs/pptx_builder.py:1)
- [backend/src/jobs/template_catalog.py](C:/Users/User/Desktop/work/appslides/backend/src/jobs/template_catalog.py:1)
- [backend/src/api/presentations.py](C:/Users/User/Desktop/work/appslides/backend/src/api/presentations.py:1)

## Как переносить логику из другого Telegram-бота

Если у тебя уже есть другой Telegram-бот по новой тематике, он становится источником продуктовой логики.

### Что брать из нового Telegram-бота

- тексты и меню;
- последовательность шагов пользователя;
- промпты;
- ограничения и правила продукта;
- специфические сущности;
- формат результата;
- админские события;
- help/onboarding-сценарии.

### Что брать из текущего `appslides`

- весь Flutter UI-каркас;
- chat UX;
- локальную историю;
- file handling;
- billing shell;
- admin bot каркас;
- deploy и инфраструктуру;
- структуру backend.

### Простое правило

Новый Telegram-бот отвечает на вопрос:

`что именно делает продукт`

Текущий `appslides` отвечает на вопрос:

`как это выглядит, хранится, оплачивается, логируется и разворачивается`

## Карта изменений по слоям

## 1. Бренд и упаковка

Менять:

- имя приложения;
- иконку;
- README;
- скриншоты;
- help-тексты;
- store-описания.

Файлы:

- [README.md](C:/Users/User/Desktop/work/appslides/README.md:1)
- [app/README.md](C:/Users/User/Desktop/work/appslides/app/README.md:1)
- [docs/images](C:/Users/User/Desktop/work/appslides/docs/images)
- `app/assets/branding/*`

## 2. Chat flow

Менять:

- стартовый текст;
- главное меню;
- команды;
- шаги сценария;
- набор inline-кнопок;
- продуктовые статусы и сообщения.

Файл:

- [app/lib/features/chat/chat_screen.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/chat/chat_screen.dart:1)

Что обычно оставлять:

- механику transcript;
- восстановление чата после перезапуска;
- очистку временных сообщений;
- billing resume;
- file card wiring.

## 3. API-контракт

Есть два варианта.

### Вариант A. Быстрый

Оставить существующие endpoint-имена и поменять только внутреннюю семантику.

Плюсы:

- быстрее;
- меньше изменений во Flutter;
- удобнее для нового AI, если нужен быстрый перенос.

Минусы:

- названия вроде `presentations` могут уже не соответствовать смыслу продукта.

### Вариант B. Чистый

Переименовать API под новую тематику.

Плюсы:

- чище архитектурно;
- легче поддерживать долгосрочно.

Минусы:

- больше изменений в app и backend одновременно.

Для быстрого фабричного переноса лучше сначала идти по варианту A, а рефакторить названия уже вторым проходом.

## 4. Product domain на backend

Если новый продукт не связан с презентациями, то под замену почти всегда идут:

- outline-логика;
- render-логика;
- prompts;
- job payload;
- artifact metadata;
- формат пользовательского результата.

Примеры:

- для Таро вместо outline может быть расклад и трактовка;
- для фото/видео вместо `pptx/pdf` будут media artifacts;
- для песен вместо шаблонов презентаций будут стили, жанры и output-файлы другого типа.

## 5. Платежи и лимиты

Обычно менять:

- названия тарифов;
- отображаемое описание;
- что именно покупает пользователь: генерации, токены, кредиты, расклады, минуты, результаты.

Обычно не менять:

- общую модель `billing summary -> plans -> create payment -> poll -> activate entitlement`;
- `client_id`;
- `YooKassa` gateway;
- хранение subscription/payment state;
- admin-уведомления по оплатам и автосписаниям.

## 6. Админ-бот

Оставлять как базу:

- отдельный Telegram admin bot;
- ENV-доступ админов;
- статистику;
- команды по подписке;
- промокоды;
- шаблоны;
- backend-driven notifications.

Менять:

- формулировки;
- продуктовые поля;
- уведомления о конкретных сценариях новой тематики.

Ключевые файлы:

- [telegram_admin_bot/handlers/admin.py](C:/Users/User/Desktop/work/appslides/telegram_admin_bot/handlers/admin.py:1)
- [backend/src/integrations/admin_notifier.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/admin_notifier.py:1)

## Что обязательно передать следующей нейросети

Минимальный пакет:

- папку нового Telegram-бота по твоей тематике;
- [PRODUCT_ADAPTATION_GUIDE.md](C:/Users/User/Desktop/work/appslides/PRODUCT_ADAPTATION_GUIDE.md:1)
- [IMPLEMENTATION_RULES.md](C:/Users/User/Desktop/work/appslides/IMPLEMENTATION_RULES.md:1)
- [AGENT_HANDOFF.md](C:/Users/User/Desktop/work/appslides/AGENT_HANDOFF.md:1)
- [OPERATIONS.md](C:/Users/User/Desktop/work/appslides/OPERATIONS.md:1)
- [APPSLIDES_PLAN.md](C:/Users/User/Desktop/work/appslides/APPSLIDES_PLAN.md:1)

Если нужен визуальный контекст:

- [instructions/design_refs/telegram_bot_ui_brief.md](C:/Users/User/Desktop/work/appslides/instructions/design_refs/telegram_bot_ui_brief.md:1)
- [docs/images/readme_home.png](C:/Users/User/Desktop/work/appslides/docs/images/readme_home.png)
- [docs/images/readme_generation_step.png](C:/Users/User/Desktop/work/appslides/docs/images/readme_generation_step.png)
- [docs/images/readme_subscription.png](C:/Users/User/Desktop/work/appslides/docs/images/readme_subscription.png)

## Рекомендуемый порядок миграции

1. Изучить новый Telegram-бот как источник продуктовой логики.
2. Составить таблицу `что остается` / `что заменяется`.
3. Сначала обновить тексты, сценарии и сущности во Flutter chat flow.
4. Затем обновить product domain на backend.
5. Потом скорректировать admin-уведомления и статистику.
6. После этого проверить оплату, файлы, transcript restore и job flow.
7. В конце обновить README, store-материалы и deploy-доки.

## Быстрый чек-лист для новой тематики

- [ ] Переименовано приложение и бренд.
- [ ] Переписан стартовый чат-сценарий.
- [ ] Заменены кнопки и help-тексты.
- [ ] Заменены prompts и product logic на backend.
- [ ] Обновлены шаблоны/артефакты под новую тематику.
- [ ] Проверены платежи и лимиты.
- [ ] Проверены admin-уведомления.
- [ ] Проверено восстановление истории после перезапуска.
- [ ] Обновлены README и handoff-доки.

