import json
from pathlib import Path

import requests


USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
RAW_DATA_PATH = Path(__file__).with_name("raw_data.json")


def make_record(event):
    properties = event["properties"]
    longitude, latitude, depth_km = event["geometry"]["coordinates"]

    return {
        "id": event["id"],
        "magnitude": properties["mag"],
        "place": properties["place"],
        "time": properties["time"],  # Unix timestamp in milliseconds
        "event_type": properties["type"],
        "longitude": longitude,
        "latitude": latitude,
        "depth_km": depth_km,
        # Keep the same fields as the messages already in Kafka.
        "updated": properties.get("updated"),
        "mag_type": properties.get("magType"),
        "status": properties.get("status"),
        "url": properties.get("url"),
    }


def main():
    params = {
        "format": "geojson",
        "limit": 200,
        "orderby": "time",
        "eventtype": "earthquake",
    }
    response = requests.get(USGS_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if len(data["features"]) < params["limit"]:
        raise ValueError("USGS returned fewer than 200 earthquakes")

    with RAW_DATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print("Saved earthquakes:", len(data["features"]))


if __name__ == "__main__":
    main()
