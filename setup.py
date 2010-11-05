'''
Created on Nov 26, 2009

@author: Johan Roxendal
'''

from setuptools import setup
import datetime

setup(name='pyscxml',
      version='0.5.1-' + str(datetime.date.today()).replace("-", ""),
      description='A pure Python SCXML compiler/interpreter',
      author='Johan Roxendal',
      author_email='johan@roxendal.com',
      url='http://code.google.com/p/pyscxml/',
      
      packages=['scxml'],
      package_dir={'' : "src"},
      license="LGPLv3",
      install_requires=["Louie", "suds"]
     )

