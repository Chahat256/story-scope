#!/usr/bin/env python3
"""
StoryScope Evaluation Harness
==============================

Runs the literary analysis service against a golden dataset of well-known novels
and computes precision, recall, and F1 for character detection, theme coverage,
and trope detection.

Usage (from the backend/ directory with PYTHONPATH set):
    cd /path/to/story_scope
    PYTHONPATH=backend python evals/run_evals.py --pdf-dir /path/to/pdfs

The PDFs must be named exactly as the novel IDs in golden_dataset.json
(e.g. pride_and_prejudice.pdf, frankenstein.pdf).

Alternatively, point at an already-running StoryScope API:
    python evals/run_evals.py --api-url http://localhost:8000 --pdf-dir /path/to/pdfs

Outputs:
    - Table printed to stdout
    - evals/results/run_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Metrics helpers ────────────────────────────────────────────────────────────


def normalise(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s.lower())).strip()


def token_overlap(pred: str, gold: str) -> float:
    """Compute token-level Jaccard similarity between two strings."""
    pred_tokens = set(normalise(pred).split())
    gold_tokens = set(normalise(gold).split())
    if not gold_tokens:
        return 0.0
    intersection = pred_tokens & gold_tokens
    union = pred_tokens | gold_tokens
    return len(intersection) / len(union)


def fuzzy_match(predicted: List[str], gold: List[str], threshold: float = 0.4) -> Tuple[int, int, int]:
    """
    Match predicted items against gold items using token overlap.

    Returns (true_positives, false_positives, false_negatives).
    """
    matched_gold = set()
    true_positives = 0

    for pred in predicted:
        best_score = 0.0
        best_idx = -1
        for i, g in enumerate(gold):
            if i in matched_gold:
                continue
            score = token_overlap(pred, g)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_score >= threshold and best_idx != -1:
            true_positives += 1
            matched_gold.add(best_idx)

    false_positives = len(predicted) - true_positives
    false_negatives = len(gold) - len(matched_gold)
    return true_positives, false_positives, false_negatives


def precision_recall_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


# ── Analysis runner ────────────────────────────────────────────────────────────


def run_analysis_direct(pdf_path: str) -> Optional[Dict[str, Any]]:
    """Run analysis by importing services directly (no API server needed)."""
    try:
        import uuid
        # Add backend to sys.path
        backend_dir = Path(__file__).parent.parent / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))

        from app.services.pdf_service import extract_text_from_pdf
        from app.services.chunking_service import chunk_pages
        from app.services.embedding_service import index_chunks
        from app.services.analysis_service import run_full_analysis

        job_id = f"eval_{uuid.uuid4().hex[:8]}"
        pages = extract_text_from_pdf(pdf_path)
        chunks, _ = chunk_pages(pages)
        index_chunks(job_id, chunks)
        report = run_full_analysis(job_id, pages)
        return report.model_dump()

    except Exception as e:
        print(f"  ERROR during direct analysis: {e}")
        return None


def run_analysis_api(api_url: str, pdf_path: str) -> Optional[Dict[str, Any]]:
    """Upload PDF to running API and poll until analysis complete."""
    try:
        import requests

        with open(pdf_path, "rb") as f:
            resp = requests.post(
                f"{api_url}/api/upload",
                files={"file": (Path(pdf_path).name, f, "application/pdf")},
                timeout=30,
            )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        print(f"  Uploaded, job_id={job_id}")

        # Poll until complete
        for _ in range(180):  # up to 3 minutes
            time.sleep(5)
            status_resp = requests.get(f"{api_url}/api/status/{job_id}", timeout=10)
            status = status_resp.json()["status"]
            print(f"  Status: {status}")
            if status == "complete":
                break
            if status == "failed":
                print(f"  Analysis failed!")
                return None

        report_resp = requests.get(f"{api_url}/api/report/{job_id}", timeout=10)
        report_resp.raise_for_status()
        return report_resp.json()

    except Exception as e:
        print(f"  ERROR during API analysis: {e}")
        return None


# ── Evaluation ─────────────────────────────────────────────────────────────────


def evaluate_novel(
    novel: Dict[str, Any],
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute all metrics for one novel."""
    # ── Characters ────────────────────────────────────────────────────────
    predicted_chars = [c["name"] for c in report.get("characters", [])]
    gold_chars = novel["expected_characters"]
    tp, fp, fn = fuzzy_match(predicted_chars, gold_chars, threshold=0.4)
    char_p, char_r, char_f1 = precision_recall_f1(tp, fp, fn)

    # ── Themes ────────────────────────────────────────────────────────────
    predicted_themes = [t["theme"] for t in report.get("themes", [])]
    gold_themes = novel["expected_themes"]
    tp_t, fp_t, fn_t = fuzzy_match(predicted_themes, gold_themes, threshold=0.3)
    theme_p, theme_r, theme_f1 = precision_recall_f1(tp_t, fp_t, fn_t)

    # ── Tropes ────────────────────────────────────────────────────────────
    predicted_tropes = [t["trope_id"] for t in report.get("tropes", [])]
    gold_tropes = novel["expected_tropes"]
    # Trope IDs are exact — use direct set intersection
    tp_tr = len(set(predicted_tropes) & set(gold_tropes))
    fp_tr = len(set(predicted_tropes) - set(gold_tropes))
    fn_tr = len(set(gold_tropes) - set(predicted_tropes))
    trope_p, trope_r, trope_f1 = precision_recall_f1(tp_tr, fp_tr, fn_tr)

    # ── Overview sanity ────────────────────────────────────────────────────
    overview = report.get("overview", {})
    title_match = token_overlap(overview.get("title_guess", ""), novel["title"]) >= 0.5
    author_match = token_overlap(overview.get("author_guess", "") or "", novel["author"]) >= 0.4

    return {
        "novel_id": novel["id"],
        "title": novel["title"],
        "characters": {
            "predicted": predicted_chars,
            "gold": gold_chars,
            "precision": char_p,
            "recall": char_r,
            "f1": char_f1,
        },
        "themes": {
            "predicted": predicted_themes,
            "gold": gold_themes,
            "precision": theme_p,
            "recall": theme_r,
            "f1": theme_f1,
        },
        "tropes": {
            "predicted": predicted_tropes,
            "gold": gold_tropes,
            "precision": trope_p,
            "recall": trope_r,
            "f1": trope_f1,
        },
        "overview_sanity": {
            "title_match": title_match,
            "author_match": author_match,
        },
    }


def print_results_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted results table to stdout."""
    header = f"{'Novel':<35} {'Char F1':>7} {'Theme F1':>8} {'Trope F1':>8} {'Title':>5} {'Author':>6}"
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))

    char_f1s, theme_f1s, trope_f1s = [], [], []
    for r in results:
        novel_name = r["title"][:33]
        cf = r["characters"]["f1"]
        tf = r["themes"]["f1"]
        pf = r["tropes"]["f1"]
        title_ok = "✓" if r["overview_sanity"]["title_match"] else "✗"
        author_ok = "✓" if r["overview_sanity"]["author_match"] else "✗"
        print(f"{novel_name:<35} {cf:>7.3f} {tf:>8.3f} {pf:>8.3f} {title_ok:>5} {author_ok:>6}")
        char_f1s.append(cf)
        theme_f1s.append(tf)
        trope_f1s.append(pf)

    print("-" * len(header))
    avg_char = sum(char_f1s) / len(char_f1s) if char_f1s else 0
    avg_theme = sum(theme_f1s) / len(theme_f1s) if theme_f1s else 0
    avg_trope = sum(trope_f1s) / len(trope_f1s) if trope_f1s else 0
    print(f"{'AVERAGE':<35} {avg_char:>7.3f} {avg_theme:>8.3f} {avg_trope:>8.3f}")
    print("=" * len(header))
    print(f"\nOverall macro-F1: {(avg_char + avg_theme + avg_trope) / 3:.3f}")


# ── Main ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="StoryScope evaluation harness")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing novel PDFs named by novel ID")
    parser.add_argument("--api-url", default=None, help="If set, use running API instead of direct imports")
    parser.add_argument("--novels", nargs="+", default=None, help="Novel IDs to evaluate (default: all)")
    args = parser.parse_args()

    dataset_path = Path(__file__).parent / "golden_dataset.json"
    dataset = json.loads(dataset_path.read_text())
    novels = dataset["novels"]

    if args.novels:
        novels = [n for n in novels if n["id"] in args.novels]

    pdf_dir = Path(args.pdf_dir)
    results: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for novel in novels:
        pdf_path = pdf_dir / f"{novel['id']}.pdf"
        if not pdf_path.exists():
            print(f"\n[SKIP] {novel['title']} — {pdf_path} not found")
            skipped.append(novel["id"])
            continue

        print(f"\n[EVAL] {novel['title']} ({novel['author']})")

        if args.api_url:
            report = run_analysis_api(args.api_url, str(pdf_path))
        else:
            report = run_analysis_direct(str(pdf_path))

        if report is None:
            print(f"  Analysis returned None — skipping")
            skipped.append(novel["id"])
            continue

        result = evaluate_novel(novel, report)
        results.append(result)
        print(f"  Characters F1={result['characters']['f1']:.3f}  "
              f"Themes F1={result['themes']['f1']:.3f}  "
              f"Tropes F1={result['tropes']['f1']:.3f}")

    if not results:
        print("\nNo novels were successfully evaluated.")
        sys.exit(1)

    print_results_table(results)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(__file__).parent / "results" / f"run_{timestamp}.json"
    output_path.parent.mkdir(exist_ok=True)

    summary = {
        "run_at": datetime.now().isoformat(),
        "dataset_version": dataset.get("version", "unknown"),
        "novels_evaluated": len(results),
        "novels_skipped": skipped,
        "avg_character_f1": round(sum(r["characters"]["f1"] for r in results) / len(results), 3),
        "avg_theme_f1": round(sum(r["themes"]["f1"] for r in results) / len(results), 3),
        "avg_trope_f1": round(sum(r["tropes"]["f1"] for r in results) / len(results), 3),
        "per_novel": results,
    }
    summary["overall_macro_f1"] = round(
        (summary["avg_character_f1"] + summary["avg_theme_f1"] + summary["avg_trope_f1"]) / 3, 3
    )

    output_path.write_text(json.dumps(summary, indent=2))
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
