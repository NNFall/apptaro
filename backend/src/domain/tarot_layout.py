from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src.domain.tarot_deck import DrawnCard


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CardSlot:
    x: int
    y: int
    width: int
    height: int
    angle: float = 0.0


@dataclass(frozen=True)
class TarotLayout:
    canvas_width: int
    canvas_height: int
    background: str | None
    slots: list[CardSlot]


DEFAULT_LAYOUT = TarotLayout(
    canvas_width=1280,
    canvas_height=720,
    background=None,
    slots=[
        CardSlot(x=150, y=130, width=300, height=500, angle=-4.0),
        CardSlot(x=490, y=110, width=300, height=500, angle=0.0),
        CardSlot(x=830, y=130, width=300, height=500, angle=4.0),
    ],
)


def load_layout(layout_path: str | Path) -> TarotLayout:
    path = Path(layout_path)
    if not path.exists():
        return DEFAULT_LAYOUT

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return DEFAULT_LAYOUT

    raw_slots = payload.get('slots') if isinstance(payload, dict) else None
    if not isinstance(raw_slots, list) or len(raw_slots) < 3:
        return DEFAULT_LAYOUT

    slots = [
        CardSlot(
            x=int(slot.get('x', 0)),
            y=int(slot.get('y', 0)),
            width=int(slot.get('width', 200)),
            height=int(slot.get('height', 340)),
            angle=float(slot.get('angle', 0.0)),
        )
        for slot in raw_slots[:3]
    ]
    return TarotLayout(
        canvas_width=int(payload.get('canvas_width', DEFAULT_LAYOUT.canvas_width)),
        canvas_height=int(payload.get('canvas_height', DEFAULT_LAYOUT.canvas_height)),
        background=payload.get('background') or DEFAULT_LAYOUT.background,
        slots=slots,
    )


def _background_candidates(
    layout: TarotLayout,
    fallback_background_path: str | Path,
    layout_base_dir: Path,
) -> list[Path]:
    candidates: list[Path] = []
    raw_candidates: list[Path] = []

    if layout.background:
        bg_path = Path(layout.background)
        if bg_path.is_absolute():
            raw_candidates.append(bg_path)
        else:
            raw_candidates.append(layout_base_dir / bg_path)
            raw_candidates.append(bg_path)

    fallback = Path(fallback_background_path)
    if fallback.is_absolute():
        raw_candidates.append(fallback)
    else:
        raw_candidates.append(layout_base_dir / fallback)
        raw_candidates.append(fallback)

    seen: set[str] = set()
    for candidate in raw_candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def _open_background(
    layout: TarotLayout,
    fallback_background_path: str | Path,
    layout_base_dir: Path,
) -> Image.Image:
    for bg_file in _background_candidates(layout, fallback_background_path, layout_base_dir):
        if not bg_file.exists():
            continue
        try:
            bg = Image.open(bg_file).convert('RGBA')
            if bg.size != (layout.canvas_width, layout.canvas_height):
                bg = bg.resize((layout.canvas_width, layout.canvas_height), Image.Resampling.LANCZOS)
            return bg
        except Exception as exc:
            logger.warning('Tarot background open failed path=%s error=%s', bg_file, exc)

    return Image.new('RGBA', (layout.canvas_width, layout.canvas_height), (30, 31, 54, 255))


def compose_spread_image(
    drawn_cards: list[DrawnCard],
    output_path: str | Path,
    layout_path: str | Path,
    background_path: str | Path,
) -> Path:
    if len(drawn_cards) < 3:
        raise ValueError('Three drawn cards required')

    layout_file = Path(layout_path)
    layout = load_layout(layout_file)
    canvas = _open_background(layout, background_path, layout_file.resolve().parent)

    for idx, drawn in enumerate(drawn_cards[:3]):
        slot = layout.slots[idx]
        card_img = Image.open(drawn.card.image_path).convert('RGBA')
        card_img = card_img.resize((slot.width, slot.height), Image.Resampling.LANCZOS)
        if drawn.is_reversed:
            card_img = card_img.rotate(180, expand=True, resample=Image.Resampling.BICUBIC)
        if slot.angle:
            card_img = card_img.rotate(slot.angle, expand=True, resample=Image.Resampling.BICUBIC)

        x = slot.x + (slot.width - card_img.width) // 2
        y = slot.y + (slot.height - card_img.height) // 2
        canvas.alpha_composite(card_img, (x, y))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(out, format='JPEG', quality=95)
    return out
