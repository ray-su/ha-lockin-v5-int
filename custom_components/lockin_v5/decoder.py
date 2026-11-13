"""Pure, exact-model decoder. Never infer physical door position or identities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

ACTIONS = {
    1: ("locked", "Locked"), 2: ("unlocked", "Unlocked"),
    3: ("handle_locked", "Locked using the outside handle"),
    4: ("interior_lock_engaged", "Interior lock engaged"),
    5: ("interior_lock_released", "Interior lock released"),
    6: ("child_lock_enabled", "Child lock enabled"),
    7: ("child_lock_disabled", "Child lock disabled"),
    8: ("away_mode_enabled", "Away mode enabled"),
    9: ("away_mode_disabled", "Away mode disabled"),
}
METHODS = {1: "Mobile app", 2: "Fingerprint", 3: "PIN", 4: "NFC", 5: "Face recognition", 6: "Finger vein", 7: "Palm recognition", 8: "Physical key", 9: "One-time PIN", 10: "Scheduled PIN", 11: "HomeKit", 12: "Duress", 13: "Two-factor verification", 14: "Thumbturn", 15: "Manual operation", 16: "Automatic"}
POSITIONS = {1: "Inside", 2: "Outside", 3: "Not reported"}
BATTERY_PRESENCE = {0: "Neither battery installed", 1: "Large battery installed", 2: "Small battery installed", 3: "Both batteries installed", 4: "USB connected; no batteries", 5: "USB and large battery connected", 6: "USB and small battery connected", 7: "USB and both batteries connected"}


def integer(value: Any) -> int | None:
    """Reject booleans, fractional values and surprising string coercion."""
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return None


def timestamp(value: Any) -> datetime | None:
    value = integer(value)
    if value is None or not 1577836800 <= value <= 4102444800:
        return None
    return datetime.fromtimestamp(value, timezone.utc)


def parse_iso(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class DecodedEvent:
    category: str
    event_type: str
    summary: str
    occurred_at: datetime
    time_source: str
    source: str
    fingerprint: str
    attributes: dict[str, Any]


class Decoder:
    def __init__(self, specification: dict):
        self.properties = {(s["iid"], p["iid"]): p for s in specification["services"] for p in s.get("properties", [])}

    def event(self, payload: dict, received_at: datetime) -> DecodedEvent | None:
        if not isinstance(payload, dict):
            return None
        siid, eiid = integer(payload.get("siid")), integer(payload.get("eiid"))
        args = payload.get("arguments")
        if not isinstance(args, list):
            return None
        values: dict[int, Any] = {}
        for arg in args:
            if not isinstance(arg, dict) or integer(arg.get("piid")) is None or "value" not in arg:
                return None
            piid = integer(arg["piid"])
            if piid in values:
                return None
            values[piid] = arg["value"]
        source = f"{siid}.{eiid}"
        attrs: dict[str, Any] = {}
        category = kind = summary = ""
        time_id = {2: 5, 5: 1, 7: 10}.get(siid)
        occurred = timestamp(values.get(time_id)) if time_id else None
        # Lock/security events must have a usable device time: no guessed new unlocks.
        if siid in (2, 5, 7) and (occurred is None or occurred > received_at + timedelta(minutes=5)):
            return None
        time_source = "device" if occurred else "received"
        occurred = occurred or received_at
        if (siid, eiid) == (2, 1020):
            action = integer(values.get(3))
            if action is None:
                return None
            method, position = integer(values.get(2)), integer(values.get(1))
            kind, action_name = ACTIONS.get(action, ("unrecognized", f"Unrecognized lock action ({action})"))
            method_name = METHODS.get(method, "Not reported" if method is None else f"Unrecognized method ({method})")
            position_name = POSITIONS.get(position, "Not reported" if position is None else f"Unrecognized position ({position})")
            category = "lock"
            summary = f"{action_name} — {method_name.lower()}"
            if position_name != "Not reported":
                summary += f" — {position_name.lower()}"
            attrs = {"action": action_name, "action_code": action, "method": method_name, "method_code": method, "side": position_name, "side_code": position}
        elif (siid, eiid) == (2, 1007):
            code = integer(values.get(6))
            if code is None:
                return None
            names = {v["value"]: v["description"].strip() for v in self.properties[(2, 6)]["value-list"]}
            friendly = {23: "Door left open too long", 24: "Door ajar", 25: "Door forced open", 10: "Locking failed", 34: "Low battery: camera and door screen suspended"}
            summary = friendly.get(code, names.get(code, f"Unrecognized warning ({code})").capitalize())
            category, kind, attrs = "warning", "warning", {"warning_code": code}
        elif (siid, eiid) in ((5, 1006), (7, 1)):
            category, kind, summary = "doorbell", "pressed", "Doorbell pressed"
            source = "doorbell"  # Both services can report the same physical press.
        elif (siid, eiid) == (7, 2):
            category, kind, summary = "warning", "warning", "Video doorbell forcibly removed"
        elif (siid, eiid) == (10, 1):
            category, kind, summary = "warning", "warning", "Low battery reported"
        elif (siid, eiid) in ((7, 3), (7, 4), (11, 1), (11, 2)):
            kind, summary = {(7, 3): ("passed_by", "Someone appeared at the door"), (7, 4): ("at_door", "Someone at the door"), (11, 1): ("departed", "Visitor departed"), (11, 2): ("ultrasonic_activity", "Frequent ultrasonic activity")}[siid, eiid]
            category = "visitor"
        elif (siid, eiid) in ((11, 3), (12, 1023)):
            # Firmware debug strings can contain identifiers/face data. Do not persist them.
            category, kind, summary = "diagnostic", "unmapped", "Unmapped firmware diagnostic received"
        else:
            return None
        # Never store operation/user IDs or cloud video IDs in entities or dedup state.
        identity = [source, occurred.isoformat() if time_source == "device" else None, kind, attrs]
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        # Presentation only: keep these out of the persisted dedup identity so
        # an upgrade cannot turn an already-observed report into a new event.
        if category == "lock":
            app_description = None
            if (action, method, position) == (1, 15, 3):
                app_description = "Door closed report"
            elif (action, method, position) == (2, 15, 1):
                app_description = "Inside-handle opening"
            elif action == 2 and position == 2:
                app_description = {2: "Fingerprint unlock", 5: "Face unlock", 7: "Palm recognition unlock"}.get(method)
            if app_description:
                attrs = {**attrs, "app_description": app_description}
        return DecodedEvent(category, kind, summary, occurred, time_source, source, fingerprint, attrs)

    def property(self, payload: dict, received_at: datetime) -> tuple[str, Any, dict] | None:
        if not isinstance(payload, dict) or payload.get("code", 0) != 0:
            return None
        pair = (integer(payload.get("siid")), integer(payload.get("piid")))
        raw = integer(payload.get("value"))
        if raw is None:
            return None
        attrs = {"raw_code": raw, "source": f"property:{pair[0]}.{pair[1]}"}
        if pair == (3, 1021):
            labels = {16: "Locked", 20: "Locked", 24: "Locked", 28: "Locked", 32: "Unlocked", 36: "Unlocked", 40: "Unlocked", 44: "Unlocked", 48: "Door left open too long", 52: "Door left open too long", 56: "Door left open too long", 60: "Door left open too long", 64: "Door ajar", 68: "Door ajar", 72: "Door ajar", 76: "Door ajar"}
            return "door_report", labels.get(raw, f"Unrecognized door report ({raw})"), attrs
        if pair in ((4, 1003), (10, 1)) and 0 <= raw <= 100:
            return ("battery_a" if pair[0] == 4 else "battery_b"), raw, attrs
        if pair == (4, 1034):
            return "battery_presence", BATTERY_PRESENCE.get(raw, f"Unrecognized battery status ({raw})"), attrs
        if pair == (7, 2) and raw in (0, 1):
            return "video_status", ("Offline" if raw == 0 else "Online"), attrs
        if pair == (11, 15) and (at := timestamp(raw)) and at <= received_at + timedelta(minutes=5):
            return "battery_updated", at.isoformat(), attrs
        return None


class LockState:
    """Last observations, not an asserted live security/door state."""
    def __init__(self, decoder: Decoder, saved: dict | None = None):
        saved = saved or {}
        self.decoder = decoder
        self.fields: dict[str, dict] = saved.get("fields", {})
        self.watermarks: dict[str, str] = saved.get("watermarks", {})
        self.seen: list[str] = saved.get("seen", [])[-128:]
        self.untimed_seen: dict[str, datetime] = {}

    def snapshot(self) -> dict:
        return {"fields": self.fields, "watermarks": self.watermarks, "seen": self.seen[-128:]}

    def put(self, key: str, value: Any, at: datetime, **attrs) -> None:
        previous = self.fields.get(key, {})
        if (old_time := parse_iso(previous.get("observed_at"))) and at < old_time:
            return
        self.fields[key] = {"value": value, "observed_at": at.isoformat(), **attrs}

    def apply_event(self, payload: dict, received_at: datetime) -> DecodedEvent | None:
        event = self.decoder.event(payload, received_at)
        if event is None:
            return None
        if event.time_source == "device":
            if event.fingerprint in self.seen:
                return None
            previous = parse_iso(self.watermarks.get(event.source))
            if previous and event.occurred_at < previous:
                return None
            self.watermarks[event.source] = event.occurred_at.isoformat()
            self.seen = (self.seen + [event.fingerprint])[-128:]
        else:
            previous = self.untimed_seen.get(event.fingerprint)
            if previous and received_at - previous < timedelta(seconds=2):
                return None
            self.untimed_seen[event.fingerprint] = received_at
        attrs = {**event.attributes, "source": f"event:{event.source}", "time_source": event.time_source}
        self.put("last_received", received_at.isoformat(), received_at)
        if event.category == "lock":
            self.put("lock_activity", event.summary, event.occurred_at, **attrs)
            self.put("last_operation", attrs["action"], event.occurred_at, **attrs)
            self.put("last_method", attrs["method"], event.occurred_at)
            self.put("last_side", attrs["side"], event.occurred_at)
            self.put("last_operation_time", event.occurred_at.isoformat(), event.occurred_at)
            if event.event_type in ("locked", "unlocked"):
                self.put("reported_lock_state", attrs["action"], event.occurred_at, **attrs)
            if event.event_type == "unlocked":
                self.put("last_unlock_time", event.occurred_at.isoformat(), event.occurred_at)
        elif event.category == "doorbell":
            self.put("last_doorbell_time", event.occurred_at.isoformat(), event.occurred_at, **attrs)
        else:
            self.put(f"last_{event.category}", event.summary, event.occurred_at, **attrs)
        return event

    def apply_property(self, payload: dict, received_at: datetime) -> bool:
        decoded = self.decoder.property(payload, received_at)
        if decoded is None:
            return False
        key, value, attrs = decoded
        self.put(key, value, received_at, **attrs)
        self.put("last_received", received_at.isoformat(), received_at)
        return True
