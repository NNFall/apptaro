import os
import sys
from pathlib import Path

import json

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.replicate_api import ReplicateClient  # noqa: E402

load_dotenv('.env')

api_token = os.getenv('REPLICATE_API_TOKEN')
if not api_token:
    raise SystemExit('REPLICATE_API_TOKEN not set')

def _parse_json(value: str) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


default_input = _parse_json(os.getenv('REPLICATE_DEFAULT_INPUT', ''))

client = ReplicateClient(
    api_token=api_token,
    base_url=os.getenv('REPLICATE_BASE_URL', 'https://api.replicate.com'),
    model=os.getenv('REPLICATE_MODEL', 'black-forest-labs/flux-schnell'),
    wait_seconds=int(os.getenv('REPLICATE_WAIT_SECONDS', '60')),
    poll_interval=float(os.getenv('REPLICATE_POLL_INTERVAL', '1.5')),
    timeout_seconds=int(os.getenv('REPLICATE_TIMEOUT_SECONDS', '120')),
    default_input=default_input,
)

url = client.generate_image('Простой тестовый кадр, нейтральный фон, без текста.')
print('image_url:', url[:120])
