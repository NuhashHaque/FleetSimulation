This is the ultimate, consolidated blueprint of your enterprise architecture. It incorporates the bi-directional edge bridge, TimescaleDB unified storage, specific parallel processing requirements, and the strict Kafka routing rules (Partitions, Keys, and Consumer Groups) required to keep data perfectly synchronized.

### Flow 1: Command Lifecycle (User $\rightarrow$ Simulator & Databases)

This traces a state-change instruction (like "PAUSE") from the web dashboard down to the simulated edge device and the permanent audit log.

1. **The Trigger (Browser / React UI):**
* The operator clicks "PAUSE" for Bus 1.
* React sends an HTTP `POST` request (`/api/command`) with the payload: `{"bus_id": "BUS_01", "action": "PAUSE", "user": "admin_1"}`.


2. **The Gateway (Nginx):**
* Nginx intercepts the HTTPS request on port 443 and proxies it to the internal FastAPI container.


3. **The API & Producer (FastAPI Backend):**
* **Parallel Requirement:** FastAPI handles this route asynchronously (`async def`) so it does not block ongoing live streams.
* **Kafka Routing:** FastAPI produces the JSON payload into the Kafka topic `fleet-commands`. Crucially, it uses `bus_id` as the **Message Key** to guarantee the commands for Bus 1 always go to the same partition in chronological order.
* FastAPI instantly returns an HTTP `200 OK` to the UI.


4. **The Central Event Bus (Apache Kafka):**
* The `fleet-commands` topic holds the message (configured with **4 Partitions** to support future scaling).


5. **The Audit Storage (TimescaleDB ETL Worker):**
* **Parallel Requirement:** A Python script runs a continuous `while True` polling loop in the background.
* **Kafka Routing:** It connects to Kafka using the Consumer Group `timescaledb-audit-etl-group`.
* It reads the command and executes an `INSERT` into the standard relational `command_audit_log` table in **TimescaleDB**, logging the user, action, and exact timestamp.


6. **The Command Bridge (Kafka $\rightarrow$ Mosquitto):**
* **Parallel Requirement:** An independent Python container runs another continuous polling loop.
* **Kafka Routing:** It connects using a *different* Consumer Group: `mqtt-outbound-bridge-group` (ensuring it gets its own copy of the message without stealing it from the database worker).
* It translates the payload and publishes it to the **Mosquitto Broker** on the topic `fleet/bus/BUS_01/command`.


7. **The Device Execution (Python Simulator):**
* **Parallel Requirement:** The simulator runs `paho-mqtt`'s asynchronous network thread (`client.loop_start()`).
* This thread receives the MQTT message, securely acquires a **Thread Lock**, and updates the internal state machine of the specific `BUS_01` physics thread to `PAUSED`.



---

### Flow 2: Live Telemetry Lifecycle (Simulator $\rightarrow$ User & Databases)

This traces the relentless 1Hz physical location updates and operational events from the edge to the live map and data warehouse.

1. **The Edge Emission (Python Simulator):**
* **Parallel Requirement:** You run **4 independent worker threads** (one per bus). Each thread sleeps for 1 second, wakes up, calculates the LERP physics along its specific route, and checks if it reached a station (e.g., completing a trip).
* It publishes the resulting JSON payload to the **Mosquitto Broker** on the topic `fleet/bus/BUS_01/telemetry`.


2. **The Ingestion Bridge (Mosquitto $\rightarrow$ Kafka):**
* **Parallel Requirement:** A lightweight Python container uses an asynchronous MQTT callback (`on_message`) to instantly catch arriving data.
* **Kafka Routing:** It immediately acts as a Kafka Producer, dropping the JSON into the Kafka topic `raw-telemetry`, explicitly setting `bus_id` as the **Message Key** to prevent out-of-order coordinate jumping.


3. **The Central Event Bus (Apache Kafka):**
* The `raw-telemetry` topic holds the high-frequency data (configured with **4+ Partitions**).


4. **The Live UI Stream (FastAPI $\rightarrow$ Nginx $\rightarrow$ React):**
* **Parallel Requirement:** FastAPI runs a dedicated `aiokafka` consumer as an asynchronous background task.
* **Kafka Routing:** It connects using the Consumer Group `fastapi-sse-group`.
* It yields the incoming Kafka messages into an open **Server-Sent Events (SSE)** connection. Nginx passes this stream to React, which updates the UI progress bars at 60fps without freezing the browser.


5. **The Storage Router (TimescaleDB ETL Worker):**
* **Parallel Requirement:** A dedicated Python worker script runs a continuous polling loop.
* **Kafka Routing:** It connects using the Consumer Group `timescaledb-telemetry-etl-group`.
* It parses the JSON and executes a logical split:
* **Path A (Physics Data):** It strips out `lat`, `lon`, `speed`, and `timestamp`, then executes an `INSERT` into the `telemetry` **Hypertable**. TimescaleDB automatically partitions this data into time-based chunks on the disk.
* **Path B (Event Data):** It checks the JSON to see if a trip counter incremented. If an event occurred, it executes a separate `INSERT` into the standard relational `trip_logs` table.


---

This complete, finalized flow protects your system from data loss, prevents database lockups, and guarantees that your live React map remains perfectly smooth regardless of how much historical data you are saving.
