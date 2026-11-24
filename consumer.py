import argparse
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic

import pandas as pd
import pandera.pandas as pa
from kafka import KafkaConsumer, TopicPartition
from kafka.errors import KafkaError


BOOTSTRAP_SERVERS = "127.0.0.1:19092"
TOPIC = "earthquakes-demo"
IDLE_TIMEOUT_SECONDS = 15
OUTPUT_PATH = Path(__file__).with_name("validated_earthquakes.json")


def is_finite_number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def check(rule, description):
    return pa.Check(rule, element_wise=True, error=description)


TEXT = check(lambda value: isinstance(value, str), "must be text")
EPOCH_MS = check(lambda value: type(value) is int, "must be integer Unix milliseconds")
NUMBER = check(is_finite_number, "must be a finite number")

EARTHQUAKE_SCHEMA = pa.DataFrameSchema(
    {
        "id": pa.Column(
            checks=check(
                lambda value: isinstance(value, str) and bool(value.strip()),
                "must be non-empty text",
            )
        ),
        "magnitude": pa.Column(checks=NUMBER),
        "place": pa.Column(checks=TEXT, nullable=True),
        "time": pa.Column(checks=EPOCH_MS),
        "event_type": pa.Column(
            checks=check(lambda value: value == "earthquake", "must be earthquake")
        ),
        "longitude": pa.Column(
            checks=check(
                lambda value: is_finite_number(value) and -180 <= value <= 180,
                "must be between -180 and 180",
            )
        ),
        "latitude": pa.Column(
            checks=check(
                lambda value: is_finite_number(value) and -90 <= value <= 90,
                "must be between -90 and 90",
            )
        ),
        # USGS records can have negative depths, including in our input file.
        "depth_km": pa.Column(checks=NUMBER),
        "updated": pa.Column(checks=EPOCH_MS, nullable=True),
        "mag_type": pa.Column(checks=TEXT, nullable=True),
        "status": pa.Column(checks=TEXT, nullable=True),
        "url": pa.Column(checks=TEXT, nullable=True),
    }
)


def read_topic():
    """Read the records already in Kafka when this run starts."""
    with KafkaConsumer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=None,
        enable_auto_commit=False,
        allow_auto_create_topics=False,
        bootstrap_timeout_ms=5000,
    ) as consumer:
        partition_ids = consumer.partitions_for_topic(TOPIC)
        if not partition_ids:
            raise RuntimeError(f"No partitions found for topic {TOPIC!r}.")

        partitions = [TopicPartition(TOPIC, number) for number in sorted(partition_ids)]
        starts = consumer.beginning_offsets(partitions, timeout_ms=5000)
        ends = consumer.end_offsets(partitions, timeout_ms=5000)
        positions = {
            partition: starts[partition]
            for partition in partitions
            if starts[partition] < ends[partition]
        }
        consumer.assign(list(positions))
        for partition, start in positions.items():
            consumer.seek(partition, start)

        messages = []
        deadline = monotonic() + IDLE_TIMEOUT_SECONDS
        while positions:
            for partition, batch in consumer.poll(timeout_ms=1000).items():
                messages.extend(
                    message for message in batch if message.offset < ends[partition]
                )

            for partition, previous in list(positions.items()):
                position = consumer.position(partition, timeout_ms=1000)
                if position > previous:
                    deadline = monotonic() + IDLE_TIMEOUT_SECONDS
                if position >= ends[partition]:
                    consumer.pause(partition)
                    del positions[partition]
                else:
                    positions[partition] = position

            if positions and monotonic() >= deadline:
                raise RuntimeError("Kafka stopped returning records before the expected end offsets.")

    return messages


def reject_json_constant(value):
    raise ValueError(f"{value} is not a JSON number")


def decode_record(value):
    """Turn a Kafka message value into one earthquake dictionary."""
    if value is None:
        raise ValueError("message has no value")
    record = json.loads(value.decode("utf-8"), parse_constant=reject_json_constant)
    if not isinstance(record, dict):
        raise ValueError("expected a JSON object")
    return record


def validate_records(records):
    """Return the valid DataFrame and errors keyed by original message index."""
    # Keep JSON types so checks can distinguish numbers, strings, and booleans.
    columns = list(EARTHQUAKE_SCHEMA.columns)
    rows = [[record.get(column) for column in columns] for record in records.values()]
    frame = pd.DataFrame(rows, index=list(records), columns=columns, dtype=object)
    errors = {}
    try:
        EARTHQUAKE_SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for failure in exc.failure_cases.itertuples(index=False):
            if pd.isna(failure.index):
                raise
            errors.setdefault(failure.index, []).append(f"{failure.column}: {failure.check}")

    return frame.drop(index=list(errors)), errors


def validate_messages(messages):
    records = {}
    rejected = {}
    for index, message in enumerate(messages):
        try:
            records[index] = decode_record(message.value)
        except ValueError as exc:
            rejected[index] = [str(exc)]

    valid, schema_errors = validate_records(records)
    rejected.update(schema_errors)
    return valid, rejected


def write_valid_records(frame, path):
    rows = frame.to_dict(orient="records")
    file = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    temporary_path = Path(file.name)
    try:
        with file:
            json.dump(rows, file, indent=2, allow_nan=False)
            file.write("\n")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Validate earthquake records from Kafka.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Path for the validated JSON file.")
    args = parser.parse_args()

    try:
        messages = read_topic()
        if not messages:
            raise RuntimeError(f"Topic {TOPIC!r} has no messages to validate.")

        valid, rejected = validate_messages(messages)
        for index, reasons in sorted(rejected.items()):
            message = messages[index]
            print(
                f"Rejected partition {message.partition}, offset {message.offset}: "
                f"{'; '.join(reasons)}"
            )

        write_valid_records(valid, args.output)
    except (KafkaError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Consumer failed: {exc}\n")

    print(f"Received: {len(messages)} | Valid: {len(valid)} | Rejected: {len(rejected)}")
    print(f"Validated JSON: {args.output}")


if __name__ == "__main__":
    main()