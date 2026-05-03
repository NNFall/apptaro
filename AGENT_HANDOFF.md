# Agent Handoff

## Для чего этот файл

Этот файл нужен, когда проект передается другой нейросети или другому разработчику для адаптации под новую тематику.

Он отвечает не на вопрос `как устроен весь appslides`, а на вопрос:

`что именно нужно дать новому агенту и как сформулировать задачу, чтобы он не переписывал платформу с нуля`

## Что прикладывать новому агенту

Обязательно:

- папку Telegram-бота по новой тематике;
- [PRODUCT_ADAPTATION_GUIDE.md](C:/Users/User/Desktop/work/appslides/PRODUCT_ADAPTATION_GUIDE.md:1);
- [IMPLEMENTATION_RULES.md](C:/Users/User/Desktop/work/appslides/IMPLEMENTATION_RULES.md:1);
- [OPERATIONS.md](C:/Users/User/Desktop/work/appslides/OPERATIONS.md:1);
- [APPSLIDES_PLAN.md](C:/Users/User/Desktop/work/appslides/APPSLIDES_PLAN.md:1).

Желательно:

- [README.md](C:/Users/User/Desktop/work/appslides/README.md:1);
- [app/README.md](C:/Users/User/Desktop/work/appslides/app/README.md:1);
- [backend/README.md](C:/Users/User/Desktop/work/appslides/backend/README.md:1);
- [instructions/design_refs/telegram_bot_ui_brief.md](C:/Users/User/Desktop/work/appslides/instructions/design_refs/telegram_bot_ui_brief.md:1).

## Что должен понять новый агент

1. Текущий `appslides` уже является рабочим каркасом приложения.
2. Новая папка Telegram-бота является источником предметной логики.
3. Нельзя просто копировать Telegram-бот в Flutter один-в-один.
4. Нужно сохранить:
   - chat UX;
   - transcript persistence;
   - billing shell;
   - backend/deploy/admin infrastructure.
5. Нужно заменить:
   - продуктовые тексты;
   - сценарий;
   - prompts;
   - тип артефактов;
   - тематические backend-модули.

## Как ставить задачу следующему агенту

Готовая формулировка:

```text
У тебя есть два источника:
1. Текущий проект appslides — это уже готовый Flutter + backend + admin-bot каркас.
2. Папка с другим Telegram-ботом — это источник предметной логики под мою тематику.

Твоя задача:
- не переписывать платформу с нуля;
- сохранить chat UX, billing, local persistence, admin bot и deploy-процесс;
- взять из нового Telegram-бота тексты, сценарии, prompts, продуктовые сущности и продуктовые правила;
- адаптировать текущий appslides под новую тематику.

Сначала составь карту: что сохраняется, что заменяется.
Потом меняй Flutter chat flow.
Потом меняй product domain на backend.
Потом сверяй billing, file flow, transcript restore и admin notifications.
```

## На какие файлы нового агента направлять в первую очередь

### Flutter

- [app/lib/features/chat/chat_screen.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/chat/chat_screen.dart:1)
- [app/lib/features/billing/billing_controller.dart](C:/Users/User/Desktop/work/appslides/app/lib/features/billing/billing_controller.dart:1)
- [app/lib/data/api/appslides_api_client.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/api/appslides_api_client.dart:1)
- [app/lib/data/repositories/chat_transcript_repository.dart](C:/Users/User/Desktop/work/appslides/app/lib/data/repositories/chat_transcript_repository.dart:1)

### Backend

- [backend/src/api/presentations.py](C:/Users/User/Desktop/work/appslides/backend/src/api/presentations.py:1)
- [backend/src/domain/presentation_outline_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_outline_service.py:1)
- [backend/src/domain/presentation_render_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_render_service.py:1)
- [backend/src/domain/presentation_prompts.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/presentation_prompts.py:1)
- [backend/src/integrations/text_generation.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/text_generation.py:1)

### Инфраструктура

- [backend/src/domain/billing_service.py](C:/Users/User/Desktop/work/appslides/backend/src/domain/billing_service.py:1)
- [backend/src/integrations/admin_notifier.py](C:/Users/User/Desktop/work/appslides/backend/src/integrations/admin_notifier.py:1)
- [telegram_admin_bot/handlers/admin.py](C:/Users/User/Desktop/work/appslides/telegram_admin_bot/handlers/admin.py:1)
- [OPERATIONS.md](C:/Users/User/Desktop/work/appslides/OPERATIONS.md:1)

## Что просить от нового агента по этапам

### Этап 1. Анализ

Попросить:

- изучить новый Telegram-бот;
- составить таблицу `сохраняем / меняем`;
- определить, какие сущности заменяют презентации, outline, шаблоны и файлы результата.

### Этап 2. Flutter

Попросить:

- адаптировать стартовое сообщение, help и главное меню;
- адаптировать шаги chat flow;
- адаптировать file cards и кнопки;
- не ломать transcript persistence и local file flow.

### Этап 3. Backend

Попросить:

- заменить product domain;
- сохранить jobs, billing, admin notifications, storage и deploy;
- при необходимости временно оставить старые endpoint-имена для ускорения миграции.

### Этап 4. Проверка

Попросить:

- прогнать локальные проверки;
- описать риски;
- обновить документацию;
- закоммитить и при необходимости задеплоить backend.

## Чего новому агенту делать не надо

- не строить новый UI с нуля без запроса;
- не выкидывать отдельный admin bot;
- не ломать локальную историю;
- не убирать `client_id`;
- не переносить платежную логику в Flutter;
- не переписывать весь backend только ради новой тематики.

## Короткая мысль, которую нужно донести

Новая тематика должна заменять смысл продукта, а не платформу.
