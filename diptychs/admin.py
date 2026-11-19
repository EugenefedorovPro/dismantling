from django import forms
from django.contrib import admin
from django.db import models

from .models import Diptych, DocumentExcerpt


class DocumentExcerptInline(admin.StackedInline):
    model = DocumentExcerpt
    extra = 1
    ordering = ("display_order", "pk")
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

