import json
import os
import datetime
import logging
from copy import deepcopy
import traceback
import sys
import mycdp
import signal
from contextlib import contextmanager
from dotenv import load_dotenv
from pathlib import Path
from seleniumbase import SB, BaseCase
from cachetools import FIFOCache
from confluent_kafka import Consumer, Producer, KafkaException

sys.path.insert(0, Path(__file__).parent)
import lifecycle
from pagetimeout import timeout_handler, PageTimeout
from mongodb import init_db, insert_crawl_result

# Load environment variables
load_dotenv()
KAFKA_BROKER = os.getenv("KAFKA_BROKER")
KAFKA_GROUP = os.getenv("KAFKA_GROUP")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
INDEX_TOPIC = os.getenv("INDEX_TOPIC")

# env for database
DB_HOST = os.getenv("DB_HOST")

# Constants
DOMAIN_CSV_PATH = "data/top-1m.csv"
SITES_PER_SESSION = 100

def get_slug(url):
    domain = url.split("//")[-1].split("/")[0].replace(".", "_")
    return domain

def make_network_handlers(sb: BaseCase, additional_requests: list):
    requests = FIFOCache(maxsize=100)

    # Handler for capturing outgoing requests
    async def request_handler(event: mycdp.network.RequestWillBeSent):
        requests[event.request_id] = {
            "url": event.request.url,
            "method": event.request.method,
            "requestBody": event.request.post_data | ""
        }
    
    # Handler for capturing incoming responses
    # Use the request id to correlate original request and response
    async def response_handler(event: mycdp.network.ResponseReceived):
        request_info = requests.get(event.request_id, {})
        try:
            res = await sb.cdp.page.send(
                mycdp.network.get_response_body(event.request_id)
            )
            if res:
                additional_requests.append({
                    "endpoint": event.response.url,
                    "method": request_info.get("method", "Unknown"),
                    "status": event.response.status,
                    "requestBody": request_info.get("requestBody", ""),
                    "responseBody": res[0] if not res[1] else "[base64]",
                    "type": event.response.mime_type
                })
        except Exception as e:
            additional_requests.append({
                "endpoint": event.response.url if event.response and event.response.url else "Error",
                "method": request_info.get("method", "Unknown"),
                "status": event.response.status if event.response and event.response.status else "Error",
                "requestBody": request_info.get("requestBody", ""),
                "responseBody": f"ERROR in response handler: {e}. {traceback.format_exc()}",
                "type": event.response.mime_type if event.response and event.response.mime_type else "Error"
            })
            print(f"Failed for {event.response.url}: {e}")

    # Handler for network error such as DNS failure, connection refused, etc.
    
    async def network_failure_handler(event: mycdp.network.LoadingFailed):
        request_info = requests.get(event.request_id, {})
        additional_requests.append({
            "endpoint": request_info.get("url", "Unknown"),
            "method": request_info.get("method", "Unknown"),
            "status": -1,
            "requestBody": request_info.get("requestBody", ""),
            "responseBody": f"ERROR in network failure handler: {event.error_text}",
            "type": "Unknown"
        })

    return request_handler, response_handler, network_failure_handler

@contextmanager
def launch_selenium_base_browser():
    args = ",".join([
        "--ignore-certificate-errors",
        "--no-sandbox",
        "--disable-dev-shm-usage"
    ])

    sb_profile = Path(__file__).parent.parent / "sb_profile"
    tmp_profile = Path("/tmp/chrome_profile")
    lifecycle.copy_profile(sb_profile, tmp_profile)

    with SB(uc=True, 
    test=True, 
    locale="en", 
    xvfb=True, 
    xvfb_metrics="1920,1080",
    binary_location="cft", 
    user_data_dir=str(tmp_profile), 
    chromium_arg=args,
    window_size="1854,961",
    locale_code="en-US",
    ) as sb:
        lifecycle.clear_tabs(sb)
        sb.activate_cdp_mode("about:blank")

        # Override alert, confirm, and prompt
        # This is necessary to prevent pop-ups from halting our crawler
        sb.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            window._dialogs = [];
            window.alert = (message) => {
                window._dialogs.push({type: "alert", message: message});
            };

            window.confirm = (message) => {
                window._dialogs.push({type: "confirm", message: message});
                return true; // Automatically accept confirms
            };

            window.prompt = (message, defaultValue) => {
                window._dialogs.push({type: "prompt", message: message, defaultValue: defaultValue});
                return defaultValue || "okay"; // Automatically provide default value or "okay" for prompts
            };

        """
        })
        yield sb

def set_network_handlers(sb: BaseCase):
    """
    Set up the necessary handlers to capture network requests and responses.
    Call this function after launching the browser and before navigating to any page.
    An "addtionalRequests" array will be returned. Clear this array before each crawl
    or after saving it to the database to avoid mixing requests from different pages.

    addtionalRequests.clear()
    """
    additional_requests = []
    request_handler, response_handler, failure_handler = make_network_handlers(sb, additional_requests)
    sb.cdp.add_handler(mycdp.network.RequestWillBeSent, request_handler)
    sb.cdp.add_handler(mycdp.network.ResponseReceived, response_handler)
    sb.cdp.add_handler(mycdp.network.LoadingFailed, failure_handler)
    return additional_requests

def extract_dialogs(sb: BaseCase):
    """
    Extract any dialogs (alerts, confirms, prompts) that were triggered
    during the crawl. The output is formatted to the expected schema
    for the interaction schema
    Call this function at the end of the crawl, after the page has loaded.
    """
    dialogs = sb.cdp.execute_script("return window._dialogs;")
    return {
        "type": "dialogs",
        "info": json.dumps(dialogs)
    }

def get_status_of(requests, url):
    for req in requests:
        if req.get("endpoint") == url:
            return req.get("status", -1)
    return -1

def main():

    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': KAFKA_GROUP,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,  # Manual commit after successful crawl
        'max.poll.interval.ms': 900000,
    })
    producer = Producer({
        'bootstrap.servers': KAFKA_BROKER,
    })

    consumer.subscribe([KAFKA_TOPIC])

    site_counter = 0
    sb_context = None
    sb: BaseCase = None
    additional_requests = []

    def start_browser():
        nonlocal sb_context, sb, additional_requests
        sb_context = launch_selenium_base_browser()
        sb = sb_context.__enter__()
        additional_requests = []
        request_handler, response_handler, network_failure_handler = make_network_handlers(sb, additional_requests)
        sb.cdp.add_handler(mycdp.network.RequestWillBeSent, request_handler)
        sb.cdp.add_handler(mycdp.network.ResponseReceived, response_handler)
        sb.cdp.add_handler(mycdp.network.LoadingFailed, network_failure_handler)

    def stop_browser():
        nonlocal sb_context, sb, additional_requests
        if sb_context:
            sb_context.__exit__(None, None, None)
            sb_context = None
            sb = None
            additional_requests = []

    start_browser()
    try:
        while True:
            if site_counter >= SITES_PER_SESSION:
                stop_browser()
                start_browser()
                site_counter = 0

            msg = consumer.poll(timeout=10.0)
            if msg is None:
                logging.info("No messages received. Waiting...")
                continue
            if msg.error():
                raise KafkaException(msg.error())
            
            message_str = msg.value().decode('utf-8').split(',')[0]
            index_start = message_str.find("DNS:")
            if index_start == -1:
                index_start = message_str.find("IP Address:")
                url = message_str if index_start == -1 else message_str[index_start+11:]
            else:
                url = message_str[index_start+4:]
            url = url[2:] if url.startswith("*.") else url
            try:
                additional_requests.clear() # Clear previous requests before crawl
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(15)
                accessed_date = datetime.datetime.now(tz=datetime.timezone.utc)
                sb.cdp.get(f'https://{url}')
                sb.sleep(.5) # wait for potential captcha to load
                sb.cdp.solve_captcha()
                sb.sleep(2) # wait for page to load after captcha
                redirected_url = sb.cdp.get_current_url()   
                page_src = sb.cdp.get_page_source()
                signal.alarm(0) # disable alarm after page load    

                # TODO - include other interactions
                # Like eth wallets
                dialogs = extract_dialogs(sb)
                interactions = dialogs
            except PageTimeout:
                print(f"Page load timed out for {url}")
                redirected_url = url
                page_src = ""
                interactions = []
            except Exception as e:
                signal.alarm(0) # disable alarm in case of other exceptions
                print(f"Error crawling {url}: {e}")
                redirected_url = url
                page_src = ""
                interactions = []
            finally:
                status = get_status_of(additional_requests, url)
                insert_crawl_result(
                    url=url,
                    redirected_url=redirected_url,
                    accessed_date=accessed_date,
                    status=status,
                    page_src=page_src,
                    additional_requests=deepcopy(additional_requests),
                    interactions=[interactions] if interactions else []
                )
                producer.produce(INDEX_TOPIC, url.encode('utf-8'))
                producer.flush()
                consumer.commit(msg)
                site_counter += 1

    except KafkaException as e:
        print(f"Kafka error: {e}")
    finally:
        stop_browser()
        consumer.close()
        
if __name__ == "__main__":
    init_db(DB_HOST)
    main()