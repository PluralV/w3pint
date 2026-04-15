class PageTimeout(Exception):
    pass

def timeout_handler(signum, frame):
    raise PageTimeout()