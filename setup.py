from setuptools import setup, find_packages

setup(
    name="mothership",
    version="1.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    description="A set of scripts for trying to get tickets to Mothership",
    author="Your Name",
    author_email="your@email.com",
)
