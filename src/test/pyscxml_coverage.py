'''
Created on Dec 7, 2009

@author: johan
'''

import sys
import unittest
print sys.version_info
print sys.path

import coverage
import pyscxmlTest
import os, time
from scxml.pyscxml import StateMachine


xmlDir = "../../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"

cov = coverage.coverage()
cov.start()

unittest.makeSuite(pyscxmlTest.RegressionTest)
unittest.main()
#pyscxmlTest.RegressionTest().testInterpreter()


cov.stop()
cov.html_report(directory='coverage_output')