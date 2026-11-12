"""Constants for the single supported lock. No actuator platforms."""
DOMAIN = "lockin_v5"
MODEL = "loock.lock.v2203"
NAME = "Lockin V5 Max INT"
PLATFORMS = ["sensor", "event"]
VERSION = "0.1.1"
REGIONS = {"sg": "Singapore / Australia", "cn": "China", "de": "Europe", "i2": "India", "ru": "Russia", "us": "United States"}
# Model-specific read-only properties. Do not poll action-only properties.
READ_PROPERTIES = [(3, 1021), (4, 1003), (4, 1034), (7, 2), (10, 1), (11, 15)]
EVENT_TYPES = {
    "lock": ["locked", "unlocked", "handle_locked", "interior_lock_engaged", "interior_lock_released", "child_lock_enabled", "child_lock_disabled", "away_mode_enabled", "away_mode_disabled", "unrecognized"],
    "warning": ["warning"],
    "visitor": ["passed_by", "at_door", "departed", "ultrasonic_activity"],
    "doorbell": ["pressed"],
}
