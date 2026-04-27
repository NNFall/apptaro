import os
import json
import requests
from dotenv import load_dotenv

load_dotenv('.env')

api_key = os.getenv('KIE_API_KEY')
base_url = os.getenv('KIE_BASE_URL', 'https://api.kie.ai')
model = os.getenv('KIE_TEXT_MODEL', 'gemini-3-flash')
endpoint = os.getenv('KIE_TEXT_ENDPOINT') or f'{base_url}/{model}/v1/chat/completions'

if not api_key:
    raise SystemExit('KIE_API_KEY not set')

payload = {
    'messages': [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Скажи одно короткое предложение для теста.'}
            ],
        }
    ],
}

resp = requests.post(
    endpoint,
    headers={'Authorization': f'Bearer {api_key}'},
    json=payload,
    timeout=120,
)

print('status:', resp.status_code)
resp.raise_for_status()

data = resp.json()
print('keys:', list(data.keys()))
if 'choices' in data and data['choices']:
    msg = data['choices'][0].get('message', {})
    content = msg.get('content', '')
    print('content:', json.dumps(str(content)[:120], ensure_ascii=False))
else:
    print('response:', json.dumps(data, ensure_ascii=False))
