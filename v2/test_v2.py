import unittest

import torch

from v2.attribution import (
    calibrated_anomaly_score,
    integrated_gradients,
)
from v2.model import create_v2_model


class V2ModelTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.model = create_v2_model()
        self.model.max_rul = 542.0
        self.model.eval()

    def test_multitask_shapes(self):
        output = self.model(
            torch.randn(4, 30, 34), torch.tensor([0, 1, 4, 5])
        )
        self.assertEqual(output["rul"].shape, (4, 1))
        self.assertEqual(output["anomaly_distance"].shape, (4,))
        self.assertEqual(output["latent"].shape, (4, 160))
        self.assertEqual(output["anomaly_latent"].shape, (4, 128))
        self.assertTrue(torch.all(output["rul"] >= 0))

    def test_condition_specific_centers(self):
        centers = torch.zeros(6, 128)
        centers[1] = 1.0
        self.model.set_svdd_centers(centers)
        latent = torch.zeros(2, 128)
        distance = self.model.anomaly_distance(
            latent, torch.tensor([0, 1])
        )
        self.assertAlmostEqual(float(distance[0]), 0.0)
        self.assertAlmostEqual(float(distance[1]), 1.0)

    def test_integrated_gradients_completeness(self):
        x = torch.randn(1, 30, 34)
        baseline = x.clone()
        baseline[:, :, :20] = 0
        _, delta = integrated_gradients(
            self.model, x, 2, baseline, "rul", steps=32
        )
        self.assertLess(abs(delta), 0.2)

    def test_empirical_anomaly_calibration(self):
        calibration = {
            "quantile_levels": [0.0, 0.5, 1.0],
            "distance_quantiles": [[0.0, 1.0, 2.0]] * 6,
        }
        self.assertAlmostEqual(
            calibrated_anomaly_score(1.5, 3, calibration), 0.75
        )


if __name__ == "__main__":
    unittest.main()
