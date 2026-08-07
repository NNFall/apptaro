# Отказ App Store от 6 августа 2026 года

## Состояние отправки

- Приложение: `Tarot Reader AI: Card Reading`.
- Версия: `1.0`.
- Проверенная сборка: `21`.
- Submission ID: `f96ae908-7b4c-4a34-898a-4c4c3f0f0b5e`.
- Устройства Apple: iPad Air 11-inch (M3) и iPhone 17 Pro Max.
- Причины отказа: `2.1(a) App Completeness` и `4.3(b) Design - Spam`.

## 2.1(a): ошибка кнопки Balance

Сборка 21 обращалась к backend по адресу:

```text
https://185-171-83-116.sslip.io:8443
```

В журнале выделенного Nginx и в логах ASapptaro backend нет запроса Apple к
`/v1/billing/summary` во время проверки. Значит ошибка происходила до API:
на DNS/TLS/сетевом соединении с wildcard IP hostname и нестандартным портом.

Исправление для сборки 22:

1. Production endpoint заменён на собственный hostname:
   `https://slide-maker-ai.com:8443`.
2. Добавлен отдельный TLS virtual host для ASapptaro без изменения Xray и
   остальных проектов сервера.
3. GET-запросы получили ограниченный timeout и до трёх попыток при временных
   сетевых ошибках и ответах `408`, `425`, `429`, `500`, `502`, `503`, `504`.
4. Пользователю больше не показывается `ClientException`: отображается
   локализованное сообщение и кнопки `Retry`/`Main Menu`.
5. Release-check и runtime запрещают iOS-сборки с прямым IP, `sslip.io` и
   `nip.io`.

Серверная конфигурация хранится в:

- `deploy/apple/nginx-asapptaro-8443.conf`;
- `deploy/apple/nginx-asapptaro-proxy.conf`.

Рабочий systemd unit: `nginx-asapptaro.service`. Backend проксируется на
`127.0.0.1:8023`.

Перед повторной отправкой сборку 22 нужно установить из TestFlight на iPhone и
iPad, открыть чистое приложение и проверить кнопку `Balance` минимум два раза:
при первом запуске и после повторного запуска приложения.

### Ответ ревьюеру по 2.1(a)

```text
Hello,

We fixed the Balance screen connectivity issue in build 22. The iOS app now
uses our owned production hostname, https://slide-maker-ai.com:8443, instead of
the previous wildcard IP hostname. We also added bounded retries for transient
GET failures and a user-friendly retry state.

We verified the production health and billing summary endpoints from macOS,
validated the endpoint with the default App Transport Security diagnostics,
and tested the Balance flow in a clean release installation.

Steps to verify:
1. Launch the app.
2. Tap Balance.
3. The current balance and Apple purchase options are displayed.

No account or special setup is required.
```

Последнее предложение о clean release installation можно оставлять только
после фактической проверки сборки 22 через TestFlight.

## 4.3(b): насыщенная категория

Это не техническая ошибка и не проблема метаданных. Apple прямо указала, что
обычный сервис раскладов Таро/гаданий дублирует уже представленные приложения.
Повторная отправка того же сценария с другим названием, иконкой или описанием не
устранит причину отказа.

Реалистичные варианты:

1. Рекомендуемый: добавить самостоятельный сценарий принятия решений и
   рефлексии. Пользователь фиксирует факты, чувства и варианты, получает
   карточный разбор, выбирает конкретное действие и возвращается к результату
   через локальный журнал и check-in. Карты становятся частью уникального
   процесса, а не единственной функцией гадания.
2. Подать апелляцию, подробно объяснив отличия текущего продукта. Вероятность
   успеха ограничена, потому что текущий основной сценарий всё ещё является
   стандартным трёхкарточным раскладом.
3. Оставить продукт web/PWA, как предложила Apple.

До выбора и реализации варианта по `4.3(b)` нельзя повторно отправлять ту же
версию: технический баг будет закрыт, но концептуальный отказ останется.
