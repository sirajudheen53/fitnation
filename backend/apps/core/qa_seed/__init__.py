"""QA seeding package used by the ``seed_qa`` management command.

Modules are settings-agnostic (no ``DJANGO_SETTINGS_MODULE`` manipulation) and
idempotent (safe to re-run). They operate on whatever database the active
Django settings point at — local SQLite, QA Postgres, or Cloud Run.
"""
