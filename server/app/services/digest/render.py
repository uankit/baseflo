"""Render a `DigestEmail` into text and HTML bodies.

Per docs/40-features/DIGEST.md §3.3: text version is the primary; HTML is a
light enhancement. We keep both deterministic — same email → byte-identical
rendered output, so snapshot tests are reliable.
"""

from __future__ import annotations

from html import escape

from app.services.digest.types import (
    BulletSentiment,
    DigestBullet,
    DigestEmail,
    DigestSection,
)


__all__ = ["render_html", "render_text"]


_SENTIMENT_PREFIX_TEXT: dict[BulletSentiment, str] = {
    BulletSentiment.INFO: "•",
    BulletSentiment.POSITIVE: "+",
    BulletSentiment.NEGATIVE: "!",
    BulletSentiment.NEUTRAL: "•",
}

_SENTIMENT_CLASS_HTML: dict[BulletSentiment, str] = {
    BulletSentiment.INFO: "info",
    BulletSentiment.POSITIVE: "positive",
    BulletSentiment.NEGATIVE: "negative",
    BulletSentiment.NEUTRAL: "neutral",
}


# ---------- Text ----------


def _render_bullet_text(bullet: DigestBullet) -> str:
    prefix = _SENTIMENT_PREFIX_TEXT[bullet.sentiment]
    if bullet.delta:
        return f"  {prefix} {bullet.text} ({bullet.delta})"
    return f"  {prefix} {bullet.text}"


def _render_section_text(section: DigestSection) -> str:
    lines = [section.title.upper()]
    for bullet in section.bullets:
        lines.append(_render_bullet_text(bullet))
    if section.deep_link_url:
        lines.append(f"  → {section.deep_link_url}")
    return "\n".join(lines)


def render_text(email: DigestEmail) -> str:
    """Plain-text body; one section per blank-line-separated stanza."""
    parts: list[str] = [email.subject, "=" * len(email.subject)]
    for section in email.sections:
        parts.append("")
        parts.append(_render_section_text(section))
    return "\n".join(parts) + "\n"


# ---------- HTML ----------


def _render_bullet_html(bullet: DigestBullet) -> str:
    css_class = _SENTIMENT_CLASS_HTML[bullet.sentiment]
    text = escape(bullet.text)
    if bullet.delta:
        delta = escape(bullet.delta)
        return (
            f'<li class="{css_class}">{text} '
            f'<span class="delta">({delta})</span></li>'
        )
    return f'<li class="{css_class}">{text}</li>'


def _render_section_html(section: DigestSection) -> str:
    title = escape(section.title)
    bullets = "\n".join(_render_bullet_html(b) for b in section.bullets)
    link_html = ""
    if section.deep_link_url:
        link_html = (
            f'<p><a href="{escape(section.deep_link_url)}">View in workspace</a></p>'
        )
    return (
        f'<section class="digest-section digest-{section.kind.value}">'
        f'<h2>{title}</h2>'
        f'<ul>{bullets}</ul>'
        f'{link_html}'
        f'</section>'
    )


def render_html(email: DigestEmail) -> str:
    """Minimal HTML: a header, one `<section>` per digest section.

    Inline CSS is intentionally not added here; the email layer can wrap this
    body in a templated frame with sender-specific styling. We keep this
    function pure + framework-free.
    """
    sections = "\n".join(_render_section_html(s) for s in email.sections)
    return (
        f'<!doctype html>'
        f'<html><head><meta charset="utf-8">'
        f'<title>{escape(email.subject)}</title></head>'
        f'<body>'
        f'<h1>{escape(email.subject)}</h1>'
        f'{sections}'
        f'</body></html>'
    )
