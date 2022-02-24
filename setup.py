from setuptools import setup, find_packages

# pip -e install .
# without that relative imports (and whole script) won't work
setup(name='lab8', version='1.0', packages=find_packages())
