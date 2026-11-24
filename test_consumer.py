import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from consumer import validate_messages, write_valid_records


# An example from raw_data.json, flattened as the Producer sends it.
VALID_RECORD = {
    "id": "ci41363079",
    "magnitude": 1.22,
    "place": "11 km ESE of Pala, CA",
    "time": 1794945044550,
    "event_type": "earthquake",
    "longitude": -116.97683,
    "latitude": 33.313,
    "depth_km": 20.92,
    "updated": 1794945248199,
    "mag_type": "ml",
    "status": "automatic",
    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/ci41363079",
}


def message(record):
    return SimpleNamespace(value=json.dumps(record).encode("utf-8"))


class ConsumerTests(unittest.TestCase):
    def test_three_invalid_earthquakes(self):
        samples = [
            message(VALID_RECORD),
            message(dict(VALID_RECORD, latitude=95)),
            message(dict(VALID_RECORD, magnitude="strong")),
            message(dict(VALID_RECORD, id="")),
        ]

        valid, rejected = validate_messages(samples)

        self.assertEqual(valid.to_dict(orient="records"), [VALID_RECORD])
        self.assertEqual(set(rejected), {1, 2, 3})
        for index, column in enumerate(("latitude", "magnitude", "id"), start=1):
            self.assertTrue(rejected[index][0].startswith(f"{column}:"))
            print(f"Invalid example {index}: {rejected[index][0]}")

    def test_malformed_messages_and_missing_fields(self):
        missing_time = {key: value for key, value in VALID_RECORD.items() if key != "time"}
        samples = [
            SimpleNamespace(value=b"{broken"),
            SimpleNamespace(value=bytes([255])),
            SimpleNamespace(value=None),
            message([]),
            message({}),
            message(missing_time),
            message(dict(VALID_RECORD, time=True)),
            message(VALID_RECORD),
        ]

        valid, rejected = validate_messages(samples)

        self.assertEqual(valid.index.tolist(), [7])
        self.assertEqual(set(rejected), set(range(7)))
        self.assertTrue(rejected[5][0].startswith("time:"))
        self.assertTrue(rejected[6][0].startswith("time:"))

    def test_negative_depth_and_optional_fields_in_export(self):
        record = dict(VALID_RECORD, depth_km=-0.13, updated=None, place=None)
        del record["status"]
        valid, rejected = validate_messages([message(record)])

        self.assertEqual(rejected, {})
        with tempfile.NamedTemporaryFile(dir=Path(__file__).parent, delete=False) as file:
            path = Path(file.name)
        try:
            write_valid_records(valid, path)
            exported = json.loads(path.read_text(encoding="utf-8"))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(exported, [dict(record, status=None)])


if __name__ == "__main__":
    unittest.main()
