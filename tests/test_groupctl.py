import tempfile
import unittest
from pathlib import Path

from groupctl_pkg.config import GroupPaths
from groupctl_pkg.events import (
    EventValidationError,
    build_event,
    generate_event_id,
    next_change_id,
    validate_event,
    write_immutable_event,
)


class TestGroupctlContract(unittest.TestCase):
    def test_generate_event_id_format(self):
        ev_id = generate_event_id("P17", timestamp_compact="20261016T021530Z")
        self.assertTrue(ev_id.startswith("E-20261016T021530Z-P17-"))
        self.assertEqual(len(ev_id.split("-")), 4)

    def test_validate_all_supported_events(self):
        ev = build_event(
            event_type="change_published",
            group_id="G-12",
            person_id="P17",
            payload={
                "change_id": "C-17",
                "branch": "people/P17/parser",
                "commit": "abc1234",
                "summary": "Implemented nested parser support.",
                "files_changed": ["src/parser.py"],
                "interface_changes": ["Parser.parse returns ParseResult"],
                "tests_run": ["unittest"],
                "known_issues": [],
                "proposed_for_integration": True,
            },
        )
        validate_event(ev)
        self.assertEqual(ev["protocol_version"], "0.1")

    def test_reject_invalid_review_verdict(self):
        with self.assertRaises(EventValidationError):
            build_event(
                event_type="review",
                group_id="G-12",
                person_id="P22",
                payload={
                    "change_id": "C-17",
                    "verdict": "looks_good_to_me",
                    "summary": "Invalid verdict enum",
                    "issues": [],
                    "tests_run": [],
                },
            )

    def test_immutable_event_file_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = GroupPaths(Path(tmpdir))
            ev = build_event(
                event_type="finding",
                group_id="G-12",
                person_id="P31",
                event_id="E-20261016T021530Z-P31-1111",
                payload={
                    "summary": "Found edge case",
                    "evidence": ["test_nested_section_parsing"],
                },
            )
            write_immutable_event(paths, ev)
            with self.assertRaises(EventValidationError):
                write_immutable_event(paths, ev)

    def test_next_change_id_increment(self):
        events = [{"event_type": "change_published", "change_id": "C-17"}]
        self.assertEqual(next_change_id(events, "P17"), "C-17-2")
        self.assertEqual(next_change_id(events, "P22"), "C-22")


if __name__ == "__main__":
    unittest.main()
