# Antigravity Workflow

Use Antigravity as the working IDE for this assignment.

## Suggested Flow

1. Open this folder in Antigravity.
2. Ask Antigravity to inspect `src/ddr_pipeline.py` and improve one narrow area at a time:
   - image relevance filtering
   - area-wise observation grouping
   - DOCX/PDF report export
   - better missing/conflicting information handling
3. Keep each change committed to GitHub with a short commit message.
4. Use Kaggle for the final run so the evaluator can see the workflow is reproducible.

## Good Prompts To Use In Antigravity

```text
Improve the DDR generator so it groups observations by impacted area without inventing facts.
```

```text
Add DOCX export to the existing Markdown report while preserving image references.
```

```text
Review this repository for assignment readiness. Focus on reliability, missing data handling, and README clarity.
```

## Loom Talking Points

- The system extracts page-level text and embedded images from both PDFs.
- It preserves source page references so generated claims can be traced back.
- It asks the model to use only source evidence and to write "Not Available" where data is missing.
- It separates extraction, prompting, and report writing so the workflow can generalize to similar reports.
- Current limitation: image-to-observation matching is page-based and can be improved with computer vision or manual review.

