from scxml.pyscxml import StateMachine, default_logfunction
from louie import dispatcher
import logging
import os
#os.chdir("assertions_all/failed")
#os.chdir("assertions_ecma/failed")
#os.chdir("stoplist/failed")
# os.chdir("assertions_xpath/failed")
os.chdir("newer_xpath_tests/failed")

logging.basicConfig(level=logging.NOTSET)

nextFile = filter(lambda x: x.endswith("xml"), os.listdir("."))[0]
xml = open(nextFile).read()
import re
#xml = re.sub("datamodel=.python.", 'datamodel="ecmascript"', xml)
dispatcher.connect(default_logfunction, "invoke_log")
sm = StateMachine(xml)
sm.start()



