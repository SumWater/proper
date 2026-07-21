import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from failure_memory.boundary import (  # noqa: E402
    contains_injection_metadata,
    sanitize_observation_payload,
)


class BoundaryTests(unittest.TestCase):
    def test_sanitizer_removes_injection_metadata_only(self) -> None:
        raw = {
            "instruction": "update account",
            "transcript": [
                {
                    "tool_name": "update_account",
                    "args": {"id": "a1"},
                    "output": None,
                    "error": {
                        "code": "authz_denied",
                        "message": "denied",
                        "details": {
                            "required_role": "admin",
                            "faults": [
                                {
                                    "fault_type": "authz",
                                    "payload": {"recoverability": "transient_denial"},
                                }
                            ],
                        },
                    },
                }
            ],
            "last_error": {
                "code": "authz_denied",
                "message": "denied",
                "details": {"required_role": "admin", "faults": [{"fault_type": "authz"}]},
            },
        }
        cleaned = sanitize_observation_payload(raw)
        self.assertFalse(contains_injection_metadata(cleaned))
        self.assertEqual(
            cleaned["last_error"]["details"],
            {"required_role": "admin"},
        )
        self.assertEqual(cleaned["transcript"][0]["args"], {"id": "a1"})
        self.assertTrue(contains_injection_metadata(raw))

    def test_sanitizer_removes_adversarial_original_error(self) -> None:
        raw = {
            "transcript": [],
            "last_error": {
                "code": "ambiguous_error",
                "message": "unclear",
                "details": {"original_error_code": "timeout"},
            },
        }
        cleaned = sanitize_observation_payload(raw)
        self.assertEqual(cleaned["last_error"]["details"], {})


if __name__ == "__main__":
    unittest.main()

