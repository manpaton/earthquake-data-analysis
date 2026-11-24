import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import mannwhitneyu

DB_PATH = Path(__file__).with_name("earthquakes.db")
FIGURES_DIR = Path(__file__).with_name("figures")


def load_from_db(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load cleaned earthquake records from SQLite database."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM earthquakes", conn)

def run_analysis(df: pd.DataFrame, output_dir: Path = FIGURES_DIR) -> None:
    """Generate and save 4 publication-grade exploratory charts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")

    # 1. Spatial Epicenter Map (Longitude vs Latitude, sized by Magnitude, colored by Depth)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    scatter = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=np.clip(df["depth_km"], 0, None),
        s=np.power(df["magnitude"] + 1.5, 2.6) * 6,
        cmap="plasma_r",
        alpha=0.8,
        edgecolors="black",
        linewidths=0.5,
    )
    cbar = plt.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label("Hypocenter Depth (km)", fontweight="bold")
    ax.axhline(0, color="gray", linestyle=":", linewidth=0.8)
    ax.axvline(0, color="gray", linestyle=":", linewidth=0.8)
    ax.set_title("Global Seismic Epicenter Map (Size = Magnitude, Color = Depth)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")
    plt.tight_layout()
    plt.savefig(output_dir / "01_spatial_epicenter_map.png", dpi=180)
    plt.close()

    # 2. Regional Magnitude Distribution: Boxplot + Jittered Stripplot (Top 6 Regions)
    top6_regions = df["region"].value_counts().head(6).index
    df_top6 = df[df["region"].isin(top6_regions)]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.boxplot(
        data=df_top6,
        x="region",
        y="magnitude",
        order=top6_regions,
        palette="Blues",
        width=0.5,
        fliersize=0,
        ax=ax,
    )
    sns.stripplot(
        data=df_top6,
        x="region",
        y="magnitude",
        order=top6_regions,
        hue="status",
        palette={"automatic": "#1f77b4", "reviewed": "#d62728"},
        size=6,
        jitter=0.18,
        alpha=0.85,
        ax=ax,
    )
    ax.set_title("Magnitude Spread & Review Status Across Top 6 Active Regions", fontsize=13, fontweight="bold")
    ax.set_xlabel("Region (Ordered by Event Count)")
    ax.set_ylabel("Magnitude")
    ax.legend(title="USGS Status", loc="upper right")
    plt.tight_layout()
    plt.savefig(output_dir / "02_regional_magnitude_boxplot.png", dpi=180)
    plt.close()

    # 3. Depth vs. Released Seismic Energy (Log Scale) with Regression Trend
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for status_val, color in [("automatic", "#2b5c8f"), ("reviewed", "#e67e22")]:
        subset = df[df["status"] == status_val]
        ax.scatter(
            subset["depth_km"],
            subset["energy_joules"],
            label=f"{status_val.capitalize()} (n={len(subset)})",
            color=color,
            alpha=0.75,
            s=55,
            edgecolors="white",
            linewidths=0.4,
        )
    ax.set_yscale("log")
    ax.set_title("Hypocenter Depth vs. Released Seismic Energy (Log10 Scale)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Depth (km)")
    ax.set_ylabel("Estimated Energy (Joules, log scale)")
    ax.legend(title="Verification Status")
    plt.tight_layout()
    plt.savefig(output_dir / "03_depth_vs_energy_log.png", dpi=180)
    plt.close()

    # 4. Hourly Activity Timeline Stacked by Magnitude Category
    hourly_pivot = (
        df.pivot_table(index="event_hour", columns="mag_category", values="id", aggfunc="count", fill_value=0)
        .reindex(range(24), fill_value=0)
    )
    ordered_cols = [c for c in ["micro", "minor", "light", "moderate_plus"] if c in hourly_pivot.columns]
    hourly_pivot = hourly_pivot[ordered_cols]

    fig, ax = plt.subplots(figsize=(10, 5))
    hourly_pivot.plot(
        kind="bar",
        stacked=True,
        colormap="YlOrRd",
        edgecolor="black",
        linewidth=0.4,
        ax=ax,
    )
    ax.set_title("24-Hour Seismic Activity Profile (UTC) by Magnitude Class", fontsize=13, fontweight="bold")
    ax.set_xlabel("Hour of Day (UTC)")
    ax.set_ylabel("Number of Earthquakes")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(title="Magnitude Class")
    plt.tight_layout()
    plt.savefig(output_dir / "04_hourly_activity_stacked.png", dpi=180)
    plt.close()

    print(f"Saved 4 analytical charts to: {output_dir}")

def print_statistical_summary(df: pd.DataFrame) -> None:
    """Print descriptive statistics, correlation metrics, and hypothesis test results."""
    print("\n=== 1. Descriptive Statistics ===")
    stats_table = df[["magnitude", "depth_km", "energy_joules"]].describe().round(3)
    print(stats_table)

    total_energy_j = df["energy_joules"].sum()
    tnt_tons = total_energy_j / 4.184e9
    corr_pearson = df["depth_km"].corr(df["magnitude"], method="pearson")
    corr_spearman = df["depth_km"].corr(df["magnitude"], method="spearman")
    reviewed_pct = (df["status"] == "reviewed").mean() * 100

    # Hypothesis test: Are 'reviewed' earthquakes significantly stronger than 'automatic' ones?
    rev_mag = df[df["status"] == "reviewed"]["magnitude"]
    auto_mag = df[df["status"] == "automatic"]["magnitude"]
    u_stat, p_val = mannwhitneyu(rev_mag, auto_mag, alternative="greater")

    strongest = df.loc[df["magnitude"].idxmax()]
    deepest = df.loc[df["depth_km"].idxmax()]

    print("\n=== 2. Geophysical & Hypothesis Testing Summary ===")
    print(f"Total events analyzed:     {len(df)}")
    print(f"Reviewed by seismologists: {reviewed_pct:.1f}%")
    print(f"Total seismic energy:      {total_energy_j:.3e} J (~{tnt_tons:.2f} tons of TNT)")
    print(f"Depth-Magnitude Corr:      Pearson r = {corr_pearson:.3f}, Spearman rho = {corr_spearman:.3f}")
    print(f"Mann-Whitney U test:       U = {u_stat:.1f}, p-value = {p_val:.3e} (reviewed > automatic)")
    print(f"Strongest event:           M{strongest['magnitude']} in {strongest['place']} (depth {strongest['depth_km']} km)")
    print(f"Deepest event:             {deepest['depth_km']} km in {deepest['place']} (M{deepest['magnitude']})")    

if __name__ == "__main__":
    df_db = load_from_db()
    print_statistical_summary(df_db)
    run_analysis(df_db)