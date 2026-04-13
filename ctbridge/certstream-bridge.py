import json
import websocket
from confluent_kafka import Producer

CERTSTREAM_URL = "ws://127.0.0.1:8080"
KAFKA_BOOTSTRAP = "127.0.0.1:9092"
TOPIC = "ct-stream"
seen_urls = 0

producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

def on_message(wsock, message):
    # message from certstream-server is in JSON
    global seen_urls

    if seen_urls == 0:
        parsed = json.loads(message)
        if parsed.get("message_type") == "certificate_update":
            try:
                dns_name = parsed['data']['leaf_cert']['extensions']['subjectAltName']
            except KeyError:
                return
            dns_name = dns_name.split(',')[0]
            print(f"Parsed a certificate update for {dns_name}")
            producer.produce(TOPIC, value=dns_name.encode("utf-8"))
            producer.poll(0)
    seen_urls = (seen_urls + 1) % 5


def on_error(wsock, error):
    print(f"WebSocket error: {error}")

def on_close(wsock, close_status_code, close_msg):
    print(f"WebSocket closed: {close_status_code} {close_msg} \nReconnecting in 5s...")

def on_open(wsock):
    print("Connected to certstream-server!")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        CERTSTREAM_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )

    ws.run_forever(reconnect=5)