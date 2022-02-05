import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="beholder-email", # Replace with your own username
    version="0.0.1",
    author="Jack Terwilliger",
    author_email="jack.f.terwilliger@gmail.com",
    description="Sends an email when the device turns on",
    long_description=long_description,
    long_description_content_type="text/markdown",
    #url="https://github.com/pypa/sampleproject",
    packages=[
        "beholder.email"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    package_data={
        "beholder.email": ["py.typed"]
    },
    python_requires='>=3.8',
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)