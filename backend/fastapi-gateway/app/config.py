import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_COMMAND_TOPIC = os.getenv("KAFKA_COMMAND_TOPIC", "fleet-commands")
KAFKA_TELEMETRY_TOPIC = os.getenv("KAFKA_TELEMETRY_TOPIC", "raw-telemetry")
KAFKA_TELEMETRY_CONSUMER_GROUP = os.getenv("KAFKA_TELEMETRY_CONSUMER_GROUP", "fastapi-sse-group")
SERVICE_NAME = os.getenv("SERVICE_NAME", "fastapi-gateway")

DB_HOST = os.getenv("DB_HOST", "timescaledb")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fleetdb")
DB_USER = os.getenv("DB_USER", "fleet")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fleetpass")
