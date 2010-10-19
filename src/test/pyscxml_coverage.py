'''
Created on Dec 7, 2009

@author: johan
'''

import sys
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

StateMachine(open(xmlDir + "colors.xml").read()).start()
time.sleep(1)
StateMachine(open(xmlDir + "twolock_door.xml").read()).start()
time.sleep(1)

cov.stop()
cov.html_report(directory='coverage_output')