"""Tests for the superuser-only editorial and database downloads."""

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import AuthorBiography, Diptych, DocumentExcerpt, ProjectDescription


class TextExportTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="editor", password="test-password"
        )
        self.client.force_login(self.superuser)

    def test_text_export_includes_all_editorial_fields_and_drafts(self):
        diptych = Diptych.objects.create(
            title="Демонтаж: Гоголь",
            slug="gogol",
            poem_markdown="спичка читает пальцы\n**дымиться**",
            display_order=7,
            is_published=False,
        )
        DocumentExcerpt.objects.create(
            diptych=diptych,
            source_title="Протокол КМДА",
            source_url="https://example.org/protocol",
            quote_markdown="Видатний письменник\nукраїнського походження",
            display_order=1,
        )
        AuthorBiography.objects.create(
            body_markdown="Русская биография",
            body_markdown_uk="Українська біографія",
            body_markdown_en="English biography",
        )
        ProjectDescription.objects.create(
            body_markdown="Проект",
            body_markdown_uk="Проєкт",
            body_markdown_en="Project",
        )

        response = self.client.get(reverse("admin:diptychs_diptych_export_texts"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].endswith('.txt"'))
        self.assertIn("no-store", response["Cache-Control"])
        text = response.content.decode("utf-8")
        for expected in (
            "Демонтаж: Гоголь",
            "Slug: gogol",
            "Published: no",
            "спичка читает пальцы\n**дымиться**",
            "Протокол КМДА",
            "https://example.org/protocol",
            "Видатний письменник\nукраїнського походження",
            "Русская биография",
            "Українська біографія",
            "English biography",
            "Проект",
            "Проєкт",
            "Project",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_admin_list_has_one_click_export_links(self):
        response = self.client.get(reverse("admin:diptychs_diptych_changelist"))
        self.assertContains(response, "Export all texts (.txt)")
        self.assertContains(response, "Backup database (.sqlite3)")

    def test_staff_without_superuser_access_cannot_download(self):
        staff = get_user_model().objects.create_user(
            username="staff", password="test-password", is_staff=True
        )
        self.client.force_login(staff)
        for name in (
            "admin:diptychs_diptych_export_texts",
            "admin:diptychs_diptych_backup_sqlite",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_anonymous_cannot_download(self):
        self.client.logout()
        for name in (
            "admin:diptychs_diptych_export_texts",
            "admin:diptychs_diptych_backup_sqlite",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)


class SqliteBackupTests(TransactionTestCase):
    def test_downloaded_database_is_complete_and_valid(self):
        superuser = get_user_model().objects.create_superuser(
            username="editor", password="test-password"
        )
        Diptych.objects.create(
            title="Демонтаж: Гоголь",
            slug="gogol",
            poem_markdown="текст стихотворения",
            is_published=True,
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse("admin:diptychs_diptych_backup_sqlite"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].endswith('.sqlite3"'))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response.content[:16], b"SQLite format 3\x00")

        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "download.sqlite3"
            backup_path.write_bytes(response.content)
            with closing(sqlite3.connect(backup_path)) as backup:
                self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                poem = backup.execute(
                    "SELECT poem_markdown FROM diptychs_diptych WHERE slug = 'gogol'"
                ).fetchone()
                self.assertEqual(poem, ("текст стихотворения",))
                count = backup.execute("SELECT COUNT(*) FROM auth_user").fetchone()[0]
                self.assertEqual(count, 1)
