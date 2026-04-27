import os
import subprocess
import time
from typing import Optional

from services.logger import get_logger


logger = get_logger()


def _convert_pdf_to_docx_pdf2docx(input_path: str, output_path: str) -> Optional[str]:
    try:
        from pdf2docx import Converter  # type: ignore
    except Exception:  # noqa: BLE001
        logger.exception('pdf2docx import failed')
        return None

    try:
        logger.info('Convert fallback (pdf2docx): %s -> %s', input_path, output_path)
        conv = Converter(input_path)
        conv.convert(output_path, start=0, end=None)
        conv.close()
        if os.path.exists(output_path):
            logger.info('Convert done (pdf2docx): %s', output_path)
            return output_path
    except Exception:  # noqa: BLE001
        logger.exception('Convert failed (pdf2docx): %s', input_path)
        return None
    return None


def convert_file(
    input_path: str,
    output_ext: str,
    libreoffice_path: str,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    output_ext = output_ext.lower().lstrip('.')
    out_dir = output_dir or os.path.dirname(input_path)
    start_ts = time.time()
    cmd = [
        libreoffice_path,
        '--headless',
        '--convert-to',
        output_ext,
        '--outdir',
        out_dir,
        input_path,
    ]
    logger.info('Convert start: %s -> %s', input_path, output_ext)
    try:
        subprocess.run(cmd, check=True, timeout=300, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or '').strip()
        stdout = (exc.stdout or '').strip()
        logger.exception('Convert failed (libreoffice): %s', stderr or stdout or 'unknown error')
        if output_ext == 'docx' and input_path.lower().endswith('.pdf'):
            fallback_path = os.path.join(out_dir, f'{os.path.splitext(os.path.basename(input_path))[0]}.docx')
            return _convert_pdf_to_docx_pdf2docx(input_path, fallback_path)
        return None
    except Exception:  # noqa: BLE001
        logger.exception('Convert failed (libreoffice)')
        if output_ext == 'docx' and input_path.lower().endswith('.pdf'):
            fallback_path = os.path.join(out_dir, f'{os.path.splitext(os.path.basename(input_path))[0]}.docx')
            return _convert_pdf_to_docx_pdf2docx(input_path, fallback_path)
        return None
    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(out_dir, f'{base}.{output_ext}')
    if os.path.exists(output_path):
        logger.info('Convert done: %s', output_path)
        return output_path

    candidates = []
    base_lower = base.lower()
    ext_lower = f'.{output_ext.lower()}'
    try:
        for name in os.listdir(out_dir):
            if not name.lower().endswith(ext_lower):
                continue
            path = os.path.join(out_dir, name)
            try:
                if os.path.getmtime(path) < start_ts - 2:
                    continue
            except OSError:
                continue
            candidates.append(path)
    except OSError:
        candidates = []

    if candidates:
        def score(path: str) -> tuple[int, float]:
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            contains = 1 if base_lower in stem else 0
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = 0.0
            return (contains, mtime)

        best = max(candidates, key=score)
        logger.info('Convert done (fallback): %s', best)
        return best

    if output_ext == 'docx' and input_path.lower().endswith('.pdf'):
        fallback_path = os.path.join(out_dir, f'{base}.docx')
        fallback = _convert_pdf_to_docx_pdf2docx(input_path, fallback_path)
        if fallback:
            return fallback

    logger.info('Convert failed: no output file found')
    return None
