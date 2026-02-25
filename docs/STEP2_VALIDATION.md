# Step 2 Validation Checklist

## Goal
Finalize contracts and Kafka topic setup with DLQs.

## Must Pass
1. Contracts exist and are versioned.
2. Topics created with expected partition counts.
3. Message key routing by `bus_id` is verified.
4. DLQ topics accept malformed payload events.

## Commands Used (reference)
- Initialize topics:
  - `docker exec fleet_kafka sh -lc '.../infra/kafka/init-topics.sh'`
- Describe topics:
  - `docker exec fleet_kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic fleet-commands`
  - `docker exec fleet_kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic raw-telemetry`
- Key routing smoke:
  - produce same key (`BUS_01`) twice and verify same partition in consumer output
- DLQ smoke:
  - publish malformed payload into `raw-telemetry-dlq` and consume 1 record
