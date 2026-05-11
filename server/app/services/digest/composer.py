"""DigestComposer — assembles a typed `DigestEmail` from a `DigestInput`.

Per docs/40-features/DIGEST.md §3 + §4 (Builder pattern). Pure: same input
yields the same email. The runner (M1.6 second half) does the impure data
fetching, then hands the composer a clean fact-bundle.

Trimming rule per §3.3: "Hard cap: 12 bullets total. Trim least-significant
first." We assemble all section candidates first, then peel bullets off the
*tail* of the lowest-priority section that still has content. Section order
itself is fixed: AT_A_GLANCE → WORTH_A_LOOK → WHAT_IS_SELLING → RECENT_REFINEMENTS.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.observability.logging import get_logger
from app.services.digest.headline import build_subject_line
from app.services.digest.sections import (
    build_at_a_glance,
    build_recent_refinements,
    build_what_is_selling,
    build_worth_a_look,
)
from app.services.digest.types import (
    DigestEmail,
    DigestInput,
    DigestSection,
    SectionKind,
)


__all__ = ["DigestComposer", "MAX_BULLETS"]


MAX_BULLETS = 12


# Lowest priority first — we trim from the tail of these in order. The
# WORTH_A_LOOK section is intentionally protected: never trimmed, since its
# whole purpose is "things you should know".
_TRIM_ORDER: tuple[SectionKind, ...] = (
    SectionKind.RECENT_REFINEMENTS,
    SectionKind.WHAT_IS_SELLING,
    SectionKind.AT_A_GLANCE,
)


logger = get_logger("services.digest.composer")


class DigestComposer:
    """Use-case object. The instance is stateless; methods are pure."""

    def compose(
        self,
        input_: DigestInput,
        *,
        composed_at: datetime | None = None,
    ) -> DigestEmail:
        """Build a `DigestEmail` from `input_`.

        `composed_at` is injectable so tests can pin determinism; defaults
        to `datetime.now(UTC)`.
        """
        sections: list[DigestSection] = []
        for builder in (
            build_at_a_glance,
            build_worth_a_look,
            build_what_is_selling,
            build_recent_refinements,
        ):
            section = builder(input_)
            if section is not None:
                sections.append(section)

        sections = _enforce_bullet_cap(sections, cap=MAX_BULLETS)

        return DigestEmail(
            subject=build_subject_line(input_),
            sections=sections,
            project_id=input_.project_id,
            user_id=input_.user_id,
            period=input_.period,
            composed_at=composed_at or datetime.now(UTC),
        )


# ---------- Internal: bullet trimming ----------


def _enforce_bullet_cap(
    sections: list[DigestSection], *, cap: int
) -> list[DigestSection]:
    """Trim from the tail of low-priority sections until total bullets ≤ cap."""
    total = sum(len(s.bullets) for s in sections)
    if total <= cap:
        return sections

    by_kind: dict[SectionKind, DigestSection] = {s.kind: s for s in sections}

    overflow = total - cap
    for kind in _TRIM_ORDER:
        if overflow <= 0:
            break
        section = by_kind.get(kind)
        if section is None or not section.bullets:
            continue
        new_bullets = list(section.bullets)
        while overflow > 0 and new_bullets:
            new_bullets.pop()
            overflow -= 1
        by_kind[kind] = section.model_copy(update={"bullets": new_bullets})

    if overflow > 0:
        logger.warning(
            "digest_bullet_cap_unreachable",
            cap=cap, remaining_overflow=overflow,
        )

    # Preserve original section order; drop sections trimmed to zero bullets
    # only if they were *not* the always-on WORTH_A_LOOK section.
    out: list[DigestSection] = []
    for s in sections:
        new_section = by_kind[s.kind]
        if not new_section.bullets and s.kind != SectionKind.WORTH_A_LOOK:
            continue
        out.append(new_section)
    return out
