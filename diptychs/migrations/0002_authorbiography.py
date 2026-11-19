from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("diptychs", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="AuthorBiography",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body_markdown", models.TextField(blank=True, help_text="Write the author's biography in Markdown.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "author biography",
                "verbose_name_plural": "author biography",
            },
        ),
    ]
