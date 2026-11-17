import json
import os
from pathlib import Path

from kafka import KafkaProducer

from api_client import RAW_DATA_PATH, make_record


def main():
    path = Path(os.getenv("RAW_DATA_PATH", RAW_DATA_PATH))
    with path.open(encoding="utf-8") as file:
        events = json.load(file)["features"]

    broker = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
    topic = os.getenv("KAFKA_TOPIC", "earthquakes")
    producer = KafkaProducer(bootstrap_servers=broker, acks="all")

    try:
        for event in events:
            record = make_record(event)
            key = record["id"].encode("utf-8")
            message = json.dumps(record, ensure_ascii=False).encode("utf-8")
            producer.send(topic, key=key, value=message).get(timeout=15)
        print("Sent messages:", len(events))
    finally:
        producer.close()


if __name__ == "__main__":
    main()

