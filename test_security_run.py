import sys
from unittest.mock import MagicMock
sys.modules['requests'] = MagicMock()
import unittest
from tests.test_security_timeouts import TestSecurityTimeouts

if __name__ == '__main__':
    unittest.main()
