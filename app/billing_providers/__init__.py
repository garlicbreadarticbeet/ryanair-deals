"""Betaalproviders achter één BillingProvider-interface (Lemon Squeezy, Mollie).

Net als providers/ (maatschappijen) en channels/ (bezorgkanalen): een nieuwe betaalprovider
is één nieuw bestand hier met een @register_billing_provider-klasse. app/billing.py kiest op
``settings.billing_provider`` de juiste provider; app/core/ kent geen betaalprovider.
"""
