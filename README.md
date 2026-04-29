# DDR Report Generator

Starter workflow for the AI Generalist assignment: read an inspection report PDF and a thermal report PDF, extract text and relevant images, then generate a client-friendly Detailed Diagnostic Report (DDR).

## Recommended Tool Split

- **Antigravity**: edit/refine this repository, run the pipeline locally, and ask the agent to improve extraction or report formatting.
- **GitHub**: host the final code, README, screenshots, sample outputs, and commit history.
- **Kaggle Python Notebook**: run the actual demo in a reproducible cloud environment using the supplied PDFs as notebook input data.
- **Streamlit Community Cloud**: deploy a simple live app from this GitHub repository.

## Streamlit App

Run locally:

```bash
streamlit run app.py
```

Deploy:

1. Push this repo to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Create a new app from the GitHub repo.
4. Set the main file path to:

```text
app.py
```

5. Optional: add secrets for automatic LLM report generation with Groq:

```toml
GROQ_API_KEY = "your-groq-api-key"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

Or use OpenAI:

```toml
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-4.1-mini"
```

Without secrets, the deployed app still extracts text/images and creates the final prompt plus a rule-based DDR.

## Kaggle Steps

1. Create a new Kaggle notebook.
2. Upload these files as notebook input data:
   - `Sample Report.pdf`
   - `Thermal Images.pdf`
3. Add this install cell:

```python
!pip install pymupdf pillow python-docx openai -q
```

4. Upload this repo's `src/ddr_pipeline.py` into the notebook, or clone your GitHub repo.
5. Run:

```python
!python src/ddr_pipeline.py \
  --inspection "/kaggle/input/YOUR_DATASET/Sample Report.pdf" \
  --thermal "/kaggle/input/YOUR_DATASET/Thermal Images.pdf" \
  --out "/kaggle/working/ddr_output" \
  --max-images-per-page 4 \
  --max-total-images 80
```

6. Optional: set `GROQ_API_KEY` and `GROQ_MODEL` as Kaggle secrets/environment variables to generate the final report automatically. You can also use `OPENAI_API_KEY` and `OPENAI_MODEL`. Without a key, the script still creates extracted text, extracted images, a structured prompt, and a rule-based DDR.

## Output Files

The pipeline creates:

- `outputs/extracted/inspection_text.json`
- `outputs/extracted/thermal_text.json`
- `outputs/images/...`
- `outputs/llm_prompt.md`
- `outputs/DDR_Report.md`

The image caps are intentional. Inspection PDFs often contain repeated icons, thumbnails, and layout artifacts, so the pipeline keeps the largest deduplicated images per page instead of dumping every embedded object.

## Submission Checklist

- GitHub repository link
- Kaggle notebook link or screenshots
- Generated DDR report
- Extracted source images used in the report
- 3-5 minute Loom video explaining:
  - what you built
  - how it works
  - limitations
  - how you would improve it
- One Google Drive folder link containing all required material
