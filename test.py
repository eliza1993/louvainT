#!usr/bin/python
# -*- coding: utf-8 -*-

import math
import unittest
import MySQLdb
from louvainT import PyLouvain

class PylouvainTest(unittest.TestCase):

    def test_snap(self):
        print "============test_snap=============="
        #pyl = PyLouvain.from_file("data/soc-Epinions1.txt")
        pyl = PyLouvain.from_database("SiteRelation")
        #pyl = PyLouvain.from_file("data/test.txt")
        partition, q = pyl.apply_method()


if __name__ == '__main__':
    unittest.main()
