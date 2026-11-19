from django.test import TestCase
from django.urls import reverse

from .models import AuthorBiography, Diptych, DocumentExcerpt, ProjectDescription
from .templatetags.diptych_markdown import render_markdown


class DiptychPagesTests(TestCase):
    def setUp(self):
        self.published = Diptych.objects.create(
            title="Демонтаж: Чайковский",
            slug="chaikovsky",
            poem_markdown="Первая строка\nВторая строка",
            is_published=True,
        )
        self.draft = Diptych.objects.create(
            title="Черновик", slug="draft", poem_markdown="Draft", is_published=False
        )

    def test_index_lists_only_published_diptychs(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Чайковский</span>")
        self.assertNotContains(response, "Демонтаж: Чайковский")
        self.assertNotContains(response, "Черновик")

    def test_navigation_name_strips_prefix_without_changing_title(self):
        self.assertEqual(self.published.navigation_name, "Чайковский")
        self.assertEqual(self.published.title, "Демонтаж: Чайковский")
        self.assertEqual(self.draft.navigation_name, "Черновик")

    def test_detail_page_preserves_full_title(self):
        response = self.client.get(reverse("diptych-detail", kwargs={"slug": "chaikovsky"}))
        self.assertContains(response, "Демонтаж: Чайковский")

    def test_draft_has_no_public_page(self):
        response = self.client.get(reverse("diptych-detail", kwargs={"slug": "draft"}))
        self.assertEqual(response.status_code, 404)

    def test_multiple_document_sources_are_displayed_in_order(self):
        DocumentExcerpt.objects.create(
            diptych=self.published,
            source_title="Council decision",
            source_url="https://example.org/council",
            quote_markdown="Second quotation",
            display_order=2,
        )
        DocumentExcerpt.objects.create(
            diptych=self.published,
            source_title="Student letter",
            source_url="https://example.org/letter",
            quote_markdown="First quotation",
            display_order=1,
        )
        response = self.client.get(reverse("diptych-detail", kwargs={"slug": "chaikovsky"}))
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.content.index(b"Student letter"), response.content.index(b"Council decision"))
        self.assertContains(response, "Первая строка<br")

    def test_markdown_escapes_html_and_unsafe_links(self):
        rendered = str(render_markdown('<script>alert(1)</script>\n[bad](javascript:alert(1))'))
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('href="javascript:', rendered)


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


class AuthorBiographyTests(TestCase):
    def test_footer_links_to_author_page(self):
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'href="/author/"')

    def test_author_page_shows_placeholder_until_edited_in_admin(self):
        self.assertFalse(AuthorBiography.objects.exists())
        response = self.client.get(reverse("author-bio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Биография пока не добавлена.")

    def test_author_page_renders_editable_markdown_safely(self):
        AuthorBiography.objects.create(
            body_markdown="**Поэт** и [автор](https://example.org) <script>alert(1)</script>"
        )
        response = self.client.get(reverse("author-bio"))
        self.assertContains(response, "<strong>Поэт</strong>", html=True)
        self.assertContains(response, 'href="https://example.org"')
        self.assertNotContains(response, "<script>")


class ProjectDescriptionTests(TestCase):
    def test_homepage_title_links_to_project_page(self):
        response = self.client.get(reverse("index"))
        self.assertContains(response, '<h1 class="index-title"><a href="/project/">ДЕМОНТАЖ</a></h1>', html=True)

    def test_project_page_shows_placeholder_until_edited_in_admin(self):
        self.assertFalse(ProjectDescription.objects.exists())
        response = self.client.get(reverse("project-description"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Описание проекта пока не добавлено.")

    def test_project_page_renders_editable_markdown_safely(self):
        ProjectDescription.objects.create(
            body_markdown="**Поэзия** и [проект](https://example.org) <script>alert(1)</script>"
        )
        response = self.client.get(reverse("project-description"))
        self.assertContains(response, "<strong>Поэзия</strong>", html=True)
        self.assertContains(response, 'href="https://example.org"')
        self.assertNotContains(response, "<script>")
