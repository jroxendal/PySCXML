'''
Created on Nov 19, 2009

@author: johan
'''

import unittest
from scxml.compiler import Compiler
from xml.etree import ElementTree as etree
from os import listdir

class CompilerTest(unittest.TestCase):
    
    
    def testCompiler(self):
        
        xmlDir = "../../../unitest_xml/"
        for xmlDoc in listdir(xmlDir):
            xml = open(xmlDir + xmlDoc).read()

            compiler = Compiler()
            doc = compiler.parseXML(xml)
            
            # make sure that the amount of states stored in the stateDict in the parsed document equals
            # the amount of xml nodes of the same types.
            self.assertEqual(len(doc.stateDict.keys()),
                len(list(state for state in etree.fromstring(xml).getiterator() if state.tag in ["state", "parallel", "final", "history", "scxml"]))
            )
            
        
    
    
if __name__ == '__main__':
    unittest.main()
#    CompilerTest().testCompiler()