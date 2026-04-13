FROM python:3.12-slim

WORKDIR /analyzer

RUN pip install --no-cache-dir python-dotenv confluent-kafka pymongo

COPY analyzer/ .

CMD ["python3", "analyzer.py"]
