import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_COMMAND_TOPIC = os.getenv("KAFKA_COMMAND_TOPIC", "fleet-commands")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "mqtt-outbound-bridge-group")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

DEDUP_CACHE_SIZE = int(os.getenv("DEDUP_CACHE_SIZE", "20000"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9102"))
