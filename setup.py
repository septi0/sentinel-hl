from setuptools import setup

# import sentinel_hl.info without importing the package
info = {}

with open("sentinel_hl/info.py") as fp:
    exec(fp.read(), info)

version = ''
with open("sentinel_hl/VERSION", "r") as f:
    version = f.read().strip()

with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f]

setup(
    name=info['__package_name__'],
    version=version,
    description=info['__description__'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    license=info['__license__'],
    author=info['__author__'],
    author_email=info['__author_email__'],
    author_url=info['__author_url__'],
    python_requires='>=3.10',
    install_requires=requirements,
    packages=[
        'sentinel_hl',
        'sentinel_hl.libraries',
        'sentinel_hl.models',
        'sentinel_hl.services',
        'sentinel_hl.utils',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: Utilities",
    ],
    entry_points={
        'console_scripts': [
            'sentinel-hl = sentinel_hl:main',
        ],
    },
    include_package_data=True,
    package_data={
        'sentinel_hl': [
            'VERSION',
        ],
    },
)