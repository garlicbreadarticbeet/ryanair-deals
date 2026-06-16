"""Gedeelde HTTP-helper. Netwerkcalls gaan via requests (+certifi), nooit urllib
(harde regel uit de overdracht). Eén plek zodat providers én kanalen dezelfde
certifi-CA's gebruiken.
"""
from __future__ import annotations

import certifi
import requests


def get_session() -> requests.Session:
    """Een requests-sessie met expliciete certifi-CA-bundle."""
    session = requests.Session()
    session.verify = certifi.where()
    return session
