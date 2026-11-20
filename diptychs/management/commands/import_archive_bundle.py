"""Import a reviewed archive ZIP and match each source to existing excerpts.

Usage: python manage.py import_archive_bundle /path/to/source-archives.zip
"""

import hashlib
import json
import zipfile
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from diptychs.models import ArchiveCapture, ArchiveSource, DocumentExcerpt


MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 50 * 1024 * 1024


class Command(BaseCommand):
    help = "Import immutable archival copies matched to the current diptych sources"

    def add_arguments(self, parser):
        parser.add_argument("bundle", help="ZIP containing manifest.json and files/")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            bundle = zipfile.ZipFile(options["bundle"])
        except (OSError, zipfile.BadZipFile) as exc:
            raise CommandError(f"Cannot read ZIP: {exc}") from exc

        with bundle:
            try:
                manifest = json.loads(bundle.read("manifest.json"))
            except (ValueError, KeyError, UnicodeDecodeError) as exc:
                raise CommandError(f"Invalid manifest.json: {exc}") from exc
            if manifest.get("format") != "dismantling-source-archive-v1":
                raise CommandError("Unsupported archive manifest format")

            validated = []
            total_bytes = 0
            used_slugs = set()
            for source in manifest.get("sources", []):
                slug = source.get("slug")
                if not slug or slug in used_slugs:
                    raise CommandError(f"Duplicate or missing source slug: {slug!r}")
                used_slugs.add(slug)
                matches = DocumentExcerpt.objects.filter(
                    diptych__slug=source.get("diptych_slug"),
                    source_url=source.get("original_url"),
                )
                if matches.count() != 1:
                    raise CommandError(f"Expected one matching excerpt for {slug}, found {matches.count()}")
                existing = ArchiveSource.objects.filter(slug=slug).first()
                if existing and existing.original_url != source["original_url"]:
                    raise CommandError(f"Existing source URL differs for {slug}")
                if not source.get("title") or not source.get("captures"):
                    raise CommandError(f"Missing title or captures for {slug}")

                captures = []
                for item in source["captures"]:
                    path = item.get("filename", "")
                    parts = PurePosixPath(path).parts
                    if len(parts) != 2 or parts[0] != "files" or not parts[1] or ".." in parts:
                        raise CommandError(f"Unsafe archive filename: {path!r}")
                    if item.get("kind") not in ArchiveCapture.Kind.values:
                        raise CommandError(f"Unsupported capture kind: {path}")
                    extension = PurePosixPath(path).suffix.lower()
                    required = {
                        "screenshot": ".png", "original_html": ".html",
                    }.get(item["kind"], ".pdf")
                    if extension != required:
                        raise CommandError(f"Unexpected file extension: {path}")
                    when = parse_datetime(item.get("captured_at", ""))
                    if when is None or when.utcoffset() is None:
                        raise CommandError(f"Capture date must have timezone: {path}")
                    try:
                        info = bundle.getinfo(path)
                    except KeyError as exc:
                        raise CommandError(f"Missing file: {path}") from exc
                    if info.file_size > MAX_SINGLE_FILE_BYTES:
                        raise CommandError(f"Oversized archive file: {path}")
                    total_bytes += info.file_size
                    if total_bytes > MAX_ARCHIVE_BYTES:
                        raise CommandError("Archive exceeds size limit")
                    content = bundle.read(path)
                    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise CommandError(f"Invalid PNG signature: {path}")
                    if extension == ".pdf" and not content.startswith(b"%PDF-"):
                        raise CommandError(f"Invalid PDF signature: {path}")
                    digest = hashlib.sha256(content).hexdigest()
                    if digest != item.get("sha256"):
                        raise CommandError(f"SHA-256 mismatch: {path}")
                    captures.append((item, content, when))
                validated.append((source, matches.get(), captures))

            if not validated:
                raise CommandError("Archive contains no sources")
            if options["dry_run"]:
                self.stdout.write(
                    f"VALID: {len(validated)} sources, "
                    f"{sum(len(x[2]) for x in validated)} files, {total_bytes} bytes"
                )
                return

            created = 0
            with transaction.atomic():
                for source_data, excerpt, captures in validated:
                    source, _ = ArchiveSource.objects.get_or_create(
                        slug=source_data["slug"],
                        defaults={
                            "title": source_data["title"],
                            "original_url": source_data["original_url"],
                        },
                    )
                    if excerpt.archive_source_id != source.pk:
                        excerpt.archive_source = source
                        excerpt.save(update_fields=["archive_source"])
                    for item, content, when in captures:
                        if ArchiveCapture.objects.filter(
                            source=source, sha256=item["sha256"]
                        ).exists():
                            continue
                        capture = ArchiveCapture(
                            source=source,
                            kind=item["kind"],
                            captured_at=when,
                        )
                        capture.file = ContentFile(content, name=PurePosixPath(item["filename"]).name)
                        capture.save()
                        created += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {len(validated)} sources, {created} new copies. "
                    "All sources remain private until published in Django admin."
                )
            )
