"""Export editorial texts and back up SQLite and archived source files."""

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.db import connections, transaction
from django.utils import timezone

from .models import ArchiveCapture, AuthorBiography, Diptych, ProjectDescription


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


def backup_archive_media():
    """Return a seekable ZIP containing all archive media and a checksum manifest.

    The ZIP is written to a temporary disk file rather than buffered in RAM.
    The caller must close the returned file; Django's FileResponse does so.
    """
    root = Path(settings.MEDIA_ROOT)
    if root.exists() and not root.is_dir():
        raise ValueError("Archive media root is not a directory")

    expected = {}
    for filename, sha256, size in ArchiveCapture.objects.values_list(
        "file", "sha256", "byte_size"
    ):
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe stored archive filename")
        expected[relative.as_posix()] = (sha256, size)

    output = tempfile.TemporaryFile(mode="w+b")
    try:
        manifest_files = []
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            if root.is_dir():
                for directory, subdirectories, filenames in os.walk(root, followlinks=False):
                    folder = Path(directory)
                    if any((folder / name).is_symlink() for name in subdirectories):
                        raise ValueError("Archive media contains a symbolic link")
                    for filename in sorted(filenames):
                        path = folder / filename
                        if path.is_symlink() or not path.is_file():
                            raise ValueError("Archive media contains an unsafe file")
                        relative = path.relative_to(root).as_posix()
                        digest = hashlib.sha256()
                        size = 0
                        with path.open("rb") as original, archive.open(
                            f"archive-media/{relative}", "w", force_zip64=True
                        ) as destination:
                            while chunk := original.read(1024 * 1024):
                                digest.update(chunk)
                                destination.write(chunk)
                                size += len(chunk)
                        checksum = digest.hexdigest()
                        recorded = expected.pop(relative, None)
                        if recorded is not None and recorded != (checksum, size):
                            raise ValueError("Archived source checksum or size mismatch")
                        manifest_files.append(
                            {"path": f"archive-media/{relative}", "sha256": checksum, "bytes": size}
                        )

            if expected:
                raise FileNotFoundError("Some database-referenced archive files are missing")

            archive.writestr(
                "archive-manifest.json",
                json.dumps(
                    {
                        "format": "dismantling-archive-backup-v1",
                        "created_at": timezone.now().isoformat(),
                        "files": sorted(manifest_files, key=lambda entry: entry["path"]),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        output.seek(0)
        return output
    except Exception:
        output.close()
        raise
