from setuptools import setup, find_packages

setup(
    name='stack_generator',
    version='0.5.0',
    packages=find_packages(),
    include_package_data=True,
    entry_points='''
        [console_scripts]
        jinni=stack_modules.jinni:cli
    ''',
    url='',
    license='',
    author='Arthur Freyman',
    author_email='',
    description='CloudFormation Generator',
    install_requires=[
        'Click==6.6', 'boto3==1.4.1', 'troposphere==1.9.0', 'pyyaml==3.12', 'ipaddress==1.0.22', 'awacs==0.7.2'
    ],
)
