from django.test import TestCase
from django.urls import reverse

from .models import Diptych


class IndexTests(TestCase):
    def test_index_shows_all_published_diptychs(self):
        for number in range(1, 9):
            Diptych.objects.create(
                title=f"Диптих {number}",
                slug=f"diptych-{number}",
                poem_markdown="Стихотворение",
                display_order=number,
                is_published=True,
            )

        Diptych.objects.create(
            title="Черновик",
            slug="draft",
            poem_markdown="Не опубликовано",
            is_published=False,
        )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="index-name"', count=8)
        self.assertContains(response, 'class="index-name-text"', count=8)
        self.assertNotContains(response, "Черновик")
