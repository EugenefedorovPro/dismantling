"""Export the site's editorial text and make a consistent SQLite backup."""

import sqlite3
import tempfile
from contextlib import closing
from io import StringIO
from pathlib import Path

from django.db import connections, transaction

from .models import AuthorBiography, Diptych, ProjectDescription


def _write_text(output, label, value):
    """Write Markdown verbatim, separating it clearly from the next field."""
    output.write(f"{label}:\n")
    output.write(value)
    if not value.endswith("\n"):
        output.write("\n")
    output.write("\n")


@transaction.atomic
def export_editorial_texts():
    """Return all editorial content as TXT from one database snapshot."""
    output = StringIO()
    output.write("ДЕМОНТАЖ - EDITORIAL TEXT EXPORT\n\n")

    output.write("=== DIPTYCHS ===\n\n")
    for diptych in Diptych.objects.prefetch_related("excerpts"):
        output.write(f"--- {diptych.title} ---\n")
        output.write(f"Slug: {diptych.slug}\n")
        output.write(f"Poem date: {diptych.poem_date or ''}\n")
        output.write(f"Display order: {diptych.display_order}\n")
        output.write(f"Published: {'yes' if diptych.is_published else 'no'}\n\n")
        _write_text(output, "Poem (Markdown)", diptych.poem_markdown)

        for excerpt in diptych.excerpts.all():
            output.write(f"Document: {excerpt.source_title}\n")
            output.write(f"Source URL: {excerpt.source_url}\n")
            output.write(f"Document language: {excerpt.language}\n")
            output.write(f"Document date: {excerpt.document_date or ''}\n")
            output.write(f"Display order: {excerpt.display_order}\n\n")
            _write_text(output, "Quotation (Markdown)", excerpt.quote_markdown)
        output.write("\n")

    for heading, model in (
        ("AUTHOR BIOGRAPHIES", AuthorBiography),
        ("PROJECT DESCRIPTIONS", ProjectDescription),
    ):
        output.write(f"=== {heading} ===\n\n")
        for record in model.objects.order_by("pk"):
            output.write(f"Record #{record.pk}\n\n")
            _write_text(output, "Russian (Markdown)", record.body_markdown)
            _write_text(output, "Ukrainian (Markdown)", record.body_markdown_uk)
            _write_text(output, "English (Markdown)", record.body_markdown_en)

    return output.getvalue()


def backup_sqlite_database():
    """Return a consistent snapshot, even when the live database uses WAL."""
    database = connections["default"]
    if database.vendor != "sqlite":
        raise ValueError("The database backup is only supported for SQLite.")

    database.ensure_connection()
    with tempfile.TemporaryDirectory(prefix="dismantling-backup-") as temp_dir:
        backup_path = Path(temp_dir) / "backup.sqlite3"
        with closing(sqlite3.connect(backup_path)) as destination:
            database.connection.backup(destination)
        return backup_path.read_bytes()
