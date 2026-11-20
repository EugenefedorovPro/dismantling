import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ArchiveCapture, ArchiveSource, Diptych, DocumentExcerpt


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
ORIGINAL_URL = "https://example.org/official.pdf#page=6"


class ArchivePagesTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_context = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_context.enable()
        self.addCleanup(self.settings_context.disable)
        self.diptych = Diptych.objects.create(
            title="Демонтаж: Пример", slug="example", poem_markdown="Verse",
            is_published=True,
        )
        self.source = ArchiveSource.objects.create(
            slug="example", title="Official document", original_url=ORIGINAL_URL
        )
        self.excerpt = DocumentExcerpt.objects.create(
            diptych=self.diptych, source_title="Official document", source_url=ORIGINAL_URL,
            quote_markdown="Quotation", archive_source=self.source,
        )
        self.capture = ArchiveCapture.objects.create(
            source=self.source, kind=ArchiveCapture.Kind.ORIGINAL_PDF,
            captured_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
            file=SimpleUploadedFile("source.pdf", PDF_BYTES, content_type="application/pdf"),
        )

    def test_private_archives_do_not_leak_into_public_pages(self):
        detail = self.client.get(reverse("diptych-detail", args=[self.diptych.slug]))
        self.assertNotContains(detail, "Архивная копия")
        self.assertEqual(self.client.get(reverse("archive-detail", args=[self.source.slug])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("archive-download", args=[self.source.slug, self.capture.pk])).status_code,
            404,
        )

    def test_superuser_can_review_unpublished_archive(self):
        user = get_user_model().objects.create_superuser("owner", "owner@example.org", "password")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("archive-detail", args=[self.source.slug])), "Official document")

    def test_published_archive_has_links_download_and_checksum(self):
        self.source.is_public = True
        self.source.save(update_fields=["is_public"])
        detail = self.client.get(reverse("diptych-detail", args=[self.diptych.slug]))
        self.assertContains(detail, "Архивная копия")
        self.assertContains(detail, "Скачать документ")
        archive = self.client.get(reverse("archive-detail", args=[self.source.slug]))
        self.assertContains(archive, hashlib.sha256(PDF_BYTES).hexdigest())
        response = self.client.get(reverse("archive-download", args=[self.source.slug, self.capture.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Type"], "application/octet-stream")

    def test_archive_capture_is_immutable(self):
        self.capture.kind = ArchiveCapture.Kind.PAGE_PDF
        with self.assertRaises(ValidationError):
            self.capture.save()

    def test_rejects_incorrect_file_signature(self):
        bad = ArchiveCapture(
            source=self.source, kind=ArchiveCapture.Kind.ORIGINAL_PDF,
            captured_at=datetime.now(timezone.utc),
            file=SimpleUploadedFile("bad.pdf", b"HTML, not PDF"),
        )
        with self.assertRaises(ValidationError):
            bad.save()


class ImportArchiveBundleTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_context = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_context.enable()
        self.addCleanup(self.settings_context.disable)
        diptych = Diptych.objects.create(
            title="Test diptych", slug="example", poem_markdown="Verse", is_published=True,
        )
        self.excerpt = DocumentExcerpt.objects.create(
            diptych=diptych, source_title="Official document", source_url=ORIGINAL_URL,
            quote_markdown="Quotation",
        )

    def bundle_file(self, modified_sha=False, path="files/example-original.pdf"):
        manifest = {
            "format": "dismantling-source-archive-v1",
            "sources": [{
                "slug": "example", "diptych_slug": "example", "title": "Official document",
                "original_url": ORIGINAL_URL,
                "captures": [{
                    "filename": path, "kind": "original_pdf", "captured_at": "2026-11-20T13:00:00+00:00",
                    "sha256": "0" * 64 if modified_sha else hashlib.sha256(PDF_BYTES).hexdigest(),
                }],
            }],
        }
        bundle_path = Path(self.media.name) / "bundle.zip"
        with zipfile.ZipFile(bundle_path, "w") as out:
            out.writestr("manifest.json", json.dumps(manifest))
            out.writestr(path, PDF_BYTES)
        return bundle_path

    def test_import_matches_existing_excerpt_and_is_idempotent(self):
        bundle = self.bundle_file()
        call_command("import_archive_bundle", str(bundle), stdout=io.StringIO())
        self.excerpt.refresh_from_db()
        self.assertEqual(self.excerpt.archive_source.slug, "example")
        self.assertFalse(self.excerpt.archive_source.is_public)
        self.assertEqual(ArchiveCapture.objects.count(), 1)
        call_command("import_archive_bundle", str(bundle), stdout=io.StringIO())
        self.assertEqual(ArchiveCapture.objects.count(), 1)

    def test_dry_run_makes_no_changes(self):
        call_command("import_archive_bundle", str(self.bundle_file()), dry_run=True, stdout=io.StringIO())
        self.assertFalse(ArchiveSource.objects.exists())

    def test_mismatched_checksum_blocks_import(self):
        from django.core.management.base import CommandError
        with self.assertRaisesRegex(CommandError, "SHA-256 mismatch"):
            call_command("import_archive_bundle", str(self.bundle_file(modified_sha=True)))
        self.assertFalse(ArchiveSource.objects.exists())

    def test_rejects_unsafe_paths(self):
        from django.core.management.base import CommandError
        with self.assertRaisesRegex(CommandError, "Unsafe archive filename"):
            call_command("import_archive_bundle", str(self.bundle_file(path="../evil.pdf")))
