from setuptools import setup, find_packages

setup(
    name="basescript",
    version='0.1',
    description="Basic infrastructure for writing scripts",
    keywords='basescript',
    author='Prashanth Ellina',
    author_email="Use the github issues",
    url="https://github.com/deep-compute/basescript",
    license='MIT License',
    install_requires=[
    ],
    package_dir={'basescript': 'basescript'},
    packages=find_packages('.'),
    include_package_data=True
)
