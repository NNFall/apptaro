from __future__ import annotations

from pathlib import Path


def list_presentation_templates(templates_dir: Path) -> list[dict[str, str | int | bool | None]]:
    items: list[dict[str, str | int | bool | None]] = []
    for index in range(1, 5):
        template_path = templates_dir / f'design_{index}.pptx'
        preview_path = templates_dir / f'preview_{index}.jpg'
        items.append(
            {
                'id': index,
                'name': f'Шаблон {index}',
                'template_path': str(template_path) if template_path.exists() else None,
                'preview_path': str(preview_path) if preview_path.exists() else None,
                'template_available': template_path.exists(),
                'preview_available': preview_path.exists(),
            }
        )
    return items
