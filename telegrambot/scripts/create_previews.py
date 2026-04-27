import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image


def _convert_to_png(src_path: str, out_dir: str, libreoffice: str) -> str:
    cmd = [
        libreoffice,
        '--headless',
        '--convert-to',
        'png',
        '--outdir',
        out_dir,
        src_path,
    ]
    subprocess.run(cmd, check=True, timeout=300)
    base = os.path.splitext(os.path.basename(src_path))[0]
    png_path = os.path.join(out_dir, f'{base}.png')
    if not os.path.exists(png_path):
        # LibreOffice might add -1 suffix for slide index
        alt = os.path.join(out_dir, f'{base}-1.png')
        if os.path.exists(alt):
            return alt
    return png_path


def main() -> None:
    libreoffice = os.getenv('LIBREOFFICE_PATH', 'soffice')
    templates_dir = Path('media') / 'templates'
    templates_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, 5):
        src = templates_dir / f'design_{i}.pptx'
        if not src.exists():
            print('skip missing', src)
            continue
        png_path = _convert_to_png(str(src), str(templates_dir), libreoffice)
        if not os.path.exists(png_path):
            print('png not found for', src)
            continue
        img = Image.open(png_path).convert('RGB')
        jpg_path = templates_dir / f'preview_{i}.jpg'
        img.save(jpg_path, quality=90)
        print('created', jpg_path)
        try:
            os.remove(png_path)
        except OSError:
            pass


if __name__ == '__main__':
    main()
