import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Clear caches
for m in list(sys.modules.keys()):
    if "server" in m:
        del sys.modules[m]

import unittest
from tests.test_mahjong_logic import *

# Run only failing tests
suite = unittest.TestSuite()
loader = unittest.TestLoader()

# Find all test classes and run
for cls_name in dir():
    cls = eval(cls_name)
    if isinstance(cls, type) and issubclass(cls, unittest.TestCase) and cls != unittest.TestCase:
        suite.addTests(loader.loadTestsFromTestCase(cls))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
