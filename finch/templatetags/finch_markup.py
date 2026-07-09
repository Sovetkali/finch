import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

CODE_RE = re.compile(r"`([^`\n]+)`")
URL_RE = re.compile(r"(?P<url>https?://[^\s<]+)")
MENTION_RE = re.compile(r"(?<![\w@])@(?P<username>[A-Za-z0-9_]{1,150})")
BOLD_RE = re.compile(r"\*\*(?P<text>[^*\n]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?P<text>[^*\n]+)\*(?!\*)|_(?P<alt>[^_\n]+)_")
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+)$")


def _format_inline(text):
    code_values = []

    def store_code(match):
        code_values.append(f"<code>{match.group(1)}</code>")
        return f"@@CODE{len(code_values) - 1}@@"

    text = CODE_RE.sub(store_code, text)
    text = URL_RE.sub(r'<a href="\g<url>" rel="nofollow noopener noreferrer" target="_blank">\g<url></a>', text)
    text = MENTION_RE.sub(r'<a href="/profile/\g<username>/" class="text-decoration-none">@\g<username></a>', text)
    text = BOLD_RE.sub(r"<strong>\g<text></strong>", text)
    text = ITALIC_RE.sub(lambda match: f"<em>{match.group('text') or match.group('alt')}</em>", text)

    for index, value in enumerate(code_values):
        text = text.replace(f"@@CODE{index}@@", value)
    return text


@register.filter(name="finch_markup")
def finch_markup(value):
    """Render a small, safe subset of post markup."""
    if not value:
        return ""

    lines = escape(value).splitlines()
    output = []
    list_items = []

    def flush_list():
        if list_items:
            output.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for line in lines:
        if not line.strip():
            flush_list()
            continue

        list_match = LIST_ITEM_RE.match(line)
        if list_match:
            list_items.append(_format_inline(list_match.group("text")))
            continue

        flush_list()
        output.append(f"<p>{_format_inline(line)}</p>")

    flush_list()
    return mark_safe("".join(output))
