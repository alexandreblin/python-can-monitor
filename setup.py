import os.path
import re

import setuptools


def get_version():
    # When some variables are defined in the dunder init of a project, import of version.py can lead to circular
    # dependencies. As a workaround, this function reads the file version.py to get the package version.
    with open(os.path.join(os.path.dirname(__file__), 'canmonitor', 'version.py')) as f:
        regex = re.compile("^VERSION = '(.*?)'$", re.MULTILINE)
        return regex.search(f.read()).group(1)


setuptools.setup(
    name="canmonitor",
    version=get_version(),
    description="Read CAN frames and display them in an easy-to-read table",
    packages=setuptools.find_packages(exclude=['tests*']),
    python_requires='>=3.4',
    entry_points={
        'console_scripts': [
            'canmonitor = canmonitor.canmonitor:run',
        ],
    },
    install_requires=[
        'pyserial==3.2.1',
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Topic :: Scientific/Engineering :: Visualization",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    keywords=['can', 'can bus', 'automotive'],
)
