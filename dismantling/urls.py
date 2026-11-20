from django.contrib import admin
from django.urls import path

from diptychs import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("author/", views.author_bio, name="author-bio"),
    path("project/", views.project_description, name="project-description"),
    path("archive/<slug:slug>/", views.archive_detail, name="archive-detail"),
    path(
        "archive/<slug:slug>/download/<int:capture_id>/",
        views.archive_download,
        name="archive-download",
    ),
    path("diptych/<slug:slug>/", views.detail, name="diptych-detail"),
    path("<slug:slug>/", views.detail),
]

