"""Server-rendered templating via een eigen Jinja2-Environment.

Bewust niet via Starlette's Jinja2Templates (waarvan de TemplateResponse-signatuur wisselt);
render() geeft direct een HTMLResponse terug op basis van de templatenaam + context.
"""
from __future__ import annotations

from pathlib import Path

import jinja2
from fastapi.responses import HTMLResponse

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(Path(__file__).resolve().parent / "templates")),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(name: str, status_code: int = 200, **context) -> HTMLResponse:
    """Render een template naar een HTMLResponse."""
    html = _env.get_template(name).render(**context)
    return HTMLResponse(html, status_code=status_code)
