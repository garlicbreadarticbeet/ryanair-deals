"""Laadt de statische website-content (blog, legal, FAQ, voorbeeld-bestemmingen).

Content staat als bestanden onder ``app/web/content/`` zodat tekst los van de code te
onderhouden is (de "content-motor" uit het websiteplan §10.5/§10.8):

- ``blog/<slug>.md``   — Markdown met een simpele frontmatter (title/excerpt/date/tags).
- ``legal/<slug>.md``  — Markdown met frontmatter (title). Placeholder-teksten met [TODO]'s.
- ``faq.json``         — gegroepeerde vragen (FAQPage-schema voert hierop).
- ``destinations.json``— VOORBEELD-bestemmingen voor ``/bestemmingen`` en de homepage.

Markdown wordt met de ``markdown``-library naar HTML gerenderd. Resultaten zijn gecachet
(de bestanden veranderen niet tijdens runtime).
"""
from __future__ import annotations

import datetime
import functools
import json
from dataclasses import dataclass
from pathlib import Path

import markdown as _md

_CONTENT_DIR = Path(__file__).resolve().parent / "content"
_MD_EXTENSIONS = ["extra", "sane_lists"]

# Populaire bestemmingslanden (NL-naam + ISO alpha-2, lowercase = zoals opgeslagen) voor de
# vriendelijke landen-kiezer op /preferences. Volgorde ~ populariteit als citytrip-/zonland.
DEST_COUNTRIES = [
    {"code": "es", "name": "Spanje"}, {"code": "pt", "name": "Portugal"},
    {"code": "it", "name": "Italië"}, {"code": "gr", "name": "Griekenland"},
    {"code": "fr", "name": "Frankrijk"}, {"code": "hr", "name": "Kroatië"},
    {"code": "de", "name": "Duitsland"}, {"code": "at", "name": "Oostenrijk"},
    {"code": "hu", "name": "Hongarije"}, {"code": "pl", "name": "Polen"},
    {"code": "cz", "name": "Tsjechië"}, {"code": "ie", "name": "Ierland"},
    {"code": "gb", "name": "Verenigd Koninkrijk"}, {"code": "ro", "name": "Roemenië"},
    {"code": "bg", "name": "Bulgarije"}, {"code": "mt", "name": "Malta"},
    {"code": "ma", "name": "Marokko"}, {"code": "tr", "name": "Turkije"},
    {"code": "cy", "name": "Cyprus"}, {"code": "se", "name": "Zweden"},
    {"code": "dk", "name": "Denemarken"}, {"code": "no", "name": "Noorwegen"},
    {"code": "fi", "name": "Finland"}, {"code": "lv", "name": "Letland"},
    {"code": "lt", "name": "Litouwen"}, {"code": "ee", "name": "Estland"},
    {"code": "si", "name": "Slovenië"}, {"code": "sk", "name": "Slowakije"},
    {"code": "be", "name": "België"}, {"code": "nl", "name": "Nederland"},
]

# Vriendelijke namen voor de vertrekvelden (alleen UI; geen logica hangt eraan).
ORIGIN_NAMES = {
    "EIN": "Eindhoven", "NRN": "Weeze", "AMS": "Amsterdam", "BRU": "Brussel",
    "CRL": "Charleroi", "MST": "Maastricht", "GRQ": "Groningen", "ANR": "Antwerpen",
}


@dataclass(frozen=True)
class BlogPost:
    slug: str
    title: str
    excerpt: str
    date: datetime.date
    tags: tuple[str, ...]
    html: str = ""

    @property
    def date_label(self) -> str:
        maanden = ["", "januari", "februari", "maart", "april", "mei", "juni", "juli",
                   "augustus", "september", "oktober", "november", "december"]
        return f"{self.date.day} {maanden[self.date.month]} {self.date.year}"


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Splits een simpele ``---``-frontmatter (key: value per regel) van de body."""
    if not text.startswith("---"):
        return {}, text
    _, _, rest = text.partition("---\n")
    fm_block, sep, body = rest.partition("\n---")
    if not sep:
        return {}, text
    meta: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def _render_md(body: str) -> str:
    return _md.markdown(body, extensions=_MD_EXTENSIONS, output_format="html5")


@functools.lru_cache(maxsize=1)
def blog_index() -> list[BlogPost]:
    """Alle blogposts (zonder body-HTML), nieuwste eerst."""
    posts: list[BlogPost] = []
    blog_dir = _CONTENT_DIR / "blog"
    for path in blog_dir.glob("*.md"):
        meta, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
        try:
            date = datetime.date.fromisoformat(meta.get("date", ""))
        except ValueError:
            date = datetime.date.today()
        tags = tuple(t.strip() for t in meta.get("tags", "").split(",") if t.strip())
        posts.append(BlogPost(
            slug=path.stem, title=meta.get("title", path.stem),
            excerpt=meta.get("excerpt", ""), date=date, tags=tags,
        ))
    return sorted(posts, key=lambda p: p.date, reverse=True)


@functools.lru_cache(maxsize=32)
def blog_post(slug: str) -> BlogPost | None:
    """Eén blogpost inclusief gerenderde HTML-body, of None als hij niet bestaat."""
    path = _CONTENT_DIR / "blog" / f"{slug}.md"
    if not path.is_file():
        return None
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    try:
        date = datetime.date.fromisoformat(meta.get("date", ""))
    except ValueError:
        date = datetime.date.today()
    tags = tuple(t.strip() for t in meta.get("tags", "").split(",") if t.strip())
    return BlogPost(
        slug=slug, title=meta.get("title", slug), excerpt=meta.get("excerpt", ""),
        date=date, tags=tags, html=_render_md(body),
    )


@functools.lru_cache(maxsize=16)
def legal_doc(slug: str) -> dict | None:
    """Een juridische placeholder-pagina ({title, html}) of None."""
    path = _CONTENT_DIR / "legal" / f"{slug}.md"
    if not path.is_file():
        return None
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return {"title": meta.get("title", slug.title()), "html": _render_md(body)}


@functools.lru_cache(maxsize=1)
def faq_groups() -> list[dict]:
    data = json.loads((_CONTENT_DIR / "faq.json").read_text(encoding="utf-8"))
    return data.get("groups", [])


@functools.lru_cache(maxsize=1)
def destinations() -> list[dict]:
    data = json.loads((_CONTENT_DIR / "destinations.json").read_text(encoding="utf-8"))
    return data.get("destinations", [])
