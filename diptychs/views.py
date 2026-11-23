from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import ArchiveCapture, ArchiveSource, AuthorBiography, Diptych, ProjectDescription


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


# Literary reading order. New diptychs follow these eight in Admin display order.
# Match names rather than database IDs so it works with independent local and
# production SQLite databases and with existing Ukrainian/Russian title variants.
READING_ORDER = (
    ("пушкин",),
    ("чуковск",),
    ("цветаев", "екстер", "ekster"),
    ("булгаков",),
    ("достоевск",),
    ("чайковск",),
    ("гогол",),
    ("толстой",),
)


def reading_order_key(diptych):
    name = diptych.navigation_name.casefold()
    for position, variants in enumerate(READING_ORDER):
        if any(variant in name for variant in variants):
            return (0, position, diptych.display_order, diptych.pk)
    # Future names are never hidden or shuffled. The Admin order still applies.
    return (1, diptych.display_order, diptych.pk)


def index(request):
    diptychs = sorted(
        Diptych.objects.filter(is_published=True),
        key=reading_order_key,
    )
    return render(request, "diptychs/index.html", {"diptychs": diptychs})


def author_bio(request):
    biography = AuthorBiography.objects.first()
    return render(request, "diptychs/author.html", translated_text(biography, request))


def project_description(request):
    description = ProjectDescription.objects.first()
    return render(request, "diptychs/project.html", translated_text(description, request))


def detail(request, slug):
    diptych = get_object_or_404(
        Diptych.objects.prefetch_related("excerpts__archive_source__captures"),
        slug=slug,
        is_published=True,
    )
    return render(request, "diptychs/detail.html", {"diptych": diptych})


def _visible_archive_or_404(request, slug):
    source = get_object_or_404(ArchiveSource, slug=slug)
    if not source.is_public and not request.user.is_superuser:
        raise Http404("Archive not published")
    return source


@require_GET
def archive_detail(request, slug):
    source = _visible_archive_or_404(request, slug)
    captures = source.captures.all()
    if not captures.exists():
        raise Http404("No archive captures")
    response = render(
        request, "diptychs/archive.html", {"source": source, "captures": captures}
    )
    response["Cache-Control"] = "private, no-store" if not source.is_public else "public, max-age=300"
    return response


@require_GET
def archive_download(request, slug, capture_id):
    source = _visible_archive_or_404(request, slug)
    capture = get_object_or_404(ArchiveCapture, pk=capture_id, source=source)
    try:
        opened = capture.file.open("rb")
    except (OSError, FileNotFoundError):
        raise Http404("Archive file unavailable") from None
    name = f"{slug}-{capture.pk}{Path(capture.file.name).suffix.lower()}"
    response = FileResponse(
        opened, as_attachment=True, filename=name, content_type="application/octet-stream"
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store" if not source.is_public else "public, max-age=300"
    return response

