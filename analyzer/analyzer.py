import json
import os
import sys
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from confluent_kafka import Consumer, KafkaException

# Load .env from same directory as this script
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

KAFKA_BROKER = os.getenv("KAFKA_BROKER")
KAFKA_GROUP = os.getenv("KAFKA_GROUP")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
DB_HOST = os.getenv("DB_HOST")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def init_db(db_host: str):
    """
    Initialize the MongoDB connection. Returns the database object or None on failure.
    """
    db_user = os.environ.get('DB_USER')
    db_pwd = os.environ.get('DB_PWD')
    db_name = os.environ.get('DB_NAME')

    connection_string = "mongodb://"
    if db_user and db_pwd:
        connection_string += f"{db_user}:{db_pwd}@"
    connection_string += f"{db_host.strip()}"

    try:
        client = MongoClient(connection_string, authSource="admin")
        client.admin.command('ping')
        db = client.get_database(db_name)
        logging.info(f"Connected to MongoDB at {db_host}")
        return db
    except ConnectionFailure as e:
        logging.error(f"Failed to connect to {db_host}: {e}")
        return None


def load_search_terms(path: str) -> dict:
    """
    Load search_terms.json and validate its structure.
    Lowercases all terms for case-insensitive matching.
    """
    with open(path, 'r') as f:
        terms = json.load(f)
    if not isinstance(terms.get('js_lines'), list):
        raise ValueError("search_terms.json must have a 'js_lines' array")
    if not isinstance(terms.get('domains'), list):
        raise ValueError("search_terms.json must have a 'domains' array")
    terms['js_lines'] = [t.lower() for t in terms['js_lines']]
    terms['domains'] = [t.lower() for t in terms['domains']]
    return terms


def search_page_source(page_src: str, js_lines: list) -> list:
    """
    Scan page source line by line. For each line containing a phrase from js_lines,
    record the line number and line text.
    Returns a list of {line_number, line_text} dicts.
    """
    if not page_src:
        return []
    found_lines = []
    for line_num, line in enumerate(page_src.split('\n'), start=1):
        line_lower = line.lower()
        for phrase in js_lines:
            if phrase in line_lower:
                found_lines.append({"line_number": line_num, "line_text": line.strip()})
                break  # one match per line is sufficient
    return found_lines


def search_additional_requests(additional_requests: list, domains: list, js_lines: list) -> tuple:
    """
    Search additionalRequests for domain matches and response payload matches.

    For each request:
      - If endpoint contains a domain from the list, add it to connected_domains
        and then search its responseBody for js_lines phrases.
      - If no domain match, skip entirely.

    Returns (connected_domains, responses).
    """
    if not additional_requests:
        return [], []
    connected_domains = []
    responses = []
    for idx, req in enumerate(additional_requests):
        endpoint = (req.get('endpoint') or '').lower()
        domain_matched = False
        for domain in domains:
            if domain in endpoint:
                connected_domains.append(req.get('endpoint', ''))
                domain_matched = True
                break
        if not domain_matched:
            continue

        # Search responseBody for js_lines phrases
        response_body = req.get('responseBody', '')
        if not response_body:
            continue
        # Skip sentinel values from the crawler
        if response_body == '[base64]' or response_body.startswith('ERROR in'):
            continue
        response_body_lower = response_body.lower()
        for phrase in js_lines:
            if phrase in response_body_lower:
                responses.append({"request_index": idx, "matched_phrase": phrase})
    return connected_domains, responses


def analyze_document(doc: dict, search_terms: dict) -> dict:
    """
    Run the full analysis on a single MongoDB document.
    Returns a dict with found_lines, connected_domains, responses, and interest flag.
    """
    js_lines = search_terms['js_lines']
    domains = search_terms['domains']

    found_lines = search_page_source(doc.get('pageSrc', ''), js_lines)
    connected_domains, responses = search_additional_requests(
        doc.get('additionalRequests', []), domains, js_lines
    )

    interest = 1 if (found_lines or connected_domains or responses) else 0

    return {
        'found_lines': found_lines,
        'connected_domains': connected_domains,
        'responses': responses,
        'interest': interest
    }


def update_document(db, url: str, analysis: dict) -> bool:
    """
    Write the analysis results back to the MongoDB document for this URL.
    Returns True on success, False on failure.
    """
    try:
        result = db.crawls.update_one(
            {"url": url},
            {"$set": analysis}
        )
        if result.matched_count >= 1:
            logging.info(f"Updated {url} | interest={analysis['interest']}")
            return True
        else:
            logging.warning(f"No document matched for {url} during update")
            return False
    except Exception as e:
        logging.error(f"MongoDB update failed for {url}: {e}")
        return False


def main():
    # 1. Connect to MongoDB
    db = init_db(DB_HOST)
    if db is None:
        logging.critical("Cannot start: MongoDB connection failed")
        sys.exit(1)

    # 2. Load search terms
    search_terms_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'search_terms.json')
    search_terms = load_search_terms(search_terms_path)
    logging.info(f"Loaded {len(search_terms['js_lines'])} JS phrases, "
                 f"{len(search_terms['domains'])} domains")

    # 3. Init Kafka consumer
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': KAFKA_GROUP,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    })
    consumer.subscribe([KAFKA_TOPIC])
    logging.info(f"Subscribed to {KAFKA_TOPIC} as group {KAFKA_GROUP}")

    try:
        while True:
            # Poll for next URL
            msg = consumer.poll(timeout=10.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            url = msg.value().decode('utf-8').strip()
            if not url:
                consumer.commit(msg)
                continue

            # 4. Check if MongoDB has an entry for this URL
            doc = db.crawls.find_one({"url": url})
            if doc is None:
                logging.debug(f"No document found for {url}, skipping")
                consumer.commit(msg)
                continue

            # 5-7. Analyze the document
            try:
                analysis = analyze_document(doc, search_terms)
            except Exception as e:
                logging.error(f"Analysis error for {url}: {e}", exc_info=True)
                consumer.commit(msg)
                continue

            # 8. Update MongoDB with results
            success = update_document(db, url, analysis)
            if not success:
                logging.warning(f"Skipping commit for {url} due to update failure")
                continue

            # 9. Commit and move on
            consumer.commit(msg)

    except KafkaException as e:
        logging.error(f"Kafka error: {e}")
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        consumer.close()
        logging.info("Consumer closed")


if __name__ == "__main__":
    main()
