from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("diptychs", "0003_projectdescription")]

    operations = [
        migrations.AddField(
            model_name="authorbiography",
            name="body_markdown_uk",
            field=models.TextField(blank=True, help_text="Optional Ukrainian translation of the biography.", verbose_name="Ukrainian (Markdown)"),
        ),
        migrations.AddField(
            model_name="authorbiography",
            name="body_markdown_en",
            field=models.TextField(blank=True, help_text="Optional English translation of the biography.", verbose_name="English (Markdown)"),
        ),
        migrations.AddField(
            model_name="projectdescription",
            name="body_markdown_uk",
            field=models.TextField(blank=True, help_text="Optional Ukrainian translation of the project description.", verbose_name="Ukrainian (Markdown)"),
        ),
        migrations.AddField(
            model_name="projectdescription",
            name="body_markdown_en",
            field=models.TextField(blank=True, help_text="Optional English translation of the project description.", verbose_name="English (Markdown)"),
        ),
    ]
