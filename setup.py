from setuptools import setup, find_packages

setup(
    name="soplos-sys-cleaner",
    version="1.0.3-2",
    packages=find_packages(),
    install_requires=[
        'PyGObject>=3.40.0',
        'psutil>=5.8.0'
    ],
    entry_points={
        'console_scripts': [
            'soplos-sys-cleaner=main:main',
        ],
    },
    author="Sergi Perich",
    author_email="info@soploslinux.com",
    description="Advanced system cleaner and optimizer for Soplos Linux",
    license="GPL-3.0",
)
