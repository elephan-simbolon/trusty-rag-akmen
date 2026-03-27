import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


@dataclass
class Section:
    title: str
    level: int  # 1=Part/Chapter, 2=Section, 3=Subsection, 4=Sub-subsection
    content: str
    breadcrumb: list[str] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)


def split_by_headings(markdown_text: str, book_title: str = "", chapter: str = "") -> list[Section]:
    """
    Split Markdown text by heading hierarchy (# through ####).
    Each section gets a breadcrumb list showing its position in the hierarchy.
    Example breadcrumb: ["Part II", "Chapter 5", "Break-Even Analysis", "Formula BEP"]
    """
    lines = markdown_text.split("\n")
    sections: list[Section] = []
    current_section: Section | None = None
    heading_stack: list[tuple[int, str]] = []  # (level, title)

    if book_title:
        heading_stack.append((0, book_title))
    if chapter:
        heading_stack.append((0, chapter))

    content_lines: list[str] = []

    for line in lines:
        match = HEADING_PATTERN.match(line)
        if match:
            # Save previous section
            if current_section is not None:
                current_section.content = "\n".join(content_lines).strip()
                sections.append(current_section)
            elif content_lines:
                # Content before first heading
                sections.append(Section(
                    title="(preamble)",
                    level=0,
                    content="\n".join(content_lines).strip(),
                    breadcrumb=[h[1] for h in heading_stack],
                ))

            level = len(match.group(1))
            title = match.group(2).strip()

            # Update heading stack
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

            breadcrumb = [h[1] for h in heading_stack]

            current_section = Section(
                title=title,
                level=level,
                content="",
                breadcrumb=breadcrumb,
            )
            content_lines = []
        else:
            content_lines.append(line)

    # Save last section
    if current_section is not None:
        current_section.content = "\n".join(content_lines).strip()
        sections.append(current_section)
    elif content_lines:
        sections.append(Section(
            title="(preamble)",
            level=0,
            content="\n".join(content_lines).strip(),
            breadcrumb=[h[1] for h in heading_stack],
        ))

    logger.info(f"Split into {len(sections)} sections by heading hierarchy")
    return sections
