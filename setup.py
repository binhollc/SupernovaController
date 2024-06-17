import os
from setuptools import setup, find_packages

# Read GH_TOKEN from environment variables
gh_token = os.environ.get('GH_TOKEN')

dev_dependencies = []

if gh_token:
    dev_dependencies.append(f'binhosimulators @ git+https://{gh_token}@github.com/binhollc/BinhoSimulators.git@v0.2.1')

setup(
    name='supernovacontroller',
    version='1.3.0',
    packages=find_packages(),
    data_files=[
        ('lib/site-packages/supernovacontrollerexamples', ['examples/basic_i2c_example.py', 'examples/basic_i3c_example.py', 'examples/i3c_ibi_example.py', 'examples/ICM42605_i3c_example.py', 'examples/basic_i3c_target_example.py',
                               'examples/basic_uart_example.py', 'examples/basic_spi_controller_example.py', 'examples/hot_join_example.py', 'examples/i3c_target_set_ids.py'])
    ],
    description='A blocking API for interacting with the Supernova host-adapter device',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Binho LLC',
    author_email='support@binho.io',
    url='https://github.com/binhollc/SupernovaController',
    license='Private',
    install_requires=[
      'transfer_controller==0.4.0',
      'BinhoSupernova==2.2.0',
    ] + dev_dependencies,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)
