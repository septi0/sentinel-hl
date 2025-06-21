FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y iputils-ping iproute2 openssh-client procps; \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --upgrade .; \
    ln -s /usr/local/bin/sentinel-hl /usr/local/bin/run

VOLUME ["/config"]

ENTRYPOINT ["/usr/local/bin/sentinel-hl"]

CMD ["daemon"]