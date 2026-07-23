import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / 'docs' / 'store' / 'app-store' / 'metadata.json'
STANDARD_EULA_URL = (
    'https://www.apple.com/legal/internet-services/itunes/dev/stdeula/'
)


def test_every_app_store_description_contains_standard_eula_link():
    metadata = json.loads(METADATA_PATH.read_text(encoding='utf-8'))

    missing_locales = [
        locale
        for locale, localization in metadata['localizations'].items()
        if STANDARD_EULA_URL not in localization['description']
    ]

    assert missing_locales == []
