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

    def __str__(self):
        return self.title


class DocumentExcerpt(models.Model):
    diptych = models.ForeignKey(
        Diptych, related_name="excerpts", on_delete=models.CASCADE
    )
    source_title = models.CharField(max_length=300)
    source_url = models.URLField(max_length=1000)
    quote_markdown = models.TextField(help_text="Verbatim quotation in Markdown.")
    document_date = models.DateField(blank=True, null=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "pk"]

    def __str__(self):
        return self.source_title

