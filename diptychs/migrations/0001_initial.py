from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Diptych",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(help_text="Short Latin URL name, e.g. chaikovsky", unique=True)),
                ("poem_markdown", models.TextField(help_text="Write the poem in Markdown. Line breaks are preserved.")),
                ("poem_date", models.DateField(blank=True, null=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("is_published", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_order", "pk"]},
        ),
        migrations.CreateModel(
            name="DocumentExcerpt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_title", models.CharField(max_length=300)),
                ("source_url", models.URLField(max_length=1000)),
                ("quote_markdown", models.TextField(help_text="Verbatim quotation in Markdown.")),
                ("document_date", models.DateField(blank=True, null=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("diptych", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="excerpts", to="diptychs.diptych")),
            ],
            options={"ordering": ["display_order", "pk"]},
        ),
    ]

