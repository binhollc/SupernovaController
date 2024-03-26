import os
from setuptools import setup, find_packages

# Read GH_TOKEN from environment variables // Remove when transfer_controller v0.3.0 is approved
gh_token = os.environ.get('GH_TOKEN')

setup(
    name='supernovacontroller',
    version='1.3.0',
    packages=find_packages(),
    data_files=[
        ('SupernovaExamples', ['examples/basic_i2c_example.py', 'examples/basic_i3c_example.py', 'examples/hot_join_example.py', 'examples/ibi_example.py', 'examples/ICM42605_i3c_example.py', 'examples/basic_i3c_target_example.py'])
    ],
    description='A blocking API for interacting with the Supernova host-adapter device',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Binho LLC',
    author_email='support@binho.io',
    url='https://github.com/binhollc/SupernovaController',
    license='Private',
    install_requires=[
      'transfer_controller==0.3.1',
      'BinhoSupernova==2.0.1',
      f'binhosimulators @ git+https://{gh_token}@github.com/binhollc/BinhoSimulators.git@v0.1.0'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.5',
)
