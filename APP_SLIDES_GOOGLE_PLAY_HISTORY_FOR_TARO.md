# AppSlides Google Play History Notes For PMapptaro

Этот файл фиксирует практические уроки из предыдущей адаптации приложения по презентациям под Google Play. Его задача - не описывать старый проект полностью, а сохранить решения, которые нужно повторить или учесть в Tarot Google Play версии.

## Что сработало

- Для Google Play нужна отдельная версия проекта, backend и серверная папка. Смешивать RuStore/YooKassa и Google Play billing в одном production-контуре рискованно.
- Flutter-клиент должен подключаться к фиксированному backend Google Play версии, без пользовательского выбора сервера.
- Все пользовательские тексты для Google Play нужно переводить на английский до загрузки скриншотов и AAB.
- `AAB` используется для Google Play Console; `APK` нужен только для ручной установки и теста.
- `versionCode` должен расти при каждой новой сборке.
- Admin bot удобнее держать отдельным контейнером, но он должен читать ту же базу, что и backend Google Play версии.
- Service account Google Play должен иметь права на просмотр финансовых данных и управление заказами/подписками.

## Что вызвало проблемы

- Google Play Billing не заработает надежно, если покупка подтверждается только на клиенте.
- Если покупка была сделана до исправления backend/client sync, пользователь может переустановить приложение, но Google Play все равно считает подписку уже купленной. Клиент обязан обработать restored/owned purchase и повторно отправить purchase token на backend.
- Видимая кнопка restore может путать пользователя. Лучше делать silent restore при попытке купить тариф или при синхронизации billing.
- Backend может упасть после deploy, если локальная версия класса/зависимостей не совпадает с тем, что уже есть на сервере. Перед deploy нужно проверять diff и remote logs.
- Нельзя перезаписывать remote `.env` автоматически, если в нем есть production secrets или Google service account settings.
- Google Play review может отклонить страницу, если иконка, featured graphic или screenshots похожи на чужие бренды/продукты.

## Что нужно повторить в PMapptaro

- Создать отдельный Google Play backend на сервере.
- Использовать отдельную SQLite базу и отдельный `data/`.
- Добавить Google Play billing verification endpoint.
- Добавить backend notification admins for payment success/failure/restore.
- Проверять purchase token на backend.
- Делать silent restore.
- Повышать build number при каждой сборке.
- Проверять release build до загрузки.

## Что нужно сделать лучше, чем в прошлом проекте

- Не начинать Google Play billing до завершения базовой английской локализации.
- Сразу заложить multi-language архитектуру, а не просто заменить русские строки на английские.
- Сразу разделить RuStore и Google Play config: package id, backend URL, billing provider, offer links, support links, admin bot token.
- Сразу документировать, какой backend и какая база относятся к Google Play версии.
- Перед удалением любых данных на сервере явно проверять путь: `/root/PMapptaro`, а не соседние проекты.

## Минимальный definition of done для первого Google Play MVP

- Приложение запускается на Android Emulator.
- Весь пользовательский UI на английском.
- Tarot prompts отвечают на английском.
- Подписка покупается через Google Play тестовый трек.
- Backend видит покупку и начисляет entitlement.
- Повторная установка/очистка данных не теряет купленную подписку после sync.
- Admin bot получает уведомления о новом пользователе, раскладе, покупке, ошибке оплаты и restore.
- AAB загружается в Google Play Console без policy очевидных нарушений.
