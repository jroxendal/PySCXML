from scxml.pyscxml import StateMachine
import logging
import os
os.chdir("assertions_all/failed")
logging.basicConfig(level=logging.NOTSET)

nextFile = filter(lambda x: x.endswith("xml"), os.listdir("."))[0]

xml = open(nextFile).read()

sm = StateMachine(xml)
sm.start()

