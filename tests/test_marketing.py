"""Publieke marketing- en contentpagina's (websiteplan §8–§10) + SEO-routes.

Gebruikt dezelfde transactionele test-sessie als de andere web-tests (get_db override),
zodat het contactformulier-bericht na de test wordt teruggedraaid.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import ContactMessage
from app.web.main import app, get_db


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path,needle", [
    ("/hoe-het-werkt", "Eén keer instellen"),
    ("/premium", "Functies vergeleken"),
    ("/bestemmingen", "Goedkoop vliegen naar Europa"),
    ("/over-ons", "Hoe we geld verdienen"),
    ("/faq", "Veelgestelde vragen"),
    ("/contact", "Stuur ons een bericht"),
    ("/blog", "Reistips"),
    ("/privacy", "Privacyverklaring"),
    ("/voorwaarden", "Algemene voorwaarden"),
    ("/cookies", "Cookiebeleid"),
])
def test_public_pages_render(client, path, needle):
    resp = client.get(path)
    assert resp.status_code == 200
    assert needle in resp.text


def test_homepage_has_brand_and_signup_cta(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Vliegseintje" in resp.text
    assert "Goedkoop vliegen, zonder zoeken" in resp.text
    assert "Gratis aanmelden" in resp.text  # behoud van de bestaande CTA


def test_bestemmingen_origin_filter(client):
    resp = client.get("/bestemmingen", params={"origin": "EIN"})
    assert resp.status_code == 200
    assert "Eindhoven" in resp.text


def test_blog_post_renders_and_unknown_404(client):
    ok = client.get("/blog/wanneer-zijn-vliegtickets-het-goedkoopst")
    assert ok.status_code == 200
    assert "<h1>" in ok.text
    missing = client.get("/blog/bestaat-niet")
    assert missing.status_code == 404
    assert "niet gevonden" in missing.text.lower()


def test_faq_has_structured_data(client):
    resp = client.get("/faq")
    assert "FAQPage" in resp.text  # schema.org JSON-LD


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text
    assert "/blog/" in sitemap.text


def test_unknown_path_renders_html_404(client):
    resp = client.get("/zoiets-bestaat-niet")
    assert resp.status_code == 404
    assert "bestaat niet" in resp.text.lower()


def test_contact_valid_stores_message(db, client):
    resp = client.post("/contact", data={
        "name": "Tim", "email": "tim@example.nl", "message": "Een echte vraag over de dienst.",
    })
    assert resp.status_code == 200
    assert "bedankt" in resp.text.lower()
    count = db.execute(
        select(func.count()).select_from(ContactMessage).where(ContactMessage.email == "tim@example.nl")
    ).scalar_one()
    assert count == 1


def test_contact_honeypot_silently_drops(db, client):
    resp = client.post("/contact", data={
        "name": "Bot", "email": "bot@spam.nl", "message": "koop nu", "company": "evilcorp",
    })
    assert resp.status_code == 200
    count = db.execute(
        select(func.count()).select_from(ContactMessage).where(ContactMessage.email == "bot@spam.nl")
    ).scalar_one()
    assert count == 0


def test_contact_invalid_shows_error(client):
    resp = client.post("/contact", data={"name": "", "email": "geen-email", "message": "x"})
    assert resp.status_code == 400
    assert "geldig e-mailadres" in resp.text.lower()
