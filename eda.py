"""
Exploratory Data Analysis stage (proposal Method step 2).

Produces the distributions the proposal calls for:
  - rating distribution
  - text length distribution
  - reviews per establishment / category (checks for class imbalance,
    which matters given Macro F1 is the prioritized metric)
"""

import matplotlib
matplotlib.use("Agg")  # headless-safe for pipeline/CI runs
import matplotlib.pyplot as plt
import pandas as pd

import config


def run_eda():
    if not config.PROCESSED_REVIEWS_FILE.exists():
        raise FileNotFoundError(
            f"No processed reviews found at {config.PROCESSED_REVIEWS_FILE}. "
            "Run anonymize.py first."
        )

    df = pd.read_csv(config.PROCESSED_REVIEWS_FILE)

    summary = {
        "total_reviews": len(df),
        "unique_places": df["place_id"].nunique(),
        "reviews_per_category": df["category"].value_counts().to_dict(),
        "rating_distribution": df["rating"].value_counts().sort_index().to_dict(),
        "mean_text_length": round(df["text_length"].mean(), 1),
        "median_text_length": int(df["text_length"].median()),
    }

    print("\n=== EDA Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    # Rating distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    df["rating"].value_counts().sort_index().plot(kind="bar", ax=ax, color="#2b6cb0")
    ax.set_title("Rating Distribution")
    ax.set_xlabel("Rating (1-5)")
    ax.set_ylabel("Number of reviews")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "rating_distribution.png", dpi=150)
    plt.close(fig)

    # Text length distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    df["text_length"].plot(kind="hist", bins=30, ax=ax, color="#2f855a")
    ax.set_title("Review Text Length Distribution")
    ax.set_xlabel("Characters")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "text_length_distribution.png", dpi=150)
    plt.close(fig)

    # Reviews per category (checks class imbalance across establishment type)
    fig, ax = plt.subplots(figsize=(6, 4))
    df["category"].value_counts().plot(kind="bar", ax=ax, color="#b7791f")
    ax.set_title("Reviews per Establishment Category")
    ax.set_ylabel("Number of reviews")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "reviews_per_category.png", dpi=150)
    plt.close(fig)

    print(f"\nFigures saved to {config.FIGURES_DIR}/")
    return summary


if __name__ == "__main__":
    run_eda()
