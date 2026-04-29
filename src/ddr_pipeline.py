import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import fitz


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class ExtractedImage:
    page: int
    path: str
    width: int
    height: int


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_text(pdf_path: Path) -> list[PageText]:
    document = fitz.open(pdf_path)
    pages: list[PageText] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        pages.append(PageText(page=page_index + 1, text=clean_text(page.get_text("text"))))
    document.close()
    return pages


def extract_images(
    pdf_path: Path,
    output_dir: Path,
    min_width: int = 240,
    min_height: int = 160,
    max_images_per_page: int = 6,
    max_total_images: int = 120,
) -> list[ExtractedImage]:
    document = fitz.open(pdf_path)
    image_dir = ensure_dir(output_dir / pdf_path.stem.replace(" ", "_"))
    images: list[ExtractedImage] = []
    seen_hashes: set[str] = set()

    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        page_candidates = []
        for image_index, image_info in enumerate(page.get_images(full=True), start=1):
            xref = image_info[0]
            pixmap = fitz.Pixmap(document, xref)

            if pixmap.width < min_width or pixmap.height < min_height:
                pixmap = None
                continue

            if pixmap.n >= 5:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

            digest = hashlib.sha256(pixmap.samples).hexdigest()
            if digest in seen_hashes:
                pixmap = None
                continue

            page_candidates.append((pixmap.width * pixmap.height, image_index, digest, pixmap))

        page_candidates.sort(reverse=True, key=lambda item: item[0])
        for _, image_index, digest, pixmap in page_candidates[:max_images_per_page]:
            image_path = image_dir / f"page_{page_index + 1:02d}_image_{image_index:02d}.png"
            pixmap.save(image_path)
            seen_hashes.add(digest)
            images.append(
                ExtractedImage(
                    page=page_index + 1,
                    path=str(image_path),
                    width=pixmap.width,
                    height=pixmap.height,
                )
            )
            pixmap = None
            if len(images) >= max_total_images:
                document.close()
                return images

    document.close()
    return images


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def compact_pages(pages: Iterable[PageText], max_chars_per_page: int = 2400) -> str:
    chunks = []
    for page in pages:
        text = page.text[:max_chars_per_page]
        chunks.append(f"## Page {page.page}\n{text if text else 'Not Available'}")
    return "\n\n".join(chunks)


def image_manifest(images: Iterable[ExtractedImage]) -> str:
    rows = []
    for image in images:
        rows.append(f"- Page {image.page}: `{image.path}` ({image.width}x{image.height})")
    return "\n".join(rows) if rows else "Image Not Available"


def build_prompt(
    inspection_pages: list[PageText],
    thermal_pages: list[PageText],
    inspection_images: list[ExtractedImage],
    thermal_images: list[ExtractedImage],
) -> str:
    return f"""You are generating a client-ready Detailed Diagnostic Report (DDR).

Rules:
- Use only the source evidence below.
- Do not invent facts.
- If information is missing, write "Not Available".
- If information conflicts, explicitly mention the conflict.
- Use simple client-friendly language.
- Avoid duplicate points.
- Place relevant images under the matching observation when possible.

Required DDR structure:
1. Property Issue Summary
2. Area-wise Observations
3. Probable Root Cause
4. Severity Assessment (with reasoning)
5. Recommended Actions
6. Additional Notes
7. Missing or Unclear Information

# Inspection Report Text
{compact_pages(inspection_pages)}

# Thermal Report Text
{compact_pages(thermal_pages)}

# Inspection Report Images
{image_manifest(inspection_images)}

# Thermal Report Images
{image_manifest(thermal_images)}

Return the final report in Markdown. Include source page references in parentheses where useful.
"""


def call_openai(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return response.output_text


def fallback_report(
    inspection_pages: list[PageText],
    thermal_pages: list[PageText],
    inspection_images: list[ExtractedImage],
    thermal_images: list[ExtractedImage],
) -> str:
    inspection_preview = compact_pages(inspection_pages, max_chars_per_page=900)
    thermal_preview = compact_pages(thermal_pages, max_chars_per_page=900)
    return f"""# Detailed Diagnostic Report

This is a draft shell generated without an LLM API key. Review `llm_prompt.md` or set `OPENAI_API_KEY` to generate the final client-ready version.

## 1. Property Issue Summary

Not Available

## 2. Area-wise Observations

### Inspection Report Evidence

{inspection_preview}

### Thermal Report Evidence

{thermal_preview}

## 3. Probable Root Cause

Not Available

## 4. Severity Assessment

Not Available

## 5. Recommended Actions

Not Available

## 6. Additional Notes

Extracted inspection images:

{image_manifest(inspection_images)}

Extracted thermal images:

{image_manifest(thermal_images)}

## 7. Missing or Unclear Information

Not Available
"""


def run(
    inspection_pdf: Path,
    thermal_pdf: Path,
    output_dir: Path,
    max_images_per_page: int,
    max_total_images: int,
) -> None:
    ensure_dir(output_dir)
    extracted_dir = ensure_dir(output_dir / "extracted")
    image_dir = ensure_dir(output_dir / "images")

    inspection_pages = extract_text(inspection_pdf)
    thermal_pages = extract_text(thermal_pdf)
    inspection_images = extract_images(
        inspection_pdf,
        image_dir,
        max_images_per_page=max_images_per_page,
        max_total_images=max_total_images,
    )
    thermal_images = extract_images(
        thermal_pdf,
        image_dir,
        max_images_per_page=max_images_per_page,
        max_total_images=max_total_images,
    )

    write_json(extracted_dir / "inspection_text.json", [asdict(page) for page in inspection_pages])
    write_json(extracted_dir / "thermal_text.json", [asdict(page) for page in thermal_pages])
    write_json(extracted_dir / "inspection_images.json", [asdict(image) for image in inspection_images])
    write_json(extracted_dir / "thermal_images.json", [asdict(image) for image in thermal_images])

    prompt = build_prompt(inspection_pages, thermal_pages, inspection_images, thermal_images)
    (output_dir / "llm_prompt.md").write_text(prompt, encoding="utf-8")

    generated_report = call_openai(prompt)
    report = generated_report or fallback_report(
        inspection_pages,
        thermal_pages,
        inspection_images,
        thermal_images,
    )
    (output_dir / "DDR_Report.md").write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a DDR report from inspection and thermal PDFs.")
    parser.add_argument("--inspection", required=True, type=Path, help="Path to the inspection report PDF.")
    parser.add_argument("--thermal", required=True, type=Path, help="Path to the thermal report PDF.")
    parser.add_argument("--out", default=Path("outputs"), type=Path, help="Output directory.")
    parser.add_argument("--max-images-per-page", default=6, type=int, help="Largest embedded images to keep per page.")
    parser.add_argument("--max-total-images", default=120, type=int, help="Maximum images to keep per document.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        args.inspection,
        args.thermal,
        args.out,
        max_images_per_page=args.max_images_per_page,
        max_total_images=args.max_total_images,
    )
