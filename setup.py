from setuptools import setup, find_packages
import os

HERE = os.path.abspath(os.path.dirname(__file__))
def get_long_description():
    dirs = [ HERE ]
    if os.getenv("TRAVIS"):
        dirs.append(os.getenv("TRAVIS_BUILD_DIR"))

    long_description = ""

    for d in dirs:
        rst_readme = os.path.join(d, "README.rst")
        if not os.path.exists(rst_readme):
            continue

        with open(rst_readme) as fp:
            long_description = fp.read()
            return long_description

    return long_description

long_description = get_long_description()

version = '0.2.2'
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
        "pytz==2018.3",
        "structlog==18.1.0",
        "colorama==0.3.9",
    ],
    package_dir={'basescript': 'basescript'},
    packages=find_packages('.', exclude=['tests*']),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
    ]
)
