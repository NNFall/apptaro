# Baseline Checks - 2026-07-06

Проверки выполнены до изменения продуктовой логики Google Play адаптации.

## Commands

```powershell
python -m unittest discover -s backend/tests -v
python -m compileall backend/src telegram_admin_bot
cd app
flutter pub get
flutter test
flutter analyze
```

## Results

- Backend tests: 11 tests, OK.
- Backend/admin compile: OK.
- Flutter pub get: OK.
- Flutter test: 1 widget test, OK.
- Flutter analyze: no issues found.

## Notes

- `flutter pub get` сообщает, что `flutter_markdown` discontinued.
- Есть newer package versions, несовместимые с текущими constraints.
- Эти предупреждения не блокируют старт Google Play адаптации.
