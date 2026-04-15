from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, CollectionInvalid, WriteError
from datetime import datetime
import os
import logging

base_properties = {
    "redirectedUrl": {
        "bsonType": "string",
        "description": "URL after the page has loaded. May be different from initial URL. Required."
    },
    "accessedDate": {
        "bsonType": "date",
        "description": "date of crawl. Required."
    },
    "status": {
        "bsonType": "int",
        "description": "HTTP Status. Required."
    },
    "pageSrc": {
        "bsonType": "string",
        "description": "HTML source of the webpage."
    },
    "additionalRequests": {
        "bsonType": "array",
        "items": {
            "bsonType": "object",
            "required": ["endpoint", "method", "status"],
            "properties": {
                "endpoint": {
                    "bsonType": "string",
                    "description": "endpoint of the request. Required."
                },
                "method": {
                    "bsonType": "string",
                    "description": "HTTP method of the request. Required."
                },
                "status": {
                    "bsonType": "int",
                    "description": "HTTP status of the request. Required."
                },
                "requestBody": {
                    "bsonType": "string",
                    "description": "request body. Required."
                },
                "responseBody": {
                    "bsonType": "string",
                    "description": "response body. Optional."
                },
                "type": {
                    "bsonType": "string",
                    "description": "optional type of request (e.g., html, css, js, image, etc.)"
                }
            }
        },
        "description": "Optional array of additional requests made by the webpage."
    },
    "interactions": {
        "bsonType": "array",
        "items": {
            "bsonType": "object",
            "required": ["type", "info"],
            "properties": {
                "type": {
                    "bsonType": "string",
                    "description": "type of interation that occurred."
                },
                "info": {
                    "bsonType": "string",
                    "description": "information about the interaction that occurred."
                }
            }
        },
        "description": "Optional array of interactions that occurred during the crawl. Subject to change"
    }
}

validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["url", "redirectedUrl", "accessedDate", "status"],
        "properties": {
            "url": {
                "bsonType": "string",
                "description": "string and required"
            },
            **base_properties,
            "followups": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": [ "redirectedUrl", "accessedDate", "status"],
                    "properties": base_properties
                },
                "description": "Optional array of followup crawls after some time has passed since the initial crawl."
            }
        }
    }
}

db = None

def init_db(db_host: str):
    """
    Initialize the database connection. This updates the global db variable used by other database functions.
    Call this function before calling any other database functions.
    Environment variables for DB_USER, DB_PWD, and DB_NAME can be set for authentication and specifying the database name.
    
    :param db_host: the host of the MongoDB server. e.g., "127.0.0.1:27017"
    :return: the database object if the connection is successful, None otherwise.
    """
    global db
    db_user = os.environ.get('DB_USER')
    db_pwd = os.environ.get('DB_PWD')
    db_name = os.environ.get('DB_NAME')

    connection_string = "mongodb://"
    if db_user and db_pwd:
        connection_string += f"{db_user}:{db_pwd}@"
    connection_string += f"{db_host.strip()}"
    # if db_name:
    #     connection_string += f"/{db_name}"

    try:
        logging.info(connection_string)
        client = MongoClient(connection_string, authSource="admin")
        client.admin.command('ping')
        db = client.get_database(db_name)
        logging.info(f"Connection established for {db_host}")
        try:
            db.create_collection("crawls", validator=validator, validationLevel="strict", validationAction="error")
        except CollectionInvalid:
            logging.info("Collection 'crawls' already exists. Skipping creation.")
        return db
    except ConnectionFailure as e:
        logging.info(f"Failed to connect to {db_host}: {e}")
        return None

def insert_crawl_result(url: str, redirected_url: str, accessed_date: datetime, status: int, page_src: str = "", additional_requests: list = None, interactions: list = None):
    """
    Call init_db first to initialize the database connection before calling this function.

    Insert a crawl result into the database.
    If the website has already been crawled before, the result is instead added to the
    followup array of that website's crawl document.
    The required fields are url, redirected_url, and accessed_date.
    The rest is optional that tracks addtional information about the crawl.

    :param url: the initial URL that was crawled. e.g., "http://example.com"
    :param redirected_url: the URL after the page has loaded. May be different from initial URL. e.g., "http://example.com/home"
    :param accessed_date: date of crawl. e.g., datetime.now()
    :param status: HTTP Status. e.g., 200
    :param page_src: HTML source of the webpage. e.g., "<html></html>"
    :param additional_requests: Optional array of additional requests made by the webpage. Additional requests contain the properties, request (string), status (int), response (string), and an optional type (string) field.  View the schema for more information.
    :param interactions: Optional array of interactions that occurred during the crawl. Subject to change. Interactions contain the properties: type (string) and info (string). View the schema for more information.
    """
    
    global db
    if db is None:
        raise Exception("Database not initialized. Call init_db first.")
    
    crawl_data = {
        "redirectedUrl": redirected_url,
        "accessedDate": accessed_date,
        "status": status,
        "pageSrc": page_src,
        "additionalRequests": additional_requests or [],
        "interactions": interactions or []
    }

    try:
        result = db.crawls.update_one(
            {"url": url},
            [
                {
                    "$set": {
                        "url": {"$ifNull": ["$url", url]},
                        "redirectedUrl": {"$ifNull": ["$redirectedUrl", redirected_url]},
                        "accessedDate": {"$ifNull": ["$accessedDate", accessed_date]},
                        "status": {"$ifNull": ["$status", status]},
                        "pageSrc": {"$ifNull": ["$pageSrc", page_src]},
                        "additionalRequests": {"$ifNull": ["$additionalRequests", additional_requests or []]},
                        "interactions": {"$ifNull": ["$interactions", interactions or []]},
                        "followups": {
                            "$cond": {
                                "if": {"$isArray": "$followups"},
                                "then": {"$concatArrays": ["$followups", [crawl_data]]},
                                "else": []
                            }
                        }
                    }
                }
            ],
            upsert=True
        )
        if result.upserted_id:
            logging.info(f"Inserted new crawl result for {url} with ID {result.upserted_id}")
            return {
                "action": "new crawl",
                "id": str(result.upserted_id)
            }
        else:
            logging.info(f"Added followup crawl result for {url}")
            return {
                "action": "followup crawl",
            }

    except WriteError as e:
        logging.info(f"Failed to insert crawl result for {url}: {e}")
        return None
    
if __name__ == "__main__":
    # Example usage
    init_db("130.245.32.249:27777")
    insert_crawl_result(
        url="http://example.com",
        redirected_url="http://example.com/home",
        accessed_date=datetime.now(),
        status=200,
        page_src="<html><head><link rel='stylesheet' href='style.css'><script src='script.js'></script></head><body><h1>Example</h1></body></html>",
        additional_requests=[
            {
                "request": "http://example.com/style.css",
                "status": 200,
                "type": "css"
            },
            {
                "request": "http://example.com/script.js",
                "status": 200,
                "type": "js"
            }
        ],
        interactions=[
            {
                "type": "click",
                "info": "Clicked on the 'Learn More' button."
            },
            {
                "type": "scroll",
                "info": "Scrolled to the bottom of the page."
            }
        ]
    )