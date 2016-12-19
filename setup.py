from setuptools import setup, find_packages

long_description = ""
try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst', format='markdown_github')
except:
    print """
    README.md could not be converted to rst format.
    Make sure pypandoc is installed.
    """

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
