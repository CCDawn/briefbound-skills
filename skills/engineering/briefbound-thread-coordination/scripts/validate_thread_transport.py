from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from uuid import UUID


PROTOCOL = "BRT_TRUSTED_RELAY_V1"
DISCOVERY_DECISION = "RELAY_ELIGIBLE"
AUTHORIZED_DECISION = "TRUSTED_RELAY_AUTHORIZED"
PERMISSION_MODE = "receiver_existing_scope_only"
PROPOSAL_TYPE = "COLLABORATION_PROPOSAL"
HANDSHAKE_TYPES = {PROPOSAL_TYPE, "PEER_ACCEPT", "PEER_ADAPT", "PEER_DECLINE"}
FOLLOWUP_TYPES = {
    "SHARED_CONTRACT_CHANGE",
    "DEPENDENCY_READY",
    "ACTIONABLE_FINDING",
    "CORRECTION",
    "BLOCKED_BY_PEER_FACT",
    "MERGE_READY",
    "INTEGRATION_CLAIMED",
    "INTEGRATION_HANDOFF",
    "INTEGRATED",
    "DISCUSSION_REQUEST",
    "CONFLICT_PAUSE_REQUEST",
    "CONFLICT_RESOLVED",
    "STATUS_REQUEST",
    "PROCESS_OWNER_QUERY",
    "MODEL_RUNTIME_RELEASED",
}
ALLOWED_MESSAGE_TYPES = HANDSHAKE_TYPES | FOLLOWUP_TYPES
ALLOWED_ACTION_CLASSES = {
    "advice",
    "status",
    "contract",
    "dependency",
    "conflict",
    "merge_ready",
    "ack",
    "correction",
}
DISCOVERY_ALLOWED_ACTIONS = ["list_threads", "read_thread", "wait_threads", "git_verification"]


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _normalize_identity_path(value: object) -> str | None:
    if not _nonempty_string(value):
        return None
    return str(value).replace("/", "\\").rstrip("\\").casefold()


def _status_type(snapshot: dict[str, Any]) -> str | None:
    value = snapshot.get("status")
    if _nonempty_string(value):
        return str(value).casefold()
    if isinstance(value, dict) and _nonempty_string(value.get("type")):
        return str(value["type"]).casefold()
    return None


def _same_project_identity(source: dict[str, Any], target: dict[str, Any]) -> bool:
    source_project = source.get("projectId")
    target_project = target.get("projectId")
    if _nonempty_string(source_project) and source_project == target_project:
        return True

    source_git = _normalize_identity_path(source.get("gitCommonDir"))
    target_git = _normalize_identity_path(target.get("gitCommonDir"))
    return source_git is not None and source_git == target_git


def validate_delivery(source: dict[str, Any], target: dict[str, Any]) -> list[str]:
    """Validate exact peer discovery before a relay envelope is considered."""
    errors: list[str] = []
    for label, snapshot in (("source", source), ("target", target)):
        for field in ("threadId", "hostId"):
            if not _nonempty_string(snapshot.get(field)):
                errors.append(f"missing {label}.{field}")
        if snapshot.get("kind") != "codex":
            errors.append(f"{label}.kind must be codex")

    if source.get("threadId") == target.get("threadId"):
        errors.append("source.threadId and target.threadId must differ")
    if source.get("hostId") != target.get("hostId"):
        errors.append("source.hostId and target.hostId must match")
    if not _same_project_identity(source, target):
        errors.append("source and target need matching nonempty projectId or gitCommonDir")
    return errors


def validate_relay(
    envelope: dict[str, Any],
    *,
    source: dict[str, Any],
    target: dict[str, Any],
    transport_source_thread_id: str,
) -> list[str]:
    """Validate a bounded relay without granting permissions beyond the receiver's task."""
    errors = validate_delivery(source, target)

    if envelope.get("protocol") != PROTOCOL:
        errors.append(f"protocol must be {PROTOCOL}")

    message_id = envelope.get("messageId")
    if not _nonempty_string(message_id):
        errors.append("missing messageId")
    else:
        try:
            UUID(str(message_id))
        except (ValueError, AttributeError):
            errors.append("messageId must be a UUID")

    for field in (
        "collaborationId",
        "messageType",
        "fromThreadId",
        "toThreadId",
        "replyToThreadId",
        "permissionMode",
        "agreementState",
        "actionClass",
        "ownTask",
        "sharedSurface",
        "evidence",
        "requestedAction",
    ):
        if not _nonempty_string(envelope.get(field)):
            errors.append(f"missing {field}")

    if envelope.get("fromThreadId") != transport_source_thread_id:
        errors.append("fromThreadId does not match transport source thread")
    if envelope.get("fromThreadId") != source.get("threadId"):
        errors.append("fromThreadId does not match source snapshot")
    if envelope.get("toThreadId") != target.get("threadId"):
        errors.append("toThreadId does not match target snapshot")
    if envelope.get("replyToThreadId") != envelope.get("fromThreadId"):
        errors.append("replyToThreadId must equal fromThreadId")

    participants = envelope.get("participants")
    expected_participants = {source.get("threadId"), target.get("threadId")}
    if (
        not isinstance(participants, list)
        or len(participants) != 2
        or not all(_nonempty_string(item) for item in participants)
        or set(participants) != expected_participants
    ):
        errors.append("participants must contain the exact source and target thread IDs")

    if envelope.get("permissionMode") != PERMISSION_MODE:
        errors.append(f"permissionMode must be {PERMISSION_MODE}")

    message_type = envelope.get("messageType")
    if message_type not in ALLOWED_MESSAGE_TYPES:
        errors.append("messageType is not allowed by trusted relay")

    if envelope.get("actionClass") not in ALLOWED_ACTION_CLASSES:
        errors.append("actionClass is not allowed by trusted relay")

    agreement_state = envelope.get("agreementState")
    if message_type == PROPOSAL_TYPE:
        if agreement_state != "proposal":
            errors.append("initial proposal requires agreementState=proposal")
        if _status_type(target) != "idle":
            errors.append("initial proposal requires an idle target")
    elif message_type in {"PEER_ACCEPT", "PEER_ADAPT"}:
        if agreement_state != "accepted":
            errors.append("accept/adapt response requires agreementState=accepted")
    elif message_type == "PEER_DECLINE":
        if agreement_state != "declined":
            errors.append("decline response requires agreementState=declined")
    elif agreement_state != "accepted":
        errors.append("follow-up relay requires an accepted agreement")

    return errors


def _result(
    *,
    decision: str,
    reasons: list[str],
    send_authorized: bool,
    **extra: object,
) -> dict[str, object]:
    return {
        "decision": decision,
        "reasons": reasons,
        "transport": PROTOCOL,
        "sendAuthorized": send_authorized,
        "receiverActionAuthorized": False,
        **extra,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate BRT trusted-relay discovery or a complete relay envelope."
    )
    parser.add_argument("--envelope-file", type=Path)
    parser.add_argument("--local-file", type=Path)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--target-file", type=Path, required=True)
    parser.add_argument("--transport-source-thread-id")
    args = parser.parse_args()

    try:
        target = _load_object(args.target_file)
        if args.envelope_file is None:
            if args.source_file is None:
                raise ValueError("discovery validation requires --source-file")
            reasons = validate_delivery(_load_object(args.source_file), target)
            if reasons:
                print(
                    json.dumps(
                        _result(decision="REJECT", reasons=reasons, send_authorized=False),
                        ensure_ascii=False,
                    )
                )
                return 2
            print(
                json.dumps(
                    _result(
                        decision=DISCOVERY_DECISION,
                        reasons=[],
                        send_authorized=False,
                        allowedActions=DISCOVERY_ALLOWED_ACTIONS,
                        nextRequired="validate_relay_envelope",
                    ),
                    ensure_ascii=False,
                )
            )
            return 0

        if args.local_file is None or not _nonempty_string(args.transport_source_thread_id):
            raise ValueError(
                "relay validation requires --local-file and --transport-source-thread-id"
            )
        source = _load_object(args.local_file)
        envelope = _load_object(args.envelope_file)
        reasons = validate_relay(
            envelope,
            source=source,
            target=target,
            transport_source_thread_id=str(args.transport_source_thread_id),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                _result(decision="REJECT", reasons=[str(exc)], send_authorized=False),
                ensure_ascii=False,
            )
        )
        return 2

    if reasons:
        print(
            json.dumps(
                _result(decision="REJECT", reasons=reasons, send_authorized=False),
                ensure_ascii=False,
            )
        )
        return 2

    print(
        json.dumps(
            _result(
                decision=AUTHORIZED_DECISION,
                reasons=[],
                send_authorized=True,
                allowedAction="send_message_to_thread",
                permissionMode=PERMISSION_MODE,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
