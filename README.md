# Dismantling

A minimal Django starter for the literary diptych project **ДЕМОНТАЖ**.
It uses SQLite to store all editorial content, Django Admin to edit poems and
documentary quotations in Markdown, and custom CSS/vanilla JavaScript for the
public pages. There are no example literary texts: add your own through Admin.

## Run locally on Debian

Requirements: Docker Engine with the Docker Compose plugin.

If you already initialized `~/Documents/dismantling` locally, update it:

```bash
cd ~/Documents/dismantling
git pull --ff-only origin main
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

For a new checkout, use:

```bash
git clone git@github.com:EugenefedorovPro/dismantling.git
cd dismantling
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

- Website: http://127.0.0.1:8088/
- Admin: http://127.0.0.1:8088/admin/

In Django Admin, open **Diptychs**, create a record, enter a Latin URL slug,
paste your Markdown poem, add one or more documentary excerpts (with URLs),
and select **Is published**. The title page and diptych page update when saved.

### Export texts or back up the database

Log in to the Django Admin **homepage** as a superuser. The **Project exports**
section has two one-click downloads for the entire site:

- **Export all texts (.txt)**: a UTF-8 text file containing all poems (including
  unpublished drafts), document quotations and sources, author biographies,
  project descriptions, and available translations.
- **Backup database (.sqlite3)**: a consistent copy of the entire SQLite
  database, including accounts and other Django tables, made using SQLite's
  online backup API. Treat this file as sensitive and store it securely.

Both downloads are restricted to superusers. Neither changes the live database.

The local port is bound to `127.0.0.1`, so the test site is not exposed to your
LAN. Change `WEB_PORT` in `.env` to use another port (copy `.env.example`
to `.env` first). You do **not** need an `.env` file for local testing.

```bash
docker compose logs -f web            # read logs
docker compose down                   # stop containers; keep SQLite data
docker compose up -d                  # start again
docker compose exec web python manage.py test  # run tests
```

SQLite is stored in the named Docker volume `sqlite_data`, not in the Git
repository. **Do not run `docker compose down -v`** unless you intend to delete
the database volume and its contents. Back up the database separately.

## Development and deployment notes

- Python 3.13, Django 5.2 LTS, Gunicorn, WhiteNoise, Markdown-It-Py.
- SQLite: `Diptych` (poem, date, order, publication flag) and `DocumentExcerpt`
  (one or more verbatim quotations, with titles and source URLs).
- The Markdown renderer escapes raw HTML and avoids unsafe link schemes.
  Soft line breaks in poems are rendered as actual line breaks.
- HTML templates live in `templates/`, CSS/JS in `static/`, models and Admin
  in `diptychs/`.
- Django's built-in Admin provides editing. A live Markdown preview can be
  added later; it is not included in this initial starter.
- The included design is a functional starting point, not a finalized visual
  treatment for the title page or diptychs. The named fonts currently use
  system fallbacks until local font files are added.
- The Compose configuration is intended for **local testing**. Before a
  public deployment, set a unique `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0`,
  configure `DJANGO_ALLOWED_HOSTS`, HTTPS/reverse-proxy settings, and database
  backups. The HTTPS reverse proxy (Nginx) is **not** included here.
- Application source code lives in GitHub. Your production texts reside only
  in the SQLite database unless you export or back them up.

## CI/CD for the kant VPS

GitHub Actions can automatically deploy a tested push to `main` to
`dismantle.rhyme.kyiv.ua` on the `kant` VPS. See
[deploy/README.md](deploy/README.md) for the one-time setup of production
environment variables, the dedicated SSH key, GitHub environment secrets,
Cloudflare DNS, and Nginx. Nothing is deployed until those prerequisites
are configured and the workflow is merged into `main`.

