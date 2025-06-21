import os

__app_name__ = "Sentinel-Hl"
__package_name__ = "sentinel-hl"

with open(os.path.join(os.path.dirname(__file__), "VERSION"), "r") as version_file:
    __version__ = version_file.read().strip()

__description__ = "A simple tool that watches over your infrastructure and ensures that all systems are running."
__author__ = "Septimiu Ujica"
__author_email__ = "hellp@septi.ro"
__author_url__ = "https://www.septi.ro"
__license__ = "GPLv3"