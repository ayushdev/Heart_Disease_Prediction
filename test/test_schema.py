import unittest

from heart_risk.schema import FEATURES, parse_row, validate_features


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.row = "63,1,1,145,233,1,2,150,0,2.3,3,0,6,0".split(",")

    def test_target_mapping(self):
        for severity in range(5):
            self.row[-1] = str(severity)
            self.assertEqual(parse_row(self.row)["target"], int(severity > 0))

    def test_missing_values_are_not_imputed(self):
        self.row[11:13] = ["?", "?"]
        result = parse_row(self.row)
        self.assertIsNone(result["ca"])
        self.assertIsNone(result["thal"])

    def test_wrong_columns_and_labels_fail(self):
        with self.assertRaises(ValueError):
            parse_row(self.row[:-1])
        self.row[-1] = "5"
        with self.assertRaises(ValueError):
            parse_row(self.row)

    def test_invalid_category_and_missing_numeric_fail(self):
        for index, value in [(12, "0"), (0, "?"), (1, "2"), (3, "inf")]:
            row = self.row.copy()
            row[index] = value
            with self.assertRaises(ValueError):
                parse_row(row)

    def test_target_is_never_a_feature(self):
        record = parse_row(self.row)
        with self.assertRaises(ValueError):
            validate_features(record)
        self.assertEqual(list(validate_features({key: record[key] for key in FEATURES})), FEATURES)
