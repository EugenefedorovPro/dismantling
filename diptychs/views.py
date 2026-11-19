from django.shortcuts import get_object_or_404, render

from .models import Diptych


def index(request):
    diptychs = Diptych.objects.filter(is_published=True)
    return render(request, "diptychs/index.html", {"diptychs": diptychs})


def detail(request, slug):
    diptych = get_object_or_404(
        Diptych.objects.prefetch_related("excerpts"),
        slug=slug,
        is_published=True,
    )
    return render(request, "diptychs/detail.html", {"diptych": diptych})

