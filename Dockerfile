FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper.py .
COPY scripts/ scripts/

VOLUME ["/data"]

ENTRYPOINT ["python", "scraper.py"]
# Pass a different start URL as CMD, e.g.:
# CMD ["https://author.today/work/genre/all/ebook"]
