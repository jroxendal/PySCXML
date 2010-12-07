
from setuptools import setup
import datetime

version = "0.5.8"
filename = version + "-" + str(datetime.date.today()).replace("-", "")

setup(name="pyscxml",
      version=filename,
      description="A pure Python SCXML compiler/interpreter",
      author="Johan Roxendal",
      author_email="johan@roxendal.com",
      url="http://code.google.com/p/pyscxml/",
      
      packages=["scxml"],
      package_dir={"" : "src"},
      license="LGPLv3",
      install_requires=["Louie", "suds"]
     )
