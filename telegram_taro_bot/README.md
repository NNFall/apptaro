# Таро-бот — Telegram SaaS

## Что делает бот
- Пользователь задает вопрос.
- Бот сразу открывает первую карту и делает разбор.
- Далее предлагает оформить подписку, после оплаты раскрывает 2-ю и 3-ю карты и продолжает разбор.
- Подписки:
  - 15 раскладов / 7 дней / 199 ₽
  - 100 раскладов / 30 дней / 499 ₽
- Оплата: YooKassa (автосписание) и Telegram Stars (разово).

## Ядро платформы
Сохранено без изменения:
- deeplink-атрибуция (`ref_`, `promo_`, `utm`)
- подписки и продления
- pending_actions после оплаты
- админ-логи и команды управления
- smart-рассылка

## Медиа таро
- Карты: `media/tarot/cards`
- Фон: `media/tarot/backgrounds/main.png`
- Шаблон расклада: `media/tarot/layout.json`

Имя файла карты используется как название карты в тексте.

## Подгонка координат карт
Скрипт предпросмотра:

```bash
python tools/tarot_layout_preview.py --out media/temp/tarot_layout_preview.jpg
```

Переопределение слота:

```bash
python tools/tarot_layout_preview.py --slot1 "230,140,260,440,-6" --slot2 "510,120,260,440,0" --slot3 "790,140,260,440,6"
```

Формат слота: `x,y,width,height,angle`.

## Команды пользователя
- `/start`
- `/menu`
- `/ask`
- `/balance`
- `/help`
- `/invite`

## Запуск
```bash
pip install -r requirements.txt
python main.py
```

## Настройка текстовой LLM
- Основной провайдер: `KIE_BASE_URL` + `KIE_TEXT_MODEL` + `KIE_API_KEY`
- Фолбэк: `REPLICATE_BASE_URL` + `REPLICATE_TEXT_MODEL` + `REPLICATE_API_TOKEN`
- Альтернатива через fixed version: `REPLICATE_TEXT_VERSION`
- Промпты лежат в `prompts/tarot_prompts.py`
- Формат ответа LLM: Telegram Markdown

Проверка text-LLM цепочки:
```bash
python tools/test_text_llm.py --mode teaser
python tools/test_text_llm.py --mode full
```

## Docker
```bash
docker compose up -d --build
docker compose logs -f bot
```
