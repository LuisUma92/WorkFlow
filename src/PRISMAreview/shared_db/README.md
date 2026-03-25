# shared_db — Thin Adapter for workflow.db

This adapter lets PRISMAreview read bibliography data from the shared
`workflow.db` SQLite database without giving Django write or migration access.

## Overview

- The shared DB (`workflow.db`) is managed by the `latexzettel` module via
  SQLAlchemy. Django should treat it as read-only.
- `SharedDbRouter` redirects read queries for bibliography tables to the
  `'shared'` database alias. All writes continue to the default MariaDB.
- Django will **never** run migrations against the shared DB.

## Tables routed to `'shared'`

| Table                  | Description                  |
|------------------------|------------------------------|
| `bib_entries`          | Core bibliography records    |
| `author`               | Author names                 |
| `bib_author`           | Entry-author join table      |
| `isn_list`             | ISBNs / ISSNs                |
| `referenced_databases` | Source database references   |
| `url_list`             | Associated URLs              |
| `tags`                 | Entry tags                   |
| `keyword`              | Entry keywords               |

## Enabling the adapter (do NOT modify settings.py yet — add when ready)

Add the following to `pprsite/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        # ... existing MariaDB config ...
    },
    'shared': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'workflow.db',  # adjust path as needed
    },
}

DATABASE_ROUTERS = ['PRISMAreview.shared_db.router.SharedDbRouter']
```

## Important constraints

- **Do not run `migrate --database=shared`** — the schema is owned by SQLAlchemy.
- **Do not define new Django models** for the shared tables — PRISMAreview's
  existing models already map to them.
- The router returns `None` (defer to default behaviour) for anything outside
  the listed tables, so non-bibliography queries are unaffected.
