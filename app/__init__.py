"""Multi-user kern van de Ryanair-deal-dienst.

Pakketstructuur:
  app.settings   — centrale configuratie via env (pydantic-settings)
  app.providers  — maatschappij-adapters achter één FlightProvider-interface
  app.core       — provider- en kanaal-onafhankelijke logica (combine, match, dedup, gating)
  app.channels   — bezorgkanalen achter één Notifier-interface
  app.db         — SQLAlchemy-modellen, sessie en seed
  app.web        — FastAPI-app (health, magic-link, voorkeuren)
  app.worker     — scan -> match -> notify-loop
"""
