from pathlib import Path
import pandas as pd
import numpy as np

VALIDATED_DATA_PATH = Path(__file__).with_name("validated_earthquakes.json")


def load_validated_data(path: Path = VALIDATED_DATA_PATH) -> pd.DataFrame:
    return pd.read_json(path)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Handle missing values and drop duplicate earthquake IDs
    df["place"] = df["place"].fillna("Unknown")
    df["mag_type"] = df["mag_type"].fillna("unknown")
    df["status"] = df["status"].fillna("automatic")
    df = df.dropna(subset=["id", "magnitude", "depth_km", "latitude", "longitude", "time"])
    df = df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

    # 2. Convert Unix timestamps (ms) to readable UTC datetime
    df["event_datetime"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["updated_datetime"] = pd.to_datetime(df["updated"], unit="ms", utc=True)
    df["event_hour"] = df["event_datetime"].dt.hour

    # 3. Normalize text columns and extract region from 'place'
    for col in ["event_type", "mag_type", "status"]:
        df[col] = df[col].astype(str).str.strip().str.lower()

    df["place"] = df["place"].astype(str).str.strip()
    df["region"] = df["place"].apply(
        lambda text: text.split(",")[-1].strip() if "," in text else text
    )
    df["region"] = df["region"].replace({"CA": "California"})

    # 4. Vectorized NumPy calculations (no Python loops)
    mag_arr = df["magnitude"].to_numpy()
    depth_arr = np.clip(df["depth_km"].to_numpy(), 0.0, None)

    # Estimate seismic energy in Joules: log10(E) = 4.8 + 1.5 * M
    df["energy_joules"] = np.power(10.0, 4.8 + 1.5 * mag_arr)

    # Categorize magnitude levels with np.select
    df["mag_category"] = np.select(
        [mag_arr < 1.0, (mag_arr >= 1.0) & (mag_arr < 2.5), (mag_arr >= 2.5) & (mag_arr < 4.5)],
        ["micro", "minor", "light"],
        default="moderate_plus",
    )

    # Categorize depth levels with np.select
    df["depth_category"] = np.select(
        [depth_arr < 30.0, (depth_arr >= 30.0) & (depth_arr < 100.0)],
        ["shallow", "intermediate"],
        default="deep",
    )

    return df

def summarize_data(df: pd.DataFrame) -> None:
    # Multi-condition filtering: noticeable shallow earthquakes (mag >= 2.5 and depth < 70 km)
    notable = df[(df["magnitude"] >= 2.5) & (df["depth_km"] < 70.0)]
    print(f"\n=== Notable Shallow Earthquakes (mag >= 2.5 & depth < 70km): {len(notable)} ===")
    print(notable[["id", "magnitude", "depth_km", "region"]].head(5))

    # GroupBy aggregation by region
    region_stats = (
        df.groupby("region", as_index=False)
        .agg(
            total_events=("id", "count"),
            avg_magnitude=("magnitude", "mean"),
            max_magnitude=("magnitude", "max"),
            avg_depth_km=("depth_km", "mean"),
        )
        .sort_values(by="total_events", ascending=False)
    )
    print("\n=== Top 5 Most Active Regions (GroupBy) ===")
    print(region_stats.head(5).to_string(index=False))

    # Pivot table: average magnitude by region (top 5) and review status
    top_regions = region_stats["region"].head(5)
    pivot = pd.pivot_table(
        df[df["region"].isin(top_regions)],
        values="magnitude",
        index="region",
        columns="status",
        aggfunc="mean",
        fill_value=0.0,
    ).round(2)
    print("\n=== Pivot Table: Mean Magnitude by Region & Status ===")
    print(pivot)
    return df

if __name__ == "__main__":
    df = load_validated_data()
    df_clean = clean_data(df)
    print(f"Loaded records: {len(df)}")
    print(f"Cleaned records: {len(df_clean)}")
    print("\n=== Cleaned Data (First 5 Rows) ===")
    print(df_clean[["id", "region", "magnitude", "mag_category", "depth_category", "energy_joules"]].head())

    summarize_data(df_clean)
