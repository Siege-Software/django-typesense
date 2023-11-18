from setuptools import find_namespace_packages, setup
from django_typesense import __version__

setup(
    name="django_typesense",
    author="Siege Software",
    author_email="info@siege.ai",
    version=__version__,
    install_requires=[
        "django",
        "typesense",
    ],
    setup_requires=["wheel"],
    packages=find_namespace_packages(),
    include_package_data=True,
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    license_files=("LICENSE",),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ]
)
