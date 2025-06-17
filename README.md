# Sentinel-Hl

## Description

**Sentinel-Hl** is ...

## Features


## Software requirements

- python3

## Installation

#### 1. As a package

```
pip install --upgrade <git-repo>
```

or 

```
git clone <git-repo>
cd <git-repo>
python setup.py install
```

#### 2. As a standalone script

```
git clone <git-repo>
```

## Usage

Sentinel-Hl can be used in 3 ways:

#### 1. As a package (if installed globally)

```
/usr/bin/sentinel-hl <parameters>
```

#### 2. As a package (if installed in a virtualenv)

```
<path-to-venv>/bin/sentinel-hl <parameters>
```

#### 3. As a standalone script

```
<git-clone-dir>/run.py <parameters>
```

Check "Command line arguments" section for more information about the available parameters.

## Command line arguments

```
sentinel-hl [-h] 
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