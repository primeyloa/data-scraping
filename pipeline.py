"""
Orchestrator for the full Ghana Tourism ABSA data pipeline.

Usage:
    python pipeline.py --steps collect anonymize eda
    python pipeline.py --steps all
    python pipeline.py --steps collect      # just re-run collection (resumable)

Each stage is independent and idempotent where possible:
  collect    -> scraper.run_collection()      writes data/raw/reviews_raw.jsonl
  anonymize  -> anonymize.run_anonymization()  writes data/processed/reviews_clean.csv
                                                + annotation_template.csv
  eda        -> eda.run_eda()                  writes data/figures/*.png + prints summary
"""

import argparse
import logging

import anonymize
import eda
import scraper

log = logging.getLogger("pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

STEP_FUNCS = {
    "collect": scraper.run_collection,
    "anonymize": anonymize.run_anonymization,
    "eda": eda.run_eda,
}


def main():
    parser = argparse.ArgumentParser(description="Ghana Tourism ABSA data pipeline")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=list(STEP_FUNCS.keys()) + ["all"],
        default=["all"],
        help="Which pipeline stages to run, in order.",
    )
    args = parser.parse_args()

    steps = list(STEP_FUNCS.keys()) if "all" in args.steps else args.steps

    for step in steps:
        log.info("=== Running stage: %s ===", step)
        STEP_FUNCS[step]()

    log.info("Pipeline run complete.")


if __name__ == "__main__":
    main()
