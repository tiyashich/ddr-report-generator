import os
import shutil
import tempfile
from pathlib import Path

import streamlit as st

from src.ddr_pipeline import run


st.set_page_config(
    page_title="DDR Report Generator",
    layout="wide",
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

st.title("DDR Report Generator")
st.caption("Upload an inspection report and thermal report to generate a structured Detailed Diagnostic Report.")

with st.sidebar:
    st.header("Settings")
    max_images_per_page = st.slider("Images per page", min_value=1, max_value=8, value=4)
    max_total_images = st.slider("Maximum images per document", min_value=10, max_value=160, value=80, step=10)
    has_groq_key = bool(os.getenv("GROQ_API_KEY"))
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    if has_groq_key:
        st.info("Groq generation is enabled.")
    elif has_openai_key:
        st.info("OpenAI generation is enabled.")
    else:
        st.info("No LLM key found. The app will create a rule-based DDR and prompt.")

inspection_upload = st.file_uploader("Inspection Report PDF", type=["pdf"])
thermal_upload = st.file_uploader("Thermal Report PDF", type=["pdf"])

if st.button("Generate DDR", type="primary", disabled=not inspection_upload or not thermal_upload):
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

if "report" in st.session_state:
    st.success("DDR output generated.")

    tab_report, tab_images, tab_prompt, tab_download = st.tabs(["Report", "Evidence Images", "Prompt", "Download"])

    with tab_report:
        st.markdown(st.session_state["report"])
        if st.session_state.get("images"):
            st.divider()
            st.subheader("Evidence Images")
            st.caption("Images are extracted from the uploaded PDFs and included in the output ZIP.")
            for image in st.session_state["images"][:12]:
                st.image(image["bytes"], caption=image["name"], use_container_width=True)

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
