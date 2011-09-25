
from setuptools import setup

version = "0.7.3"
filename = "0.7.3-20110922-full"

setup(name="pyscxml",
      version=filename,
      description="A pure Python SCXML parser/interpreter",
      long_description="Use PySCXML to parse and execute an SCXML document. PySCXML aims for full compliance with the W3C standard. Features include but are not limited to multisession support, HTTP serving with easily configured REST service configuration and complete HTTP IO processor.",
      author="Johan Roxendal",
      author_email="johan@roxendal.com",
      url="http://code.google.com/p/pyscxml/",
      download_url="http://code.google.com/p/pyscxml/downloads/list?q=full",
      packages=["scxml"],
      package_dir={"" : "src"},
      license="LGPLv3",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Communications :: Telephony',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: WSGI',
          'Topic :: Software Development :: Interpreters',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Processing :: Markup :: XML'
          
      ],
      install_requires=['Louie', 'Cheetah', 'suds', 'eventlet', 'restlib']
     )
