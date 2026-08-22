"Generate one printable PDF per detailed Quitoque recipe."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import os
import re
import shutil
import time
import unicodedata
from urllib.parse import quote
import zipfile

from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import QuitoqueRecipeDetails

PDF_DIRECTORY_RELATIVE_PATH = "quitoque/recettes"
PDF_DIRECTORY_LOCAL_URL = "/local/quitoque/recettes"
PDF_ARCHIVE_RELATIVE_PATH = "quitoque/recettes_quitoque.zip"
PDF_ARCHIVE_LOCAL_URL = "/local/quitoque/recettes_quitoque.zip"




def cleanup_expired_recipe_pdfs(
    config_path: str,
    retention_days: int,
) -> tuple[int, bool]:
    """Delete generated recipe PDFs older than the configured retention.

    A retention of 0 disables automatic deletion.
    Returns (number_of_pdfs_deleted, archive_deleted).
    """
    retention_days = int(retention_days)
    if retention_days <= 0:
        return 0, False

    cutoff = time.time() - (retention_days * 86400)
    directory = Path(config_path) / "www" / PDF_DIRECTORY_RELATIVE_PATH
    archive_path = Path(config_path) / "www" / PDF_ARCHIVE_RELATIVE_PATH

    deleted = 0
    archive_deleted = False

    if directory.exists():
        for pdf_file in directory.glob("*.pdf"):
            try:
                if pdf_file.stat().st_mtime < cutoff:
                    pdf_file.unlink()
                    deleted += 1
            except FileNotFoundError:
                continue

    # The ZIP must never contain files that have already expired.
    # Remove it whenever at least one source PDF was deleted, or when the
    # archive itself is older than the configured retention.
    if archive_path.exists():
        try:
            if deleted or archive_path.stat().st_mtime < cutoff:
                archive_path.unlink()
                archive_deleted = True
        except FileNotFoundError:
            pass

    return deleted, archive_deleted



def delete_recipes_archive(config_path: str) -> bool:
    """Delete only the generated Quitoque ZIP archive.

    Individual recipe PDFs are intentionally preserved.
    Returns True when an archive was deleted.
    """
    archive_path = Path(config_path) / "www" / PDF_ARCHIVE_RELATIVE_PATH

    try:
        archive_path.unlink()
        return True
    except FileNotFoundError:
        return False



def clear_generated_recipe_files(config_path: str) -> tuple[int, bool]:
    """Immediately delete all generated Quitoque PDFs and the ZIP archive."""
    directory = Path(config_path) / "www" / PDF_DIRECTORY_RELATIVE_PATH
    archive_path = Path(config_path) / "www" / PDF_ARCHIVE_RELATIVE_PATH

    deleted = 0
    if directory.exists():
        for pdf_file in directory.glob("*.pdf"):
            try:
                pdf_file.unlink()
                deleted += 1
            except FileNotFoundError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass

    archive_deleted = False
    try:
        archive_path.unlink()
        archive_deleted = True
    except FileNotFoundError:
        pass

    return deleted, archive_deleted

def prepare_pdf_directory(config_path: str) -> Path:
    """Create a clean directory for the current Quitoque recipe PDFs."""
    directory = Path(config_path) / "www" / PDF_DIRECTORY_RELATIVE_PATH
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def recipe_pdf_filename(recipe_name: str) -> str:
    """Build a safe PDF filename while retaining the visible recipe name."""
    filename = re.sub(r'[\\\\/:*?"<>|]+', " - ", recipe_name)
    filename = re.sub(r"\s+", " ", filename).strip(" .")
    if not filename:
        filename = "Recette Quitoque"
    return f"{filename[:180]}.pdf"


def recipe_pdf_local_url(recipe_name: str) -> str:
    """Return the URL exposed by Home Assistant for a recipe PDF."""
    return f"{PDF_DIRECTORY_LOCAL_URL}/{quote(recipe_pdf_filename(recipe_name))}"



def generate_recipes_archive(config_path: str, pdf_directory: str) -> str:
    """Create a fresh ZIP archive containing only the current recipe PDFs."""
    archive_path = Path(config_path) / "www" / PDF_ARCHIVE_RELATIVE_PATH
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temp_archive = archive_path.with_name(
        f".{archive_path.name}.{time.time_ns()}.tmp"
    )

    # Always build a brand-new archive in a temporary file first.
    # This prevents an existing ZIP from being appended/reused and lets us
    # atomically replace the public file once generation is complete.
    try:
        archive_path.unlink(missing_ok=True)
    except OSError:
        # os.replace below still replaces an existing destination atomically.
        pass

    pdf_dir = Path(pdf_directory)
    try:
        with zipfile.ZipFile(
            temp_archive,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as archive:
            for pdf_file in sorted(pdf_dir.glob("*.pdf")):
                archive.write(pdf_file, arcname=pdf_file.name)

        # Atomic replacement: the old public ZIP cannot survive this step.
        os.replace(temp_archive, archive_path)
    finally:
        try:
            temp_archive.unlink(missing_ok=True)
        except OSError:
            pass

    return str(archive_path)


def generate_recipe_pdf(
    output_path: str,
    details: QuitoqueRecipeDetails,
    image_bytes: bytes | None = None,
) -> None:
    """Generate a modern recipe-card PDF while keeping all data from Quitoque."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    green = colors.HexColor("#176B3A")
    dark = colors.HexColor("#172019")
    muted = colors.HexColor("#667069")
    rule = colors.HexColor("#D8DEDA")
    pale = colors.HexColor("#F4F8F5")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RecipeTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, textColor=dark, alignment=0,
    )
    section_style = ParagraphStyle(
        "RecipeSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=green, spaceAfter=2.5 * mm,
    )
    meta_label = ParagraphStyle(
        "MetaLabel", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=10, textColor=dark,
    )
    meta_value = ParagraphStyle(
        "MetaValue", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=13, textColor=dark,
    )
    list_style = ParagraphStyle(
        "RecipeList", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.3, leading=12.5, textColor=dark, spaceAfter=1.1 * mm,
    )
    step_title = ParagraphStyle(
        "StepTitle", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11.2, leading=14, textColor=dark, spaceAfter=2 * mm,
    )
    instruction_style = ParagraphStyle(
        "Instruction", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.1, leading=12.2, textColor=dark, leftIndent=4 * mm,
        firstLineIndent=-3 * mm, spaceAfter=1.4 * mm,
    )
    source_style = ParagraphStyle(
        "Source", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7.5, leading=9, textColor=muted,
    )

    doc = SimpleDocTemplate(
        str(path), pagesize=A4, rightMargin=10 * mm, leftMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm, title=details.name,
        author="Home Assistant - Quitoque",
    )
    story = []

    # Hero: photo on the left, recipe title + duration/servings on the right.
    hero_image = ""
    if image_bytes:
        try:
            reader = ImageReader(BytesIO(image_bytes))
            width_px, height_px = reader.getSize()
            box_w, box_h = 108 * mm, 69 * mm
            scale = min(box_w / width_px, box_h / height_px)
            hero_image = Image(BytesIO(image_bytes), width=width_px * scale, height=height_px * scale)
            hero_image.hAlign = "LEFT"
        except Exception:
            hero_image = ""

    meta_cells = []
    if details.duration_minutes is not None:
        meta_cells.append([
            Paragraph("DURÉE", meta_label),
            Paragraph(f"{details.duration_minutes} min", meta_value),
        ])
    if details.servings:
        meta_cells.append([
            Paragraph("PORTIONS", meta_label),
            Paragraph(_escape(details.servings), meta_value),
        ])
    meta_table = Table(meta_cells or [[Paragraph("RECETTE", meta_label), Paragraph("Quitoque", meta_value)]],
                       colWidths=[23 * mm, 29 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
    ]))
    right = [Paragraph(_escape(details.name), title_style), Spacer(1, 4 * mm),
             HRFlowable(width=22 * mm, thickness=1.4, color=green, spaceAfter=4 * mm), meta_table]
    hero = Table([[hero_image, right]], colWidths=[112 * mm, 72 * mm], hAlign="LEFT")
    hero.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 5 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([hero, Spacer(1, 6 * mm), HRFlowable(width="100%", thickness=.6, color=rule), Spacer(1, 4 * mm)])

    def bullet_list(items: tuple[str, ...], width: float):
        rows = [[Paragraph(f"•&nbsp;&nbsp;{_escape(item)}", list_style)] for item in items]
        table = Table(rows or [[Paragraph("—", list_style)]], colWidths=[width])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), .6 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), .6 * mm),
        ]))
        return table

    # Ingredients are split over two sub-columns; equipment gets its own block.
    ingredients = tuple(i for i in details.ingredients if i.strip().casefold() not in {"ingrédient", "ingrédients"})
    kitchen_ingredients = tuple(
        i for i in details.kitchen_ingredients
        if i.strip().casefold() not in {"dans votre cuisine", "votre cuisine"}
    )
    equipment = tuple(i for i in details.equipment if i.strip().casefold() not in {"matériel", "materiel"})

    ingredient_subtitle = ParagraphStyle(
        "IngredientSubtitle", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=10.5, textColor=green, spaceBefore=1.5 * mm, spaceAfter=1 * mm,
    )

    def two_column_ingredients(items: tuple[str, ...]):
        half = (len(items) + 1) // 2
        return Table([[
            bullet_list(items[:half], 57 * mm),
            bullet_list(items[half:], 57 * mm),
        ]], colWidths=[59 * mm, 59 * mm], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

    ingredient_block = [
        Paragraph("INGRÉDIENTS", section_style),
        Paragraph("DANS VOTRE BOX", ingredient_subtitle),
        two_column_ingredients(ingredients),
    ]
    if kitchen_ingredients:
        ingredient_block.extend([
            Spacer(1, 1.5 * mm),
            Paragraph("DANS VOTRE CUISINE", ingredient_subtitle),
            two_column_ingredients(kitchen_ingredients),
        ])
    equipment_block = [Paragraph("MATÉRIEL", section_style), bullet_list(equipment, 55 * mm)]
    lists = Table([[ingredient_block, equipment_block]], colWidths=[123 * mm, 61 * mm])
    lists.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 2 * mm),
        ("RIGHTPADDING", (0, 0), (0, 0), 5 * mm),
        ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("LINEBEFORE", (1, 0), (1, 0), .5, rule),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([lists, Spacer(1, 4 * mm), HRFlowable(width="100%", thickness=.6, color=rule), Spacer(1, 3 * mm)])

    # Preparation: compact two-column cards, close to the supplied reference.
    step_cards = []
    for step in details.steps:
        number = Paragraph(
            f'<font color="#FFFFFF"><b>{step.number}</b></font>',
            ParagraphStyle("StepNumber", parent=styles["BodyText"], fontName="Helvetica-Bold",
                           fontSize=10, leading=12, alignment=TA_CENTER),
        )
        heading = Table([[number, Paragraph(_escape(step.title), step_title)]], colWidths=[9 * mm, 76 * mm])
        heading.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), green),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 3 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ]))
        content = [heading, Spacer(1, 1.5 * mm)]
        content.extend(Paragraph(f"• {_escape(line)}", instruction_style) for line in step.instructions)
        step_cards.append(content)

    for index in range(0, len(step_cards), 2):
        row = [step_cards[index], step_cards[index + 1] if index + 1 < len(step_cards) else ""]
        grid = Table([row], colWidths=[91 * mm, 91 * mm], hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 2 * mm),
            ("RIGHTPADDING", (0, 0), (0, 0), 5 * mm),
            ("LEFTPADDING", (1, 0), (1, 0), 5 * mm),
            ("RIGHTPADDING", (1, 0), (1, 0), 2 * mm),
            ("LINEBEFORE", (1, 0), (1, 0), .5, rule),
            ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        story.append(grid)
        if index + 2 < len(step_cards):
            story.extend([HRFlowable(width="100%", thickness=.45, color=rule), Spacer(1, 1 * mm)])

    story.extend([
        Spacer(1, 3 * mm),
        Table([[Paragraph(f"<b>Source :</b> {_escape(details.source_url)}", source_style)]],
              colWidths=[184 * mm], style=TableStyle([
                  ("BACKGROUND", (0, 0), (-1, -1), pale),
                  ("BOX", (0, 0), (-1, -1), .4, rule),
                  ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                  ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
              ])),
    ])
    doc.build(story)

def _escape(text: str) -> str:
    """Escape text for ReportLab Paragraph markup."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
