# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PRISMAreview (P-REVIEW) is a personal implementation of the PRISMA-2020 systematic review methodology. It is a Django 5.0 web application backed by MariaDB that manages bibliographic entries, conducts literature reviews, and tracks PRISMA compliance.

## Commands

All commands run from `pprsite/` (where `manage.py` lives):

```bash
cd pprsite
python manage.py runserver            # Dev server (default port 8000)
python manage.py migrate              # Apply migrations
python manage.py makemigrations       # Generate migrations after model changes
python manage.py test                 # Run all tests
python manage.py test prismadb        # Run tests for a single app
python manage.py createsuperuser      # Create admin user
```

No `requirements.txt` or `pyproject.toml` exists. Key dependencies: Django 5.0, mysql-connector-python, bibtexparser, pandas, djangorestframework, channels.

## Architecture

```
pprsite/                          # Django project root (manage.py)
├── pprsite/                      # Project config (settings, root urls, asgi/wsgi)
├── prismadb/                     # Core app: models, custom ORM (ppORM.py), WebSocket consumers
├── addbib/                       # Bibliography import: BibTeX upload, parsing, WebSocket routing
├── review/                       # Systematic review interface & PRISMA utilities
├── home/                         # Landing page
├── inspectdatabase/              # Database browser/inspection tool
├── templates/                    # Shared HTML templates
└── bibFiles/                     # Static BibTeX file storage
```

### URL routing

| Path | App | Purpose |
|------|-----|---------|
| `/` | home | Landing page |
| `/importBib/` | addbib | Upload & process BibTeX files |
| `/review/` | review | Systematic review interface |
| `/inspect/` | inspectdatabase | Browse stored entries |
| `/admin/` | django.contrib.admin | Django admin |

### Key patterns

- **Custom ORM layer**: `prismadb/ppORM.py` wraps Django ORM with BibTeX-specific logic.
- **Consumer pattern**: `prismadb/consumers.py` has `BibEntryProcessor` that encapsulates entry creation/update logic, used via Django Channels WebSocket.
- **Session-based processing**: Multi-step BibTeX file upload uses Django sessions to hold state between requests.
- **WebSocket support**: Django Channels with `InMemoryChannelLayer` (single-process only). Routing in `addbib/routing.py`.

### Data model (prismadb/models.py)

Core models: `Bib_entries` (bibliography records), `Author` (unique on first+last name pair), `Author_type` (roles: author/editor/translator), `Tags`, `Isn_list` (ISBN/ISSN), `Referenced_databases`, `Abstract` (with background/discussion/conclusion fields).

## Database

MariaDB on `localhost:3306`, database `prisma`, user `luis`. Credentials are hardcoded in `settings.py` (dev-only setup).
