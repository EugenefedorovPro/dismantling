from django.shortcuts import get_object_or_404, render

from .models import AuthorBiography, Diptych, ProjectDescription


LANGUAGE_FIELDS = {
    "ru": "body_markdown",
    "uk": "body_markdown_uk",
    "en": "body_markdown_en",
}


def translated_text(record, request):
    """Select an editable Markdown field and retain Russian as a fallback."""
    language = request.GET.get("lang", "ru")
    if language not in LANGUAGE_FIELDS:
        language = "ru"

    body_markdown = getattr(record, LANGUAGE_FIELDS[language], "") if record else ""
    fallback_to_russian = bool(
        language != "ru" and not body_markdown and record and record.body_markdown
    )
    if fallback_to_russian:
        body_markdown = record.body_markdown

    return {
        "language": language,
        "body_markdown": body_markdown,
        "text_language": "ru" if fallback_to_russian else language,
        "fallback_to_russian": fallback_to_russian,
    }


def index(request):
    diptychs = Diptych.objects.filter(is_published=True)
    return render(request, "diptychs/index.html", {"diptychs": diptychs})


def author_bio(request):
    biography = AuthorBiography.objects.first()
    return render(request, "diptychs/author.html", translated_text(biography, request))


def project_description(request):
    description = ProjectDescription.objects.first()
    return render(request, "diptychs/project.html", translated_text(description, request))


def detail(request, slug):
    diptych = get_object_or_404(
        Diptych.objects.prefetch_related("excerpts"),
        slug=slug,
        is_published=True,
    )
    return render(request, "diptychs/detail.html", {"diptych": diptych})

