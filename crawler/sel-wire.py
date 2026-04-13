import json
import os
import time
import datetime
import shutil
import logging
from pymongo import MongoClient
import pandas as pd
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
from confluent_kafka import Consumer, Producer, KafkaException


# Load environment variables
load_dotenv()
KAFKA_BROKER = os.getenv("KAFKA_BROKER")
KAFKA_GROUP = os.getenv("KAFKA_GROUP")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
INDEX_TOPIC = os.getenv("INDEX_TOPIC")

#env for database
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PWD = os.getenv("DB_PWD")
DB_NAME = os.getenv("DB_NAME")

# Constants
base_path = "../../setup/chrome/browser_setup/versions/"
CHROME_VERSION = "134.0.6944.0"
CHROME_FOLDER = "../../setup/chrome/browser_setup/versions/"
DOMAIN_CSV_PATH = "data/top-1m.csv"
#df = pd.read_csv(DOMAIN_CSV_PATH, header=None, names=["id", "domain"])

def get_chrome_binary_path(version):
    return f"{CHROME_FOLDER}version_{version}/chrome/chrome-linux64/chrome"

def get_slug(url):
    domain = url.split("//")[-1].split("/")[0].replace(".", "_")
    return domain

def launch_selenium_wire_browser(chrome_path, time_start, domain_slug):
    chrome_options = Options()
    # chrome_options.binary_location = chrome_path

    profile_dir = f"/tmp/chrome-profile-{str(time_start)}/{domain_slug}"
    os.makedirs(profile_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1024,768")
    chrome_options.add_argument("--headless=new")

    chromedriver_path = os.path.join(
        base_path,
        f"version_{CHROME_VERSION}",
        "chromedriver/chromedriver-linux64/chromedriver"
    )

    #service = Service(executable_path=chromedriver_path)
    #driver = webdriver.Chrome(service=service, options=chrome_options)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def extract_domains(driver):
    additional_reqs = set()
    for request in driver.requests:
        if request.host:
            request_obj = {
                "endpoint": request.url,
                "request": request.body
            }

            if request.response:
                cont_type = request.response.headers.get('Content-Type')
                request_obj["response"] = request.response.body
                request_obj["status"] = request.response.status_code
                request_obj["type"] = cont_type
            else:
                request_obj["status"] = -1 #If no response was received, status code -1
            additional_reqs.add(request_obj)
    return additional_reqs


def save_domains(domain_slug, domains):
    os.makedirs("logs", exist_ok=True)
    output_path = f"logs/{domain_slug}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        for domain in sorted(domains):
            f.write(f"{domain}\n")

def main(mdb_client):
    os.makedirs("run_logs", exist_ok=True)
    time_start = datetime.datetime.now(tz=datetime.timezone.utc)
    log_file = f"run_logs/crawl_log_{str(time_start)}.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.getLogger("seleniumwire").setLevel(logging.WARNING)

    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': KAFKA_GROUP,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,  # Manual commit after successful crawl
    })
    producer = Producer({
        'bootstrap.servers': KAFKA_BROKER,
    })

    consumer.subscribe([KAFKA_TOPIC])

    chrome_binary_path = get_chrome_binary_path(CHROME_VERSION)
    try:
        while True:
            msg = consumer.poll(timeout=10.0)
            if msg is None:
                logging.info("No messages received. Waiting...")
                continue
            if msg.error():
                raise KafkaException(msg.error())

            message_str = msg.value().decode('utf-8')
            index_start = message_str.find("DNS:")
            if index_start == -1:
                url = message_str
            else:
                url = message_str[index_start+4:]
            domain_slug = get_slug(url)
            driver = None
            retries = 0
            while retries < 3:
                try:
                    driver = launch_selenium_wire_browser(chrome_binary_path, time_start, domain_slug)
                    driver.get(url)
                    base_status = -1
                    for request in driver.requests:
                        if request.url == url and request.response:
                            base_status = request.response.status_code
                            break
                    time.sleep(2)
                    extra_requests = extract_domains(driver)
                    # save_domains(domain_slug, extra_requests)
                    result_log = {
                        'redirectedUrl': url,
                        'accessedDate': datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                        'status':base_status,
                        'pageSrc': driver.page_source,
                        'additionalRequests': list(extra_requests),
                        'interactions':[] #TODO: once interactions are recorded add in
                    }
                    result_log_json = json.dumps(result_log)

                    '''Commit to database:'''
                    '''TODO TODO TODO'''
                    '''use mdb_client to insert the json object as document etc'''
                    '''Commit URL back to Kafka queue:'''
                    producer.produce(INDEX_TOPIC, result_log['redirectedUrl'].encode('utf-8'))
                    producer.flush()

                    consumer.commit(msg)

                    logging.info(f"Successfully visited {url}")
                    break
                except Exception as e:
                    retries +=1
                    error_msg = str(e).split("\n")[0]
                    logging.error(f"Failed to visit {url}: {error_msg}")
                finally:
                    if retries == 3:
                        consumer.commit(msg)
                    if driver:
                        driver.quit()
                    shutil.rmtree(f"/tmp/chrome-profile-{str(time_start)}/{domain_slug}", ignore_errors=True)
    finally:
        consumer.close()

if __name__ == "__main__":
    # try:
    #     mdb_client = MongoClient(f"mongodb://{DB_USER}:{DB_PASS}@{DATABASE_ADDR}")
    #     mdb_client.connect()
    #     # Send a ping to confirm a successful connection
    #     mdb_client.admin.command({'ping': 1})
    #     logging.info("Successfully connected to MongoDB!")
    # except Exception as e:
    #     logging.error(f"Failed to connect to MongoDB: {e}")
    #     exit(-1)
    main(None)
    # mdb_client.close()

    # logs = os.listdir('logs/')
    # domains = set()
    # for log in logs:
    #     domains.add(log)
    #     data = [x.strip() for x in open('logs/' + log).readlines()]
    #     for x in data:
    #         domains.add(x)
    # print(len(domains))