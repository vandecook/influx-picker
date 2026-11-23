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

# Exporter defaults (see ROADMAP.md, M1 buffer defaults)
BATCH_SIZE = 100
BATCH_TIMEOUT = 1.0  # seconds of quiet before a flush
MAX_QUEUE = 50_000  # points
BACKOFF_START = 5.0  # seconds
BACKOFF_MAX = 60.0  # seconds
WRITE_TIMEOUT = 10  # seconds, same as the core integration
SHUTDOWN_FLUSH_TIMEOUT = 10.0  # seconds
