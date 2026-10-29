import unittest
from firstlight_decision.stats import paired_bootstrap,exact_discordance_p
class StatisticalTests(unittest.TestCase):
 def test_all_tied_no_false_significance(self):self.assertEqual(exact_discordance_p(0,0),1.0)
 def test_one_each_no_significance(self):self.assertEqual(exact_discordance_p(1,1),1.0)
 def test_large_improvement_can_be_significant(self):self.assertLess(exact_discordance_p(10,0),0.05)
 def test_bootstrap_tied(self):
  x=paired_bootstrap([0]*24);self.assertEqual((x['low_95'],x['high_95']),(0,0))
 def test_bootstrap_repeatable(self):
  self.assertEqual(paired_bootstrap([1,-1,0,2]),paired_bootstrap([1,-1,0,2]))
 def test_empty_is_missing_not_zero(self):self.assertIsNone(paired_bootstrap([]))
if __name__=='__main__':unittest.main()
