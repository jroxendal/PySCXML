'''
Created on Dec 7, 2009

@author: johan
'''

import sys
import unittest

import coverage
import pyscxmlTest
import os, time
from scxml.pyscxml import StateMachine


xmlDir = "../../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"

cov = coverage.coverage()
cov.start()

sm = StateMachine(open(xmlDir + "colors.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "parallel.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "factorial.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "issue_164.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "all_configs.xml").read())
sm.start()
sm.send("a")
sm.send("b")
sm.send("c")
sm.send("d")
sm.send("e")
sm.send("f")
sm.send("g")
sm.send("h")
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "issue_626.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "twolock_door.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors
'''
sm = StateMachine(open(xmlDir + "xinclude.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors
self.assert_(sm.isFinished())
'''

sm = StateMachine(open(xmlDir + "if_block.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "donedata.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "invoke.xml").read())
sm.start()
time.sleep(1) #lets us avoid asynchronous errors

sm = StateMachine(open(xmlDir + "history.xml").read())
sm.start()
time.sleep(6) #lets us avoid asynchronous errors

cov.stop()
cov.html_report(directory='coverage_output')