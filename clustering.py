from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from analysis import load_from_db


#  imabe loading sql lite data from loader 
df = load_from_db()


df = df.dropna(subset=["latitude", "longitude"]).copy()


coordinates = df[["latitude", "longitude"]]


scaler = StandardScaler()
scaled_coordinates = scaler.fit_transform(coordinates)


scores = []
models = []

for number_of_clusters in range(2, 7):
    model = KMeans(
        n_clusters=number_of_clusters,
        random_state=42,
        n_init=10
    )

    labels = model.fit_predict(scaled_coordinates)
    score = silhouette_score(scaled_coordinates, labels)

    scores.append(score)
    models.append(model)

    print(
        f"Групп: {number_of_clusters}, "
        f"оценка silhouette: {score:.3f}"
    )


best_index = scores.index(max(scores))
best_model = models[best_index]
best_number_of_clusters = best_index + 2


df["cluster"] = best_model.labels_

print(f"\nВыбрано групп: {best_number_of_clusters}")


summary = (
    df.groupby("cluster")
    .agg(
        events=("id", "count"),
        average_magnitude=("magnitude", "mean"),
        average_depth_km=("depth_km", "mean"),
    )
    .round(2)
)

print("\nСводка по группам:")
print(summary)


output_dir = Path("figures")
output_dir.mkdir(exist_ok=True)


df.to_csv("earthquakes_with_clusters.csv", index=False)
summary.to_csv("earthquake_cluster_summary.csv")


plt.figure(figsize=(10, 6))
plt.scatter(
    df["longitude"],
    df["latitude"],
    c=df["cluster"],
    cmap="tab10",
    s=35,
    alpha=0.75,
)

plt.title(f"Earthquake Clusters (K-Means, {best_number_of_clusters} groups)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.colorbar(label="Cluster")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / "05_earthquake_clusters.png", dpi=150)
plt.show()

print("\nСохранены файлы:")
print("- earthquakes_with_clusters.csv")
print("- earthquake_cluster_summary.csv")
print("- figures/05_earthquake_clusters.png")