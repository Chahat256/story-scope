# StoryScope Evaluation Framework

This directory contains tools for measuring the quality of StoryScope's literary analysis pipeline against a curated golden dataset of well-known novels.

---

## Golden Dataset

`golden_dataset.json` contains 7 canonical English novels, all available on [Project Gutenberg](https://www.gutenberg.org):

| Novel | Author | Genre |
|-------|--------|-------|
| Pride and Prejudice | Jane Austen | Romantic Fiction |
| Frankenstein | Mary Shelley | Gothic / Sci-Fi |
| Adventures of Huckleberry Finn | Mark Twain | Adventure / Literary |
| A Study in Scarlet | Arthur Conan Doyle | Mystery / Detective |
| Dracula | Bram Stoker | Gothic Horror |
| Great Expectations | Charles Dickens | Bildungsroman |
| The Picture of Dorian Gray | Oscar Wilde | Gothic / Philosophical |

For each novel, the dataset records:
- **Expected major characters** (names as they appear in the text)
- **Expected themes** (human-curated labels)
- **Expected tropes** (exact IDs from `TROPE_LIBRARY` in `analysis_service.py`)

---

## Metrics

### Character Detection (Precision / Recall / F1)
Characters are matched using **token-level Jaccard similarity** (threshold 0.4). This handles variations like "Mr. Darcy" vs "Darcy" or "Victor" vs "Victor Frankenstein".

- **Precision** — of all characters the model predicted, what fraction were real major characters?
- **Recall** — of all expected major characters, what fraction did the model find?
- **F1** — harmonic mean of precision and recall.

### Theme Coverage (Precision / Recall / F1)
Themes are fuzzy-matched against expected themes (threshold 0.3 Jaccard, since themes are often paraphrases). A predicted "Loss and Grief" should match gold "Death and Loss".

### Trope Detection (Precision / Recall / F1)
Tropes are matched exactly by `trope_id` (e.g. `enemies_to_lovers`). Since IDs come from a controlled vocabulary, fuzzy matching is not needed.

### Overview Sanity
Binary checks that `title_guess` and `author_guess` have token overlap ≥ 50% and 40% respectively with the ground truth.

---

## How to Run

### Option A: Direct (no running server)

```bash
# From the project root
cd story_scope

# Install backend deps if not already done
pip install -r backend/requirements.txt

# Download novels from Project Gutenberg and save as {novel_id}.pdf
# e.g. pride_and_prejudice.pdf, frankenstein.pdf, etc.

PYTHONPATH=backend python evals/run_evals.py --pdf-dir /path/to/pdfs
```

### Option B: Against running API

```bash
# Start the API first
cd backend && uvicorn main:app --reload

# Run evals
python evals/run_evals.py --api-url http://localhost:8000 --pdf-dir /path/to/pdfs
```

### Evaluating a subset

```bash
python evals/run_evals.py --pdf-dir /pdfs --novels pride_and_prejudice frankenstein
```

---

## Output

Results are printed as a table and saved to `evals/results/run_YYYYMMDD_HHMMSS.json`.

### Example output

```
===================================================================
Novel                               Char F1  Theme F1  Trope F1  Title Author
===================================================================
Pride and Prejudice                   0.714     0.600     0.500      ✓      ✓
Frankenstein                          0.667     0.800     0.500      ✓      ✓
Adventures of Huckleberry Finn        0.571     0.600     0.400      ✓      ✓
A Study in Scarlet                    0.800     0.667     0.667      ✓      ✓
Dracula                               0.667     0.600     0.667      ✓      ✗
Great Expectations                    0.571     0.600     0.500      ✓      ✓
The Picture of Dorian Gray            0.667     0.500     0.500      ✓      ✓
-------------------------------------------------------------------
AVERAGE                               0.665     0.624     0.533
===================================================================

Overall macro-F1: 0.607
```

---

## Methodology Notes

- The golden dataset is **static** — it reflects well-established literary scholarship, not the model's output.
- Fuzzy matching is intentionally generous. The goal is not to penalise paraphrases ("Romantic tension" vs "Forbidden love") but to catch actual misses.
- Trope IDs are strict because the model can only output IDs from the controlled `TROPE_LIBRARY`. A wrong trope ID is a real error.
- The `expected_characters` lists include more names than the model's 2–6 limit. High recall requires finding the *most significant* characters, not all named characters.
- Running the eval suite against Gutenberg texts (which may have Project Gutenberg headers, footnotes, etc.) gives a slightly pessimistic score compared to clean PDFs. Clean the text first for fairer comparison.

---

## Extending the Dataset

To add a novel:
1. Add an entry to `golden_dataset.json` with the required fields.
2. Download the PDF from Project Gutenberg and name it `{novel_id}.pdf`.
3. Run the evals — no code changes required.

Trope IDs must come from `backend/app/services/analysis_service.py::TROPE_LIBRARY`.
