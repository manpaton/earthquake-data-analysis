from pathlib import Path

import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from analysis import load_from_db


df = load_from_db()


df = df.dropna(subset=["latitude", "longitude"]).copy()


coordinates = df[["latitude", "longitude"]]


scaler = StandardScaler()
scaled_coordinates = scaler.fit_transform(coordinates)


model = KMeans(n_clusters=2, random_state=42, n_init=10)
df["cluster"] = model.fit_predict(scaled_coordinates)


summary = df.groupby("cluster").agg(
    events=("id", "count"),
    average_magnitude=("magnitude", "mean"),
    average_depth_km=("depth_km", "mean"),
).round(2)

print("Группы землетрясений:")
print(summary)


df.to_csv("earthquakes_with_clusters.csv", index=False)


output_dir = Path("figures")
output_dir.mkdir(exist_ok=True)

plt.figure(figsize=(10, 6))
plt.scatter(
    df["longitude"],
    df["latitude"],
    c=df["cluster"],
    cmap="tab10",
    s=35,
    alpha=0.75,
)

plt.title("Earthquakes grouped by location (K-Means)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.colorbar(label="Cluster")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / "05_earthquake_clusters.png", dpi=150)
plt.show()

print("\nРезультат сохранён в earthquakes_with_clusters.csv")
print("График сохранён в figures/05_earthquake_clusters.png")