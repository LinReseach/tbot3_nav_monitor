# In: src/tbot3_nav_monitor/setup.py
from setuptools import setup
import os
from glob import glob

package_name = 'tbot3_nav_monitor'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    # Console scripts reference modules under the Python package directory.
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.world')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*.yaml')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*.pgm')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='your@email.com',
    description='TurtleBot3 Navigation Performance Monitor',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'performance_monitor = tbot3_nav_monitor.performance_monitor:main',
            'adaptive_controller = tbot3_nav_monitor.adaptive_controller:main',
            'data_logger = tbot3_nav_monitor.data_logger:main',
        ],
    },
)