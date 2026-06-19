"""Bezorgkanalen achter één Notifier-interface (Telegram, e-mail).

De abstractie blijft uitbreidbaar: een nieuw kanaal = één nieuw bestand met een
@register_notifier-klasse (zie app/channels/base.py).
"""
