from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpResponse
from django.urls import path
from django.utils import timezone

from .exports import backup_sqlite_database, export_editorial_texts
from .models import (
    ArchiveCapture,
    ArchiveSource,
    AuthorBiography,
    Diptych,
    DocumentExcerpt,
    ProjectDescription,
)


class DocumentExcerptInline(admin.StackedInline):
    model = DocumentExcerpt
    extra = 1
    ordering = ("display_order", "pk")
    autocomplete_fields = ("archive_source",)
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 12})}
    }


@admin.register(Diptych)
class DiptychAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "poem_date", "display_order", "is_published")
    list_editable = ("display_order", "is_published")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "poem_markdown")
    inlines = [DocumentExcerptInline]
    fieldsets = [
        (None, {"fields": ("title", "slug", "poem_date", "poem_markdown")}),
        ("Publication", {"fields": ("display_order", "is_published")}),
    ]

    def get_urls(self):
        export_urls = [
            path(
                "export-texts/",
                self.admin_site.admin_view(self.export_texts),
                name="diptychs_diptych_export_texts",
            ),
            path(
                "backup-sqlite/",
                self.admin_site.admin_view(self.backup_sqlite),
                name="diptychs_diptych_backup_sqlite",
            ),
        ]
        return export_urls + super().get_urls()

    @staticmethod
    def _require_superuser(request):
        # The database includes Django user accounts and session data.
        if not request.user.is_superuser:
            raise PermissionDenied

    def export_texts(self, request):
        self._require_superuser(request)
        response = HttpResponse(
            export_editorial_texts(), content_type="text/plain; charset=utf-8"
        )
        filename = f"dismantling-texts-{timezone.localdate():%Y-%m-%d}.txt"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response

    def backup_sqlite(self, request):
        self._require_superuser(request)
        response = HttpResponse(
            backup_sqlite_database(), content_type="application/vnd.sqlite3"
        )
        filename = f"dismantling-{timezone.localdate():%Y-%m-%d}.sqlite3"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response


class SingletonMarkdownAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Russian (original)", {"fields": ("body_markdown",)}),
        ("Ukrainian", {"fields": ("body_markdown_uk",)}),
        ("English", {"fields": ("body_markdown_en",)}),
    )
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 18})}
    }

    def has_add_permission(self, request):
        # Each site-wide text page has one editable record.
        return super().has_add_permission(request) and not self.model.objects.exists()


@admin.register(AuthorBiography)
class AuthorBiographyAdmin(SingletonMarkdownAdmin):
    pass


@admin.register(ProjectDescription)
class ProjectDescriptionAdmin(SingletonMarkdownAdmin):
    pass


class ArchiveCaptureInline(admin.TabularInline):
    model = ArchiveCapture
    extra = 0
    can_delete = False
    fields = ("kind", "captured_at", "sha256", "byte_size")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ArchiveSource)
class ArchiveSourceAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_public", "capture_count")
    list_filter = ("is_public",)
    search_fields = ("title", "slug", "original_url")
    fields = ("slug", "title", "original_url", "is_public")
    inlines = [ArchiveCaptureInline]

    def capture_count(self, obj):
        return obj.captures.count()

    capture_count.short_description = "Copies"

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ArchiveCapture)
class ArchiveCaptureAdmin(admin.ModelAdmin):
    list_display = ("source", "kind", "captured_at", "byte_size", "sha256")
    list_filter = ("kind", "captured_at")
    autocomplete_fields = ("source",)
    fields = ("source", "kind", "captured_at", "file")

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

