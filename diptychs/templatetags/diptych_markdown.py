"""Render trusted editorial Markdown without allowing embedded HTML."""

from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt


register = template.Library()
renderer = MarkdownIt("commonmark", {"html": False, "breaks": True})


@register.filter(name="render_markdown")
def render_markdown(value):
    # markdown-it escapes raw HTML and rejects unsafe link protocols.
    return mark_safe(renderer.render(value or ""))

