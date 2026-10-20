import numpy as np
import pandas as pd
import pytest

from heart_risk.schema import FEATURES


@pytest.fixture
def sample_frame():
    random = np.random.default_rng(42)
    rows = []
    for index in range(40):
        rows.append(
            [
                35 + index,
                index % 2,
                1 + index % 4,
                110 + index,
                180 + index,
                index % 2,
                index % 3,
                120 + index,
                index % 2,
                float(random.uniform(0, 4)),
                1 + index % 3,
                np.nan if index % 8 == 0 else index % 4,
                np.nan if index % 9 == 0 else [3, 6, 7][index % 3],
            ]
        )
    frame = pd.DataFrame(rows, columns=FEATURES)
    frame["target"] = [index % 2 for index in range(40)]
    return frame
