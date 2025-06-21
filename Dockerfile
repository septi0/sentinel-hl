FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential iputils-ping iproute2 openssh-client; \
    rm -rf /var/lib/apt/lists/*

COPY ./sentinel_hl ./sentinel_hl
COPY run.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

VOLUME ["/config"]

ENTRYPOINT ["python", "-m", "sentinel_hl", "--config", "/config/config.yml"]

CMD ["daemon"]