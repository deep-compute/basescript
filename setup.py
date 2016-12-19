from setuptools import setup, find_packages
import os

long_description = ""
rst_readme = os.path.join(
    os.path.dirname(__file__), "README.rst"
)
if os.path.exists(rst_readme):
    with open(rst_readme) as fp:
        long_description = rst_readme.read()

version = '0.1.6'
setup(
    name="basescript",
    version=version,
    description="Basic infrastructure for writing scripts",
    long_description=long_description,
    keywords='basescript',
    author='Deep Compute, LLC',
    author_email="contact@deepcompute.com",
    url="https://github.com/deep-compute/basescript",
    download_url="https://github.com/deep-compute/basescript/tarball/%s" % version,
    license='MIT License',
    install_requires=[
        "structlog",
    ],
    package_dir={'basescript': 'basescript'},
    packages=find_packages('.'),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
    ]
)
