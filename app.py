import os
import base64
import json
import re
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ddr_pipeline import run


APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "urbanroof-logo.webp"

st.set_page_config(
    page_title="DDR Report Generator",
    layout="wide",
)


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{encoded}"


st.markdown(
    """
    <style>
    :root {
        --ddr-brand: #283842;
        --ddr-ink: #17212b;
        --ddr-muted: #5c6975;
        --ddr-line: #dbe3ea;
        --ddr-panel: #f7fafc;
        --ddr-accent: #0f766e;
        --ddr-accent-2: #365f8c;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    h1, h2, h3 {
        color: var(--ddr-ink);
        letter-spacing: 0;
    }

    .ddr-hero {
        background: var(--ddr-brand);
        border: 1px solid #344954;
        border-radius: 8px;
        padding: 1.15rem 1.25rem;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 1.15rem;
    }

    .ddr-logo-wrap {
        flex: 0 0 auto;
        width: 190px;
        max-width: 38vw;
    }

    .ddr-logo {
        display: block;
        width: 100%;
        height: auto;
    }

    .ddr-hero-text {
        min-width: 0;
        background: rgba(0, 0, 0, 0.22);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        padding: 0.85rem 1rem;
    }

    .ddr-kicker {
        color: #f6b33f;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .ddr-hero .ddr-title {
        color: #ffffff;
        font-size: 2.25rem;
        line-height: 1.12;
        font-weight: 760;
        margin: 0;
        text-shadow: none;
        -webkit-text-fill-color: #ffffff;
    }

    .ddr-subtitle {
        color: #edf4f7;
        font-size: 1.02rem;
        max-width: 760px;
        margin-top: 0.65rem;
    }

    @media (max-width: 720px) {
        .ddr-hero {
            align-items: flex-start;
            flex-direction: column;
        }

        .ddr-logo-wrap {
            width: 160px;
            max-width: 70vw;
        }

        .ddr-title {
            font-size: 1.8rem;
        }
    }

    .ddr-status {
        border: 1px solid var(--ddr-line);
        border-left: 4px solid var(--ddr-accent);
        background: var(--ddr-panel);
        border-radius: 8px;
        padding: 0.85rem 1rem;
        min-height: 86px;
    }

    .ddr-status strong {
        display: block;
        color: var(--ddr-ink);
        font-size: 0.95rem;
        margin-bottom: 0.2rem;
    }

    .ddr-status span {
        color: var(--ddr-muted);
        font-size: 0.9rem;
    }

    .ddr-flow {
        border: 1px solid var(--ddr-line);
        border-radius: 8px;
        background: #ffffff;
        padding: 1rem;
        margin: 1rem 0 0.4rem 0;
    }

    .ddr-flow-title {
        color: var(--ddr-ink);
        font-size: 1rem;
        font-weight: 750;
        margin-bottom: 0.55rem;
    }

    .ddr-flow-steps {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.7rem;
    }

    .ddr-flow-step {
        border-left: 3px solid var(--ddr-accent);
        background: var(--ddr-panel);
        border-radius: 6px;
        padding: 0.7rem 0.8rem;
        color: var(--ddr-muted);
        font-size: 0.9rem;
    }

    .ddr-flow-step strong {
        display: block;
        color: var(--ddr-ink);
        margin-bottom: 0.15rem;
    }

    .ddr-watermark {
        color: #72818c;
        font-size: 0.82rem;
        text-align: right;
        margin: 0.6rem 0 1rem 0;
    }

    .ddr-section-title {
        color: var(--ddr-ink);
        font-size: 1.05rem;
        font-weight: 700;
        margin: 1.2rem 0 0.25rem 0;
    }

    div[data-testid="stFileUploader"] {
        border: 1px solid var(--ddr-line);
        border-radius: 8px;
        padding: 0.7rem 0.8rem 0.25rem 0.8rem;
        background: #ffffff;
    }

    div[data-testid="stFileUploader"] label {
        font-weight: 700;
        color: var(--ddr-ink);
    }

    .stButton > button {
        min-height: 2.85rem;
        border-radius: 8px;
        font-weight: 700;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid var(--ddr-line);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.7rem 1rem;
    }

    .stDownloadButton > button {
        border-radius: 8px;
        min-height: 2.8rem;
    }

    [data-testid="stSidebar"] {
        background: #f4f7fa;
        border-right: 1px solid var(--ddr-line);
    }

    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--ddr-ink);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def save_upload(uploaded_file, destination: Path) -> Path:
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def make_zip(output_dir: Path) -> Path:
    zip_base = output_dir.parent / "ddr_output"
    zip_path = shutil.make_archive(str(zip_base), "zip", output_dir)
    return Path(zip_path)


def collect_images(output_dir: Path) -> list[dict[str, object]]:
    images = []
    image_root = output_dir / "images"
    for image_path in sorted(image_root.rglob("*.png")):
        images.append(
            {
                "name": str(image_path.relative_to(output_dir)),
                "bytes": image_path.read_bytes(),
            }
        )
    return images


def collect_thermal_readings(output_dir: Path) -> pd.DataFrame:
    thermal_text_path = output_dir / "extracted" / "thermal_text.json"
    if not thermal_text_path.exists():
        return pd.DataFrame()

    pages = json.loads(thermal_text_path.read_text(encoding="utf-8"))
    rows = []
    for page in pages:
        text = page.get("text", "")
        hotspot_match = re.search(r"Hotspot\s*:\s*([0-9.]+)", text, flags=re.IGNORECASE)
        coldspot_match = re.search(r"Coldspot\s*:\s*([0-9.]+)", text, flags=re.IGNORECASE)
        image_match = re.search(r"Thermal image\s*:\s*([A-Z0-9_.-]+)", text, flags=re.IGNORECASE)
        if hotspot_match and coldspot_match:
            hotspot = float(hotspot_match.group(1))
            coldspot = float(coldspot_match.group(1))
            rows.append(
                {
                    "Page": int(page.get("page", len(rows) + 1)),
                    "Thermal Image": image_match.group(1) if image_match else "Not Available",
                    "Hotspot": hotspot,
                    "Coldspot": coldspot,
                    "Delta": round(hotspot - coldspot, 2),
                }
            )

    return pd.DataFrame(rows)


def configure_api_key() -> None:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
        model = st.secrets.get("OPENAI_MODEL", None)
        groq_api_key = st.secrets.get("GROQ_API_KEY", None)
        groq_model = st.secrets.get("GROQ_MODEL", None)
    except Exception:
        api_key = None
        model = None
        groq_api_key = None
        groq_model = None

    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    if model:
        os.environ["OPENAI_MODEL"] = model

    if groq_api_key:
        os.environ["GROQ_API_KEY"] = groq_api_key

    if groq_model:
        os.environ["GROQ_MODEL"] = groq_model


configure_api_key()
logo_data_uri = image_data_uri(LOGO_PATH)

has_groq_key = bool(os.getenv("GROQ_API_KEY"))
has_openai_key = bool(os.getenv("OPENAI_API_KEY"))

if has_groq_key:
    llm_status = "Groq generation enabled"
    llm_detail = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
elif has_openai_key:
    llm_status = "OpenAI generation enabled"
    llm_detail = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
else:
    llm_status = "Rule-based mode"
    llm_detail = "Add Groq or OpenAI secrets for model-written output"

st.markdown(
    f"""
    <div class="ddr-hero">
        <div class="ddr-logo-wrap">
            {'<img class="ddr-logo" src="' + logo_data_uri + '" alt="UrbanRoof logo">' if logo_data_uri else ''}
        </div>
        <div class="ddr-hero-text">
            <div class="ddr-kicker">Applied AI Builder</div>
            <div class="ddr-title">DDR Report Generator</div>
            <div class="ddr-subtitle">
                Convert an inspection PDF and a thermal PDF into a structured Detailed Diagnostic Report with extracted evidence.
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

status_col_1, status_col_2, status_col_3 = st.columns(3)
with status_col_1:
    st.markdown(
        f"""<div class="ddr-status"><strong>LLM Mode</strong><span>{llm_status}<br>{llm_detail}</span></div>""",
        unsafe_allow_html=True,
    )
with status_col_2:
    st.markdown(
        """<div class="ddr-status"><strong>Evidence Handling</strong><span>Text extraction, image filtering, and output ZIP packaging</span></div>""",
        unsafe_allow_html=True,
    )
with status_col_3:
    st.markdown(
        """<div class="ddr-status"><strong>Report Structure</strong><span>Summary, observations, root cause, severity, actions, and missing data</span></div>""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="ddr-watermark">Prepared by Tiyas</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ddr-flow">
        <div class="ddr-flow-title">How it works</div>
        <div class="ddr-flow-steps">
            <div class="ddr-flow-step"><strong>1. Upload PDFs</strong>Inspection and thermal reports are provided as source documents.</div>
            <div class="ddr-flow-step"><strong>2. Extract evidence</strong>Text, thermal readings, and embedded images are extracted and organized.</div>
            <div class="ddr-flow-step"><strong>3. Generate DDR</strong>Groq writes the client-ready report, with a rule-based fallback if the model is unavailable.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Settings")
    max_images_per_page = st.slider("Images per page", min_value=1, max_value=8, value=4)
    max_total_images = st.slider("Maximum images per document", min_value=10, max_value=160, value=80, step=10)
    if has_groq_key:
        st.success("Groq generation is enabled.")
    elif has_openai_key:
        st.success("OpenAI generation is enabled.")
    else:
        st.info("No LLM key found. The app will create a rule-based DDR and prompt.")

st.markdown('<div class="ddr-section-title">Source Documents</div>', unsafe_allow_html=True)
upload_col_1, upload_col_2 = st.columns(2)
with upload_col_1:
    inspection_upload = st.file_uploader("Inspection Report PDF", type=["pdf"])
    if inspection_upload:
        st.caption(f"Selected: {inspection_upload.name}")
with upload_col_2:
    thermal_upload = st.file_uploader("Thermal Report PDF", type=["pdf"])
    if thermal_upload:
        st.caption(f"Selected: {thermal_upload.name}")

button_col, hint_col = st.columns([1, 2])
with button_col:
    generate_clicked = st.button("Generate DDR", type="primary", disabled=not inspection_upload or not thermal_upload, use_container_width=True)
with hint_col:
    if not inspection_upload or not thermal_upload:
        st.caption("Upload both PDFs to enable report generation.")
    else:
        st.caption("Ready to extract evidence and generate the DDR.")

if generate_clicked:
    with st.spinner("Extracting report text, filtering images, and building the DDR..."):
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            inspection_path = save_upload(inspection_upload, work_dir / "inspection_report.pdf")
            thermal_path = save_upload(thermal_upload, work_dir / "thermal_report.pdf")
            output_dir = work_dir / "ddr_output"

            run(
                inspection_pdf=inspection_path,
                thermal_pdf=thermal_path,
                output_dir=output_dir,
                max_images_per_page=max_images_per_page,
                max_total_images=max_total_images,
            )

            report_path = output_dir / "DDR_Report.md"
            prompt_path = output_dir / "llm_prompt.md"
            zip_path = make_zip(output_dir)

            st.session_state["report"] = read_text(report_path)
            st.session_state["prompt"] = read_text(prompt_path)
            st.session_state["zip_bytes"] = zip_path.read_bytes()
            st.session_state["images"] = collect_images(output_dir)
            st.session_state["thermal_df"] = collect_thermal_readings(output_dir)

if "report" in st.session_state:
    st.success("DDR output generated successfully.")

    tab_report, tab_charts, tab_images, tab_prompt, tab_download = st.tabs(
        ["Report", "Thermal Charts", "Evidence Images", "Prompt", "Download"]
    )

    with tab_report:
        st.markdown('<div class="ddr-section-title">Generated Report</div>', unsafe_allow_html=True)
        st.markdown(st.session_state["report"])
        if st.session_state.get("images"):
            st.divider()
            st.markdown('<div class="ddr-section-title">Evidence Preview</div>', unsafe_allow_html=True)
            st.caption("Images are extracted from the uploaded PDFs and included in the output ZIP.")
            for image in st.session_state["images"][:12]:
                st.image(image["bytes"], caption=image["name"], use_container_width=True)

    with tab_charts:
        thermal_df = st.session_state.get("thermal_df", pd.DataFrame())
        if thermal_df.empty:
            st.warning("Thermal chart data is Not Available")
        else:
            metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
            metric_col_1.metric("Thermal Records", len(thermal_df))
            metric_col_2.metric("Max Hotspot", f"{thermal_df['Hotspot'].max():.1f} deg C")
            metric_col_3.metric("Max Delta", f"{thermal_df['Delta'].max():.1f} deg C")

            chart_df = thermal_df.set_index("Page")[["Hotspot", "Coldspot"]]
            st.markdown('<div class="ddr-section-title">Hotspot vs Coldspot Trend</div>', unsafe_allow_html=True)
            st.line_chart(chart_df)

            st.markdown('<div class="ddr-section-title">Temperature Difference by Thermal Record</div>', unsafe_allow_html=True)
            st.bar_chart(thermal_df.set_index("Page")["Delta"])

            st.markdown('<div class="ddr-section-title">Thermal Reading Table</div>', unsafe_allow_html=True)
            st.dataframe(thermal_df, use_container_width=True, hide_index=True)

    with tab_images:
        images = st.session_state.get("images", [])
        if not images:
            st.warning("Image Not Available")
        else:
            st.caption(f"{len(images)} extracted images. Download the ZIP to access all image files.")
            columns = st.columns(3)
            for index, image in enumerate(images):
                with columns[index % 3]:
                    st.image(image["bytes"], caption=image["name"], use_container_width=True)

    with tab_prompt:
        st.text_area("LLM prompt", st.session_state["prompt"], height=420)

    with tab_download:
        st.download_button(
            "Download DDR output ZIP",
            data=st.session_state["zip_bytes"],
            file_name="ddr_output.zip",
            mime="application/zip",
        )
