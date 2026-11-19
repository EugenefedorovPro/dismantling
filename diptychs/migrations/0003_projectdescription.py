from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("diptychs", "0002_authorbiography")]

    operations = [
        migrations.CreateModel(
            name="ProjectDescription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body_markdown", models.TextField(blank=True, help_text="Write the project's description in Markdown.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "project description",
                "verbose_name_plural": "project description",
            },
        ),
    ]
