from setuptools import setup, find_packages
import os

HERE = os.path.abspath(os.path.dirname(__file__))

long_description = ""

rst_readme = os.path.join(HERE, "README.rst")
rst_readme = os.path.join(
    os.path.dirname(__file__), "README.rst"
)
if os.path.exists(rst_readme):
    print "found rst file %s" % rst_readme
    with open(rst_readme) as fp:
        long_description = rst_readme.read()
else:
    print "could not find rst file %s" % rst_readme

version = '0.1.7'
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
        "colorama",
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
