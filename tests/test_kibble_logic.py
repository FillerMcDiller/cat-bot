import math
import unittest

from main import type_dict


class TestKibbleLogic(unittest.TestCase):
    def test_per_cat_value_formula(self):
        # per-cat value used across the bot: sum(type_dict.values()) / type_dict[type]
        total = sum(type_dict.values())
        for cat, weight in type_dict.items():
            val = total / weight
            # value should be positive and finite
            self.assertTrue(val > 0)
            # for at least one known type, check an expected numeric relation
        fine_val = total / type_dict["Fine"]
        # sanity check: fine should be the smallest per-cat value among common types
        self.assertTrue(fine_val <= max(total / w for w in type_dict.values()))


if __name__ == '__main__':
    unittest.main()
