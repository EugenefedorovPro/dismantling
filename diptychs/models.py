import hashlib
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models


class Diptych(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Short Latin URL name, e.g. chaikovsky")
    poem_markdown = models.TextField(help_text="Write the poem in Markdown. Line breaks are preserved.")
    poem_date = models.DateField(blank=True, null=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "pk"]

    @property
    def navigation_name(self):
        """Show only the author's name on the title page."""
        title = self.title.strip()
        prefix = "Демонтаж:"
        if title.casefold().startswith(prefix.casefold()):
            return title[len(prefix):].strip()
        return title

    def __str__(self):
        return self.title


class DocumentExcerpt(models.Model):
    class Language(models.TextChoices):
        UKRAINIAN = "uk", "Ukrainian"
        RUSSIAN = "ru", "Russian"
        ENGLISH = "en", "English"
        UNSPECIFIED = "und", "Unspecified"

    diptych = models.ForeignKey(
        Diptych, related_name="excerpts", on_delete=models.CASCADE
    )
    source_title = models.CharField(max_length=300)
    source_url = models.URLField(max_length=1000)
    archive_source = models.ForeignKey(
        "ArchiveSource",
        related_name="excerpts",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Optional preserved source. The original source URL remains unchanged.",
    )
    quote_markdown = models.TextField(help_text="Verbatim quotation in Markdown.")
    language = models.CharField(max_length=3, choices=Language, default=Language.UKRAINIAN)
    document_date = models.DateField(blank=True, null=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "pk"]

    def __str__(self):
        return self.source_title


class ArchiveSource(models.Model):
    """A cited source, independent of any one diptych or captured version."""

    slug = models.SlugField(unique=True, max_length=120)
    title = models.CharField(max_length=300)
    original_url = models.URLField(max_length=1000)
    is_public = models.BooleanField(
        default=False,
        help_text="Publish only after reviewing copyright and source fidelity.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return self.title


def archive_file_path(instance, filename):
    # The filename is generated, not trusted input from an uploaded attachment.
    extension = Path(filename).suffix.lower()
    return f"source-archive/{instance.source.slug}/{uuid.uuid4().hex}{extension}"


class ArchiveCapture(models.Model):
    class Kind(models.TextChoices):
        ORIGINAL_PDF = "original_pdf", "Original PDF"
        ORIGINAL_HTML = "original_html", "Original HTML snapshot"
        PAGE_PDF = "page_pdf", "Webpage PDF"
        SCREENSHOT = "screenshot", "Webpage screenshot"

    source = models.ForeignKey(
        ArchiveSource, related_name="captures", on_delete=models.PROTECT
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    captured_at = models.DateTimeField()
    file = models.FileField(upload_to=archive_file_path, max_length=300)
    sha256 = models.CharField(max_length=64, editable=False)
    byte_size = models.PositiveBigIntegerField(editable=False)

    class Meta:
        ordering = ["captured_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "sha256"], name="archive_unique_source_file"
            )
        ]

    def __str__(self):
        return f"{self.source}: {self.get_kind_display()} ({self.captured_at:%Y-%m-%d})"

    def clean(self):
        super().clean()
        if not self.file:
            raise ValidationError({"file": "A preserved file is required."})
        extension = Path(self.file.name).suffix.lower()
        expected = {
            self.Kind.SCREENSHOT: ".png",
            self.Kind.ORIGINAL_HTML: ".html",
        }.get(self.kind, ".pdf")
        if extension != expected:
            raise ValidationError({"file": f"Expected a {expected} file."})
        if self.file.size > 50 * 1024 * 1024:
            raise ValidationError({"file": "Individual archive files must be under 50 MiB."})
        self.file.open("rb")
        magic = self.file.read(8)
        self.file.seek(0)
        if expected == ".png":
            valid = magic.startswith(b"\x89PNG\r\n\x1a\n")
        elif expected == ".pdf":
            valid = magic.startswith(b"%PDF-")
        else:
            valid = True  # HTML can begin with various encodings or leading whitespace.
        if not valid:
            raise ValidationError({"file": "The file contents do not match its format."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Archive captures are immutable. Create a new capture.")
        digest = hashlib.sha256()
        size = 0
        for chunk in self.file.chunks():
            digest.update(chunk)
            size += len(chunk)
        self.sha256 = digest.hexdigest()
        self.byte_size = size
        self.file.seek(0)
        self.full_clean()
        super().save(*args, **kwargs)


class AuthorBiography(models.Model):
    body_markdown = models.TextField(
        blank=True,
        help_text="Write the author's biography in Markdown.",
    )
    body_markdown_uk = models.TextField(
        "Ukrainian (Markdown)", blank=True,
        help_text="Optional Ukrainian translation of the biography.",
    )
    body_markdown_en = models.TextField(
        "English (Markdown)", blank=True,
        help_text="Optional English translation of the biography.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "author biography"
        verbose_name_plural = "author biography"

    def __str__(self):
        return "Евгений Проскуликов"


class ProjectDescription(models.Model):
    body_markdown = models.TextField(
        blank=True,
        help_text="Write the project's description in Markdown.",
    )
    body_markdown_uk = models.TextField(
        "Ukrainian (Markdown)", blank=True,
        help_text="Optional Ukrainian translation of the project description.",
    )
    body_markdown_en = models.TextField(
        "English (Markdown)", blank=True,
        help_text="Optional English translation of the project description.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "project description"
        verbose_name_plural = "project description"

    def __str__(self):
        return "ДЕМОНТАЖ"

