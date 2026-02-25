import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_COMMAND_TOPIC = os.getenv("KAFKA_COMMAND_TOPIC", "fleet-commands")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "timescaledb-audit-etl-group")
KAFKA_AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")

DB_HOST = os.getenv("DB_HOST", "timescaledb")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fleetdb")
DB_USER = os.getenv("DB_USER", "fleet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fleetpass")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9103"))
