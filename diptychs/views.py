from django.shortcuts import get_object_or_404, render

from .models import AuthorBiography, Diptych, ProjectDescription


def index(request):
    diptychs = Diptych.objects.filter(is_published=True)
    return render(request, "diptychs/index.html", {"diptychs": diptychs})


def author_bio(request):
    biography = AuthorBiography.objects.first()
    return render(request, "diptychs/author.html", {"biography": biography})


def project_description(request):
    description = ProjectDescription.objects.first()
    return render(request, "diptychs/project.html", {"description": description})


def detail(request, slug):
    diptych = get_object_or_404(
        Diptych.objects.prefetch_related("excerpts"),
        slug=slug,
        is_published=True,
    )
    return render(request, "diptychs/detail.html", {"diptych": diptych})

