import os

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "fleet/bus/+/telemetry")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TELEMETRY_TOPIC = os.getenv("KAFKA_TELEMETRY_TOPIC", "raw-telemetry")
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "raw-telemetry-dlq")

SERVICE_NAME = os.getenv("SERVICE_NAME", "mqtt-to-kafka-bridge")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9101"))
