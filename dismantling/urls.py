from django.contrib import admin
from django.urls import path

from diptychs import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("<slug:slug>/", views.detail, name="diptych-detail"),
]

