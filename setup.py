from setuptools import setup, find_packages
import os

HERE = os.path.abspath(os.path.dirname(__file__))
long_description = ""
def get_long_description():
    dirs = [ HERE ]
    if os.getenv("TRAVIS"):
        dirs.append(os.getenv("TRAVIS_BUILD_DIR"))

    for d in dirs:
        rst_readme = os.path.join(d, "README.rst")
        if not os.path.exists(rst_readme):
            print "failed to find %s" % rst_readme
            continue

        print "found rst readme %s" % rst_readme
        with open(rst_readme) as fp:
            long_description = rst_readme.read()

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
