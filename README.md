# Sentinel-Hl

## Description

**Sentinel-Hl** is a python script that watches over your infrastructure and ensures that all systems are running. It monitors the status of systems, optionally checks for power outages, and manages the shutdown and wake-up processes of systems based on their status and power availability to ensure minimal downtime and protection against power outages.

It uses WOL (Wake-on-LAN) to wake up systems that are down and polls the NUT (Network UPS Tools) server to check for power outages and shutdown systems if necessary via SSH. After power is restored and stable, it wakes up the systems again.

It can be run as a python package, a standalone script, or as a docker container using image `ghcr.io/septi0/sentinel-hl:latest`.

**Shortly:** System not responding? Wake it up by sending a magic packet. Power outage? Shutdown the system to protect it from damage. Power restored and stable? Wake it up again.

## Features
- Systems status monitoring (up/down)
- UPS status and battery charge monitoring via NUT server
- Automatic system wake-up using WOL
- Automatic system shutdown via SSH
- Automatic system wake-up after power restoration
- Configurable via a YAML configuration file

## Supported OS:
- Linux

## Software requirements (if running directly on the host, not in a container)

- python3
- nut-server (if using UPS monitoring)
- ssh (if using UPS monitoring)

## Installation

#### 1. As a docker container
The docker image is available at `ghcr.io/septi0/sentinel-hl:latest`. It can be deployed using any tool, just make sure that the network is set to host and the configuration folder is mounted to `/config` inside the container with a `config.yml` file inside it and provide a volume or bind mount for the SSH keys (if using UPS monitoring functionality) mounted to `/ssh_keys` inside the container. The container runs the script as a daemon, but optionally you can pass alternative commands to do other tasks like clearing the cache, acknowledging hosts, etc.

SSH keys will be automatically generated if they are not present in the `/ssh_keys` folder.

**Note:** the `network=host` mode is required for the WOL functionality to work properly, as it needs to send magic packets to the network.

Quick start docker run command:
```bash
docker run -d \
  --name sentinel-hl \
  --restart unless-stopped \
  --volume /path/to/config/folder:/config \
  --volume /path/to/persist/ssh/keys:/ssh_keys \
  --network host \
  ghcr.io/septi0/sentinel-hl:latest
```

Docker compose:
```yaml
services:
  sentinel-hl:
    image: ghcr.io/septi0/sentinel-hl:latest
    container_name: sentinel-hl
    restart: unless-stopped
    volumes:
      - ./config:/config
      - ./ssh_keys:/ssh_keys
    network_mode: host
```

#### 2. As a package

```
pip install --upgrade git+https://github.com/septi0/sentinel-hl.git
```

or 

```
git clone https://github.com/septi0/sentinel-hl.git
cd sentinel-hl
pip install .
```

#### 3. As a standalone script

```
git clone https://github.com/septi0/sentinel-hl.git
cd sentinel-hl
pip install -r requirements.txt
```

The recommended way to install Sentinel-Hl is as a docker container.

## Usage

#### 1. As a docker container

```
docker exec -it sentinel-hl run <parameters>
```

**Note!** `run` is just an alias for `sentinel-hl` command inside the container, so you can use it as a shortcut to run software specific commands.

#### 2. As a package (if installed globally)

```
/usr/bin/sentinel-hl <parameters>
```

#### 3. As a package (if installed in a virtualenv)

```
<path-to-venv>/bin/sentinel-hl <parameters>
```

#### 4. As a standalone script

```
<git-clone-dir>/run.py <parameters>
```

Check "Command line arguments" section for more information about the available parameters.

## Command line arguments

```
usage: sentinel-hl [-h] [--config CONFIG_FILE] [--log LOG_FILE] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--version] {daemon,daemon-reload,clear-cache,ack,clear-ack} ...

options:
  -h, --help            show this help message and exit
  --config CONFIG_FILE  Alternative config file
  --log LOG_FILE        Log file where to write logs
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Log level
  --version             show program's version number and exit

Commands:
  {daemon,daemon-reload,clear-cache,ack,clear-ack}
    daemon              Run as daemon
    daemon-reload       Reload running daemon
    clear-cache         Clear cache
    ack                 Acknowledge host down
    clear-ack           Clear acknowledged host
```

## Configuration file

For a sample configuration file see `config.sample.yml` file. Aditionally, you can copy the file to `/etc/sentinel-hl/config.yml`, `/etc/opt/sentinel-hl/config.yml` or `~/.config/sentinel-hl/config.yml` (or where you want as long as you provide the `--config` parameter) and adjust the values to your needs.

For details on how to configure the file, see the `config.sample.yml` file.

## Systemd service

To run Sentinel-Hl as a service, have it start on boot and restart on failure, create a systemd service file in `/etc/systemd/system/sentinel-hl.service` and copy the content from `sentinel-hl.sample.service` file, adjusting the `ExecStart` parameter based on the installation method.

After that, run the following commands:

```
systemctl daemon-reload
systemctl enable sentinel-hl.service
systemctl start sentinel-hl.service
```

## Disclaimer

This software is provided as is, without any warranty. Use at your own risk. The author is not responsible for any damage caused by this software.

## License

This software is licensed under the GNU GPL v3 license. See the LICENSE file for more information.