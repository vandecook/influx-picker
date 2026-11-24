"""Constants for Series Picker."""

DOMAIN = "series_picker"

# Entry data
CONF_BACKEND = "backend"
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_ORG = "organization"
CONF_BUCKET = "bucket"
CONF_VERIFY_SSL = "verify_ssl"
CONF_PRECISION = "precision"

# Entry options
CONF_LABEL_CHANGE = "label_change"
CONF_LABEL_HEARTBEAT = "label_heartbeat"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
CONF_INHERIT = "inherit_labels"
CONF_STARTUP_SNAPSHOT = "startup_snapshot"
CONF_MANUAL_CHANGE = "manual_change"  # entity IDs, write on change
CONF_MANUAL_HEARTBEAT = "manual_heartbeat"  # entity IDs, change + heartbeat

# What is written for every selected entity when the entry starts
# (Home Assistant start or reload of the entry).
STARTUP_SNAPSHOT_NOW = "now"  # current time, marked as heartbeat
STARTUP_SNAPSHOT_LAST_UPDATED = "last_updated"  # own time, marked _startup
STARTUP_SNAPSHOT_OFF = "off"
STARTUP_SNAPSHOT_MODES = (
    STARTUP_SNAPSHOT_NOW,
    STARTUP_SNAPSHOT_LAST_UPDATED,
    STARTUP_SNAPSHOT_OFF,
)

# Entry options: data format, same names and meaning as the core integration
CONF_MEASUREMENT_ATTR = "measurement_attr"
CONF_DEFAULT_MEASUREMENT = "default_measurement"
CONF_OVERRIDE_MEASUREMENT = "override_measurement"
CONF_TAGS = "tags"
CONF_TAGS_ATTRIBUTES = "tags_attributes"
CONF_IGNORE_ATTRIBUTES = "ignore_attributes"
CONF_COMPONENT_CONFIG = "component_config"
CONF_COMPONENT_CONFIG_DOMAIN = "component_config_domain"
CONF_COMPONENT_CONFIG_GLOB = "component_config_glob"

DEFAULT_PRECISION = "ns"  # same as the core integration
DEFAULT_HEARTBEAT_INTERVAL = 15  # minutes
DEFAULT_INHERIT = True
DEFAULT_STARTUP_SNAPSHOT = STARTUP_SNAPSHOT_NOW

# Pre-filled in the data format step of a new setup. These are not the core
# defaults but the maintainer's usual settings; the user can clear them.
# Stored options are never filled in from here.
SUGGESTED_DATA_FORMAT = {
    CONF_DEFAULT_MEASUREMENT: "units",
    CONF_TAGS: {"source": "HA"},
    CONF_TAGS_ATTRIBUTES: ["friendly_name"],
}

# Exporter defaults (see ROADMAP.md, M1 buffer defaults)
BATCH_SIZE = 100
BATCH_TIMEOUT = 1.0  # seconds of quiet before a flush
MAX_QUEUE = 50_000  # points
BACKOFF_START = 5.0  # seconds
BACKOFF_MAX = 60.0  # seconds
WRITE_TIMEOUT = 10  # seconds, same as the core integration
SHUTDOWN_FLUSH_TIMEOUT = 10.0  # seconds
