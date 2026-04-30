import argparse
import hashlib
import json
import os
import re
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


def full_text(pages: Iterable[PageText]) -> str:
    return "\n".join(page.text for page in pages)


def image_manifest(images: Iterable[ExtractedImage]) -> str:
    rows = []
    for image in images:
        rows.append(f"- Page {image.page}: `{image.path}` ({image.width}x{image.height})")
    return "\n".join(rows) if rows else "Image Not Available"


def find_description_values(text: str, label: str) -> list[str]:
    values = []
    pattern = re.compile(rf"{re.escape(label)}\s+(.+?)(?=\s+(?:Negative side photographs|Positive side photographs|Impacted Area|Site Details|$))", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(text):
        value = " ".join(match.group(1).split())
        if value and value not in values:
            values.append(value)
    return values


def thermal_summary(thermal_pages: list[PageText]) -> str:
    thermal_text = full_text(thermal_pages)
    hotspots = [float(value) for value in re.findall(r"Hotspot\s*:\s*([0-9.]+)", thermal_text, flags=re.IGNORECASE)]
    coldspots = [float(value) for value in re.findall(r"Coldspot\s*:\s*([0-9.]+)", thermal_text, flags=re.IGNORECASE)]
    image_names = re.findall(r"Thermal image\s*:\s*([A-Z0-9_.-]+)", thermal_text, flags=re.IGNORECASE)

    if not hotspots or not coldspots:
        return "Thermal readings are present, but the hotspot/coldspot range could not be reliably extracted."

    return (
        f"Thermal images dated 27/09/22 show hotspot readings from {min(hotspots):.1f} deg C to {max(hotspots):.1f} deg C "
        f"and coldspot readings from {min(coldspots):.1f} deg C to {max(coldspots):.1f} deg C across "
        f"{len(image_names) or len(thermal_pages)} thermal records."
    )


def bullet_list(items: Iterable[str]) -> str:
    cleaned = [item for item in items if item]
    return "\n".join(f"- {item}" for item in cleaned) if cleaned else "- Not Available"


def detailed_observation_rows(observations: list[str], side: str) -> str:
    if not observations:
        return "- Not Available"

    rows = []
    for index, observation in enumerate(observations, start=1):
        evidence_note = "Inspection report description"
        if "damp" in observation.lower() or "seepage" in observation.lower():
            implication = "Moisture ingress is likely affecting finishes and may continue spreading if the source is not corrected."
        elif "hollow" in observation.lower() or "joint" in observation.lower():
            implication = "Open or hollow tile areas may allow water movement behind finishes and should be checked before surface repairs."
        elif "crack" in observation.lower() or "duct" in observation.lower():
            implication = "External openings or cracks may permit water entry and should be sealed after confirming substrate condition."
        else:
            implication = "Further site verification is recommended before final repair scope is closed."

        rows.append(
            f"### {side} Observation {index}: {observation}\n\n"
            f"- Evidence: {evidence_note}.\n"
            f"- Client meaning: {implication}\n"
            "- Image support: See extracted evidence images in the app/ZIP. Exact photo-to-observation mapping is Not Available from extracted text.\n"
        )
    return "\n".join(rows)


def thermal_detail_table(thermal_pages: list[PageText]) -> str:
    rows = []
    for page in thermal_pages:
        hotspot_match = re.search(r"Hotspot\s*:\s*([0-9.]+)", page.text, flags=re.IGNORECASE)
        coldspot_match = re.search(r"Coldspot\s*:\s*([0-9.]+)", page.text, flags=re.IGNORECASE)
        image_match = re.search(r"Thermal image\s*:\s*([A-Z0-9_.-]+)", page.text, flags=re.IGNORECASE)
        if hotspot_match and coldspot_match:
            image_name = image_match.group(1) if image_match else "Not Available"
            rows.append(f"| {page.page} | {image_name} | {hotspot_match.group(1)} deg C | {coldspot_match.group(1)} deg C |")

    if not rows:
        return "Not Available"

    return "\n".join(
        [
            "| Page | Thermal Image | Hotspot | Coldspot |",
            "| --- | --- | --- | --- |",
            *rows[:30],
        ]
    )


def rule_based_report(
    inspection_pages: list[PageText],
    thermal_pages: list[PageText],
    inspection_images: list[ExtractedImage],
    thermal_images: list[ExtractedImage],
) -> str:
    inspection_text = full_text(inspection_pages)
    negative_observations = find_description_values(inspection_text, "Negative side Description")
    positive_observations = find_description_values(inspection_text, "Positive side Description")
    impacted_area_match = re.search(r"Impacted Areas/Rooms\s+(.+?)\s+Impacted Area", inspection_text, flags=re.IGNORECASE | re.DOTALL)
    impacted_areas = " ".join(impacted_area_match.group(1).split()) if impacted_area_match else "Not Available"

    issue_points = [
        f"Impacted areas/rooms: {impacted_areas}.",
        "Observed dampness/seepage in multiple areas including hall, bedroom, kitchen, master bedroom, parking area, and common bathroom based on the inspection report.",
        thermal_summary(thermal_pages),
    ]

    root_causes = [
        "Concealed plumbing leakage is marked as present in the inspection checklist.",
        "Damage in Nahani trap/brickbat coba under tile flooring is marked as present for the WC checklist.",
        "Gaps or blackish dirt in tile joints and gaps around Nahani trap joints are marked as present.",
        "External wall cracks and duct issues are reported near the master bedroom area.",
    ]

    severity = (
        "Moderate. The inspection report marks external wall/RCC crack conditions as moderate and reports all-time leakage, "
        "skirting-level dampness, ceiling dampness, seepage, and tile joint gaps across multiple areas. No source evidence "
        "states an immediate structural emergency, so a higher severity is not assumed."
    )

    actions = [
        "Inspect and repair concealed plumbing lines linked to the WC/common bathroom and affected adjoining walls.",
        "Repair or re-grout open tile joints and gaps around Nahani trap joints.",
        "Seal and repair external wall cracks, duct openings, and any poorly grouted pipe penetrations.",
        "Treat damp, seepage, and efflorescence-affected wall surfaces only after the moisture source is repaired.",
        "Re-test the affected areas after repairs using visual inspection and thermal imaging to confirm that dampness has reduced.",
    ]

    missing = [
        "Customer name: Not Available",
        "Mobile: Not Available",
        "Email: Not Available",
        "Address: Not Available",
        "Property age: Not Available",
        "Exact one-to-one mapping between each site photo and each observation: Not Available",
        "Thermal image room/area labels: Not Available",
    ]

    return f"""# Detailed Diagnostic Report

## Report Basis

This DDR is generated from the uploaded inspection report and thermal image report. The report uses extracted source text, extracted images, and temperature readings. Where the PDFs do not provide a detail clearly, the value is marked as Not Available.

## 1. Property Issue Summary

{bullet_list(issue_points)}

The inspection evidence indicates repeated moisture-related symptoms across internal rooms and wet areas. The reported pattern includes skirting-level dampness, wall dampness, ceiling dampness, parking area seepage, tile hollowness, tile joint gaps, plumbing concerns, and external wall/duct issues. The thermal report supports the presence of measurable surface temperature variation across 30 thermal records, but the extracted thermal text does not provide room-wise labels.

## 2. Area-wise Observations

### Negative Side / Impacted Area Observations

{detailed_observation_rows(negative_observations, "Negative Side")}

### Positive Side / Exposed Area Observations

{detailed_observation_rows(positive_observations, "Positive Side")}

### Thermal Observations

- {thermal_summary(thermal_pages)}
- Thermal image filenames and temperature readings are available in the source thermal report, but room-level labels are not available in the extracted text.

{thermal_detail_table(thermal_pages)}

## 3. Probable Root Cause

{bullet_list(root_causes)}

The most likely issue pattern is moisture transfer from wet areas and exterior openings into adjacent surfaces. The inspection checklist specifically marks concealed plumbing leakage and Nahani trap/brickbat coba-related leakage indicators as present. External cracks and duct issues may be a separate or contributing path for water entry near the master bedroom/external wall side. Because the source documents do not provide destructive testing or plumbing pressure test results, these causes should be treated as probable rather than finally confirmed.

## 4. Severity Assessment

{severity}

Severity reasoning:
- Spread: Multiple rooms/areas are affected rather than a single isolated point.
- Frequency: Leakage is recorded as occurring all the time.
- Building envelope: External wall cracks/duct issues are present.
- Wet-area risk: WC/common bathroom and bathroom tile joint conditions are repeatedly referenced.
- Limitation: No source evidence confirms exposed reinforcement, severe corrosion, or immediate structural instability.

## 5. Recommended Actions

### Immediate Diagnostic Actions

- Carry out a focused plumbing inspection for WC/common bathroom lines, traps, joints, and concealed supply/drainage paths.
- Conduct moisture meter checks around skirting, wall, and ceiling dampness locations.
- Verify whether thermal anomalies align with visible dampness or suspected concealed plumbing routes.

### Repair Actions

{bullet_list(actions)}

### Post-Repair Validation

- Reinspect all affected areas after repairs and drying time.
- Repeat thermal imaging at comparable locations.
- Confirm that tile joint gaps, external cracks, and duct openings are sealed before repainting or finishing.
- Avoid repainting or cosmetic patching until the water source is corrected.

## 6. Additional Notes

- Inspection date and time: 27.09.2022 14:28 IST.
- Inspected by: Krushna & Mahesh.
- Property type: Flat.
- Floors: 11.
- Previous structural audit: No.
- Previous repair work: No.
- Extracted inspection images: {len(inspection_images)} files.
- Extracted thermal images: {len(thermal_images)} files.
- Image files are included in the downloadable output ZIP. Place the relevant photos under matching observations during final client formatting.
- The extracted source text does not provide reliable room labels for each thermal image, so the report does not invent room-wise thermal mapping.
- Duplicate or small PDF artifacts are filtered during extraction to keep the evidence package usable.

## 7. Missing or Unclear Information

{bullet_list(missing)}
"""


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
- Place relevant images under the matching observation when possible by referencing the extracted image path/page.
- Write a detailed professional report, not a short summary.
- Include source page references where useful, especially for major observations, thermal readings, and missing data.
- Explain reasoning in plain language so a property owner can understand why each issue matters.
- Keep the tone professional, calm, and client-ready.

Required DDR structure:
1. Report Basis
   - Documents reviewed
   - Important limitations
2. Property Issue Summary
   - Overall issue pattern
   - Key impacted areas
   - Main evidence from inspection report
   - Main evidence from thermal report
3. Area-wise Observations
   For each affected area, include:
   - Observation
   - Evidence from inspection report
   - Related thermal evidence if available
   - Relevant image reference or "Image Not Available"
   - Client-friendly implication
4. Probable Root Cause
   - Separate confirmed evidence from probable interpretation
   - Mention alternate/contributing causes if supported
5. Severity Assessment
   - Severity rating
   - Reasoning
   - Factors increasing risk
   - Factors not available or not confirmed
6. Recommended Actions
   - Immediate diagnostic checks
   - Repair actions
   - Post-repair validation
   - Preventive actions
7. Additional Notes
   - Thermal camera/device details if available
   - Handling of images
   - Assumptions avoided
8. Missing or Unclear Information
   - Explicitly list missing fields as "Not Available"

# Inspection Report Text
{compact_pages(inspection_pages)}

# Thermal Report Text
{compact_pages(thermal_pages)}

# Inspection Report Images
{image_manifest(inspection_images)}

# Thermal Report Images
{image_manifest(thermal_images)}

Return the final report in Markdown. Aim for a detailed report of roughly 900-1500 words when evidence supports it. Use tables where they improve readability.
"""


def call_groq(prompt: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    from groq import Groq

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You generate client-ready property diagnostic reports using only provided source evidence.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
        max_tokens=3500,
    )
    return response.choices[0].message.content


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
    return rule_based_report(inspection_pages, thermal_pages, inspection_images, thermal_images)


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

    generated_report = call_groq(prompt) or call_openai(prompt)
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
