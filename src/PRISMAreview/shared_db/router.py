from __future__ import annotations


class SharedDbRouter:
    """Route bibliography reads to the shared workflow.db SQLite."""

    SHARED_MODELS = {
        'bib_entries',
        'author',
        'bib_author',
        'isn_list',
        'referenced_databases',
        'url_list',
        'tags',
        'keyword',
    }

    def db_for_read(self, model, **hints):
        if model._meta.db_table in self.SHARED_MODELS:
            return 'shared'
        return None

    def db_for_write(self, model, **hints):
        # Writes always go to default (MariaDB) for now
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'shared':
            return False  # Never migrate the shared DB via Django
        return None
