from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from nxjob.schemas.core import TailoredResumeContent


def render_resume_docx(content: TailoredResumeContent, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)

    styles = document.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(9.5)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run(content.candidate_name)
    title_run.bold = True
    title_run.font.size = Pt(15)

    headline = document.add_paragraph()
    headline.alignment = WD_ALIGN_PARAGRAPH.CENTER
    headline_run = headline.add_run(content.headline)
    headline_run.font.size = Pt(9)

    _add_section(document, "SUMMARY", content.summary)
    if content.skills:
        skills = document.add_paragraph()
        _add_section_heading(skills, "SKILLS")
        skills.add_run(", ".join(content.skills))
    _add_section(document, "SELECTED EXPERIENCE", content.experience_bullets)

    document.save(output_path)
    return output_path


def _add_section(document: Document, heading: str, bullets: list[str]) -> None:
    if not bullets:
        return
    paragraph = document.add_paragraph()
    _add_section_heading(paragraph, heading)
    for bullet in bullets:
        item = document.add_paragraph(style=None)
        item.paragraph_format.left_indent = Inches(0.18)
        item.paragraph_format.first_line_indent = Inches(-0.12)
        item.paragraph_format.space_after = Pt(1.5)
        item.add_run("- ")
        item.add_run(bullet)


def _add_section_heading(paragraph, heading: str) -> None:
    run = paragraph.add_run(f"{heading}\n")
    run.bold = True
    run.font.size = Pt(9)
