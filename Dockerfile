FROM python:3.12-slim

# curl for uploads, fonts-dejavu-core for e-ink rendering on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# output/ and state/ are mounted as volumes at runtime; create stubs so
# Python doesn't choke if the mount isn't present during build/test.
RUN mkdir -p output/eink output/iphone state

CMD ["python", "-u", "scripts/watch_and_upload.py"]
