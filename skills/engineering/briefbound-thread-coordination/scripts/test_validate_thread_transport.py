from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


SCRIPT_PATH = Path(__file__).with_name("validate_thread_transport.py")
SPEC = importlib.util.spec_from_file_location("validate_thread_transport", SCRIPT_PATH)
transport = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(transport)


def snapshot(
    thread_id: str,
    *,
    project_id: str | None = "project-a",
    git_common_dir: str | None = None,
    status: str = "idle",
) -> dict[str, object]:
    return {
        "threadId": thread_id,
        "hostId": "local",
        "projectId": project_id,
        "gitCommonDir": git_common_dir,
        "kind": "codex",
        "status": status,
    }


def envelope(message_type: str = "COLLABORATION_PROPOSAL") -> dict[str, object]:
    return {
        "protocol": "BRT_TRUSTED_RELAY_V1",
        "messageId": str(uuid4()),
        "collaborationId": "collab-1",
        "messageType": message_type,
        "fromThreadId": "source-thread",
        "toThreadId": "target-thread",
        "replyToThreadId": "source-thread",
        "participants": ["source-thread", "target-thread"],
        "permissionMode": "receiver_existing_scope_only",
        "agreementState": "proposal" if message_type == "COLLABORATION_PROPOSAL" else "accepted",
        "actionClass": "advice",
        "ownTask": "source task",
        "sharedSurface": "shared API contract",
        "evidence": "fresh Git and thread evidence",
        "requestedAction": "review the proposed boundary and reply",
    }


class TrustedRelayTests(unittest.TestCase):
    def test_accepts_matching_nonempty_project_id(self) -> None:
        self.assertEqual(
            transport.validate_delivery(snapshot("source-thread"), snapshot("target-thread")),
            [],
        )

    def test_accepts_matching_git_common_dir_when_managed_worktree_has_no_project_id(self) -> None:
        source = snapshot(
            "source-thread",
            project_id=None,
            git_common_dir=r"C:\repo\.git",
        )
        target = snapshot(
            "target-thread",
            project_id=None,
            git_common_dir=r"c:\REPO\.git",
        )
        self.assertEqual(transport.validate_delivery(source, target), [])

    def test_authorizes_valid_idle_proposal(self) -> None:
        errors = transport.validate_relay(
            envelope(),
            source=snapshot("source-thread"),
            target=snapshot("target-thread"),
            transport_source_thread_id="source-thread",
        )
        self.assertEqual(errors, [])

    def test_rejects_spoofed_source_id(self) -> None:
        errors = transport.validate_relay(
            envelope(),
            source=snapshot("source-thread"),
            target=snapshot("target-thread"),
            transport_source_thread_id="different-thread",
        )
        self.assertIn("fromThreadId does not match transport source thread", errors)

    def test_rejects_initial_proposal_to_active_target(self) -> None:
        errors = transport.validate_relay(
            envelope(),
            source=snapshot("source-thread"),
            target=snapshot("target-thread", status="active"),
            transport_source_thread_id="source-thread",
        )
        self.assertIn("initial proposal requires an idle target", errors)

    def test_rejects_message_that_claims_new_permissions(self) -> None:
        message = envelope()
        message["permissionMode"] = "grant_new_permissions"
        errors = transport.validate_relay(
            message,
            source=snapshot("source-thread"),
            target=snapshot("target-thread"),
            transport_source_thread_id="source-thread",
        )
        self.assertIn("permissionMode must be receiver_existing_scope_only", errors)

    def test_rejects_followup_without_accepted_agreement(self) -> None:
        message = envelope("ACTIONABLE_FINDING")
        message["agreementState"] = "proposal"
        errors = transport.validate_relay(
            message,
            source=snapshot("source-thread"),
            target=snapshot("target-thread"),
            transport_source_thread_id="source-thread",
        )
        self.assertIn("follow-up relay requires an accepted agreement", errors)

    def test_rejects_malformed_participants_without_crashing(self) -> None:
        message = envelope()
        message["participants"] = [{"thread": "source-thread"}, "target-thread"]
        errors = transport.validate_relay(
            message,
            source=snapshot("source-thread"),
            target=snapshot("target-thread"),
            transport_source_thread_id="source-thread",
        )
        self.assertIn("participants must contain the exact source and target thread IDs", errors)

    def test_cli_authorizes_complete_relay_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_file = root / "source.json"
            target_file = root / "target.json"
            envelope_file = root / "envelope.json"
            source_file.write_text(json.dumps(snapshot("source-thread")), encoding="utf-8")
            target_file.write_text(json.dumps(snapshot("target-thread")), encoding="utf-8")
            envelope_file.write_text(json.dumps(envelope()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--local-file",
                    str(source_file),
                    "--target-file",
                    str(target_file),
                    "--envelope-file",
                    str(envelope_file),
                    "--transport-source-thread-id",
                    "source-thread",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["decision"], "TRUSTED_RELAY_AUTHORIZED")
            self.assertTrue(payload["sendAuthorized"])
            self.assertFalse(payload["receiverActionAuthorized"])


if __name__ == "__main__":
    unittest.main()
