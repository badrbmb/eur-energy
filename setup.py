from distutils.util import convert_path

from setuptools import setup, find_packages

# load long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# load version
main_ns = {}
ver_path = convert_path('version.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

setup(
    name='eur-energy',
    version=main_ns['__version__'],
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4==4.11.1",
        "pandas==1.2.4",
        "plotly==5.8.0",
        "pycountry==22.3.5",
        "millify==0.1.1",
        "requests==2.27.1",
        "tqdm==4.64.1"
    ],
    python_requires=">=3.9",
    include_package_data=True,
    package_data={
        "eur_energy": [
            "data/schema"
        ]
    },
    author="Badr Ben m'barek",
    author_email='badr.benb@gmail.com',
    description='Explore decomposition of the European energy consumption of specific processes and end-uses',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
