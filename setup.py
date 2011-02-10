
from setuptools import setup

version = "0.6.5"
filename = "0.6.5-20110130-full"

setup(name="pyscxml",
      version=filename,
      description="A pure Python SCXML compiler/interpreter",
      author="Johan Roxendal",
      author_email="johan@roxendal.com",
      url="http://code.google.com/p/pyscxml/",
      
      packages=["scxml"],
      package_dir={"" : "src"},
      license="LGPLv3",
      install_requires=['Louie', 'Cheetah', 'suds', 'eventlet']
     )
