"""Constants for Influx Picker."""

DOMAIN = "influx_picker"

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

DEFAULT_PRECISION = "ns"  # same as the core integration
DEFAULT_HEARTBEAT_INTERVAL = 15  # minutes
DEFAULT_INHERIT = True

# Exporter defaults (see ROADMAP.md, M1 buffer defaults)
BATCH_SIZE = 100
BATCH_TIMEOUT = 1.0  # seconds of quiet before a flush
MAX_QUEUE = 50_000  # points
BACKOFF_START = 5.0  # seconds
BACKOFF_MAX = 60.0  # seconds
WRITE_TIMEOUT = 10  # seconds, same as the core integration
SHUTDOWN_FLUSH_TIMEOUT = 10.0  # seconds
