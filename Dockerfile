FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y iputils-ping iproute2 openssh-client procps; \
    rm -rf /var/lib/apt/lists/*

COPY sentinel_hl ./sentinel_hl
COPY README.md requirements.txt setup.py ./
COPY docker/entrypoint.sh /usr/local/bin/
COPY docker/ssh_config /root/.ssh/config

RUN pip install --upgrade .; \
    ln -s /usr/local/bin/sentinel-hl /usr/local/bin/run; \
    chmod +x /usr/local/bin/entrypoint.sh

VOLUME ["/config", "/ssh_keys"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["daemon"]