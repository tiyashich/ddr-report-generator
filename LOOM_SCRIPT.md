# Loom Script

Use this as a 3-5 minute recording guide.

## 1. Introduction

Hi, I am Tiyas. For this assignment, I built an AI-powered DDR Report Generator for UrbanRoof-style inspection workflows. The goal is to convert an inspection PDF and a thermal image PDF into a structured Detailed Diagnostic Report.

## 2. What I Built

The project includes a Streamlit web app, a reusable Python pipeline, and a GitHub repository. The app accepts two PDFs: the inspection report and the thermal report. It then extracts text, thermal readings, and relevant embedded images, and generates a structured DDR.

## 3. How It Works

The workflow has three main stages:

1. The user uploads the inspection and thermal PDFs.
2. The Python pipeline extracts page-level text, thermal hotspot/coldspot data, and embedded images.
3. The extracted evidence is converted into a structured prompt and sent to Groq. Groq generates the final client-ready DDR.

If the Groq API is unavailable, the app has a rule-based fallback that still creates a usable DDR from the extracted evidence.

## 4. Output

The generated DDR includes:

- Property issue summary
- Area-wise observations
- Probable root cause
- Severity assessment with reasoning
- Recommended actions
- Additional notes
- Missing or unclear information

The app also shows thermal charts, extracted evidence images, the model prompt, and a downloadable ZIP containing the report and extracted files.

## 5. Limitations

The system avoids inventing facts. If the source documents do not clearly provide a detail, the report marks it as Not Available. One limitation is that exact photo-to-observation mapping is not always available from the PDF text, so the app extracts and displays the evidence images but does not pretend to know a perfect one-to-one mapping unless the source supports it.

## 6. Improvements

With more time, I would improve image-to-observation matching using vision models, export the final DDR directly as a polished PDF or DOCX, and add human review controls before final submission to a client.

