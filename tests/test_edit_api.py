import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from class_schedule import webapp


def _record(**overrides):
    base = {
        "Subject": "MATH", "Number": "0903", "Section": "001",
        "Time Slot": "MWF 9:00am", "Duration": 50,
        "Building": "Corley", "Room": "101", "Instructor": "Winn, Janet L.",
    }
    base.update(overrides)
    return base


class EditApiTests(unittest.TestCase):
    """POST /api/edit -- the single edit entry point (see docs/codes.md):
    the browser names one row and a new value, the atomic-class object
    (Class.edit_targets/apply_edit) decides which records that must also
    touch, never the frontend.
    """

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        config_root = Path(self.temporary.name) / "config"
        source = Path(__file__).parents[1] / "config" / "27S"
        shutil.copytree(source, config_root / "27S")
        shutil.rmtree(config_root / "27S" / "template", ignore_errors=True)
        self.config_patch = patch.object(webapp, "CONFIG_DIR", config_root)
        self.config_patch.start()
        self.client = TestClient(webapp.create_app())

    def tearDown(self):
        self.config_patch.stop()
        self.temporary.cleanup()

    def _coreq_records(self):
        # MATH 0903 001 / MATH 1113 001 is a real declared coreq
        # relationship in config/27S/courses.toml.
        return [
            _record(),
            _record(
                Number="1113", Section="001", **{"Time Slot": "T 9:20am"},
                Duration=75,
            ),
        ]

    def _edit_payload(self, *, records=None, class_index=0, record_index=0, **values):
        records = records or self._coreq_records()
        target = records[record_index]
        payload = {
            "package": "27S",
            "records": records,
            "class_index": class_index,
            "record_index": record_index,
            "expected_course_ids": ["MATH 0903-001", "MATH 1113-001"],
            "expected_record": {
                "subject": target["Subject"],
                "number": target["Number"],
                "section": target["Section"],
                "expected_time_slot": target["Time Slot"],
            },
        }
        payload.update(values)
        return payload

    def test_instructor_edit_links_both_coreq_rows(self):
        response = self.client.post("/api/edit", json=self._edit_payload(
            field="instructor",
            value="Growns, Landon C.",
        ))

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["classes"]), 1)
        instructors = {row["Instructor"] for row in body["classes"][0]["sections"]}
        self.assertEqual(instructors, {"Growns, Landon C."})
        coreq_issues = [
            item for item in body["violations"]["hard"]
            if item["rule"] == "coreq_invalid"
        ]
        self.assertEqual(coreq_issues, [])

    def test_view_payload_carries_linked_fields_from_edit_targets(self):
        # linked_fields is the precomputed answer to "would editing this
        # field on one row also touch the other" (Class.edit_targets, see
        # docs/codes.md) -- the web UI reads it instead of re-deriving its
        # own guess. This coreq pair's rows are on disjoint weekdays (MWF
        # vs T), so room/time never link even though instructor always
        # does for CoreqClass.
        response = self.client.post("/api/edit", json=self._edit_payload(
            field="instructor",
            value="Growns, Landon C.",
        ))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["classes"][0]["linked_fields"],
            {"instructor": True, "room": False, "time": False},
        )

    def test_room_edit_does_not_link_across_disjoint_weekdays(self):
        response = self.client.post("/api/edit", json=self._edit_payload(
            record_index=1,
            field="room",
            value={"building": "Rothwell", "room": "221"},
        ))

        self.assertEqual(response.status_code, 200, response.text)
        rooms = {row["Room"] for row in response.json()["classes"][0]["sections"]}
        self.assertEqual(rooms, {"101", "221"})

    def test_unknown_class_index_is_rejected(self):
        response = self.client.post("/api/edit", json=self._edit_payload(
            class_index=5,
            field="instructor",
            value="Growns, Landon C.",
        ))

        self.assertEqual(response.status_code, 400)

    def test_time_edit_on_an_online_row_is_rejected(self):
        records = [{
            "Subject": "MATH", "Number": "1113", "Section": "TC1",
            "Time Slot": "ONLINE", "Duration": None,
            "Building": "", "Room": "", "Instructor": "Staff",
        }]
        response = self.client.post("/api/edit", json={
            "package": "27S", "records": records,
            "class_index": 0,
            "record_index": 0,
            "expected_course_ids": ["MATH 1113-TC1"],
            "expected_record": {
                "subject": "MATH", "number": "1113", "section": "TC1",
                "expected_time_slot": "ONLINE",
            },
            "field": "time",
            "value": {"days": "MWF", "start": "09:00"},
        })

        self.assertEqual(response.status_code, 400)

    def test_changed_atomic_class_identity_is_rejected_without_editing(self):
        payload = self._edit_payload(
            field="instructor", value="Growns, Landon C.",
        )
        payload["expected_course_ids"] = ["MATH 9999-001"]

        response = self.client.post("/api/edit", json=payload)

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("grouping changed", response.json()["detail"])

    def test_changed_target_row_snapshot_is_rejected_without_editing(self):
        payload = self._edit_payload(
            record_index=1, field="time",
            value={"days": "TR", "start": "09:30"},
        )
        payload["expected_record"]["expected_time_slot"] = "TR 9:30am"

        response = self.client.post("/api/edit", json=payload)

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("grouping changed", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
