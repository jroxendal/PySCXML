'''
Created on Dec 7, 2009

@author: johan
'''

import sys
import unittest

import coverage
import pyscxmlTest
import os, time




xmlDir = "../../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"

cov = coverage.coverage(source=["scxml"])
cov.start()

tst = pyscxmlTest.RegressionTest()

tst.runTest()


cov.stop()
cov.html_report(directory='coverage_output')