# apptaro Flutter Client

Flutter-клиент остается единым Telegram-style чатовым приложением. Новая предметная логика таро встроена поверх существующего chat shell без переписывания UI с нуля.

## Активный UX

- Один чат вместо набора продуктовых экранов.
- Пользователь может нажать `Задать вопрос` или просто написать вопрос в composer.
- Приложение показывает три карты расклада и предлагает открыть полный разбор или перетянуть карты.
- Если расклады закончились, paywall открывает YooKassa flow через backend.
- После оплаты pending context восстанавливается и генерация продолжается.
- Готовый результат приходит в чат как карточки файлов `JPG` и `TXT`.
- Trial teaser behavior: a brand-new unpaid client receives a one-card preview once.
- After the teaser is used, next questions in the same install return the standard three-card outline.
- Tarot image artifacts are rendered inline in chat messages and remain available as downloadable files.

## Сохраненные платформенные инварианты

- Transcript persistence хранит сообщения, inline-кнопки, pending paywall context и file cards.
- История чата восстанавливается после перезапуска приложения.
- Результаты скачиваются в app-specific storage и открываются системным приложением.
- `client_id` сохраняется локально и передается в backend как `X-AppSlides-Client-Id`.
- Billing остается backend-driven; Flutter только открывает checkout URL и poll-ит статус.
- Конвертер и старые сервисные экраны не удалены из платформы, но основной user-facing menu теперь ведет в tarot flow.

## Ключевые файлы

- `lib/features/chat/chat_screen.dart` - основной чат, onboarding, tarot flow, paywall, file cards.
- `lib/features/billing/billing_controller.dart` - YooKassa payment polling.
- `lib/features/presentation/presentation_controller.dart` - job flow, сохранен как совместимый слой для tarot reading.
- `lib/data/api/appslides_api_client.dart` - backend API client.
- `lib/data/repositories/chat_transcript_repository.dart` - persistent chat snapshot.
- `lib/data/repositories/saved_files_repository.dart` - локальное сохранение и открытие файлов.
- `lib/app/app_scope.dart` - DI для клиентских сервисов.

## Runtime

Клиент фиксированно подключается к production backend:

```text
http://185.171.83.116:8010
```

Локальное переключение backend URL в приложении намеренно не возвращалось.

## Проверки

```powershell
cd app
flutter analyze
flutter test
flutter build web
flutter build apk
```

`flutter run` является живой dev-сессией и не завершается сам; останавливать через `q` в терминале.
