from unittest.mock import patch

import pytest

from heart_risk.data import clean_data, create_split, download_raw, sha256

ROW = "63,1,1,145,233,1,2,150,0,2.3,3,0,6,0"


def test_cleaning_duplicates_and_missing():
    frame = clean_data(ROW + "\n" + ROW + "\n" + ROW.replace(",0,6,0", ",?,?,1"))
    assert len(frame) == 2
    assert frame.ca.isna().sum() == 1
    assert frame.target.tolist() == [0, 1]


def test_conflicting_duplicates_fail():
    with pytest.raises(ValueError, match="conflicting"):
        clean_data(ROW + "\n" + ROW[:-1] + "1")


@pytest.mark.parametrize("text", ["", "garbage", ROW.replace("145", "NaN")])
def test_invalid_data_fails(text):
    with pytest.raises(ValueError):
        clean_data(text)


def test_split_is_disjoint_complete_and_deterministic(sample_frame):
    split = create_split(sample_frame, 42, 0.2)
    assert split == create_split(sample_frame, 42, 0.2)
    assert not set(split["train_indices"]) & set(split["test_indices"])
    assert sorted(split["train_indices"] + split["test_indices"]) == list(range(40))
    assert sample_frame.iloc[split["test_indices"]].target.nunique() == 2


def test_cached_download_requires_checksum(tmp_path):
    raw = tmp_path / "cleveland.data"
    raw.write_text(ROW)
    with pytest.raises(ValueError, match="checksum"):
        download_raw(raw)
    raw.with_suffix(".sha256").write_text(sha256(raw))
    with patch("urllib.request.urlopen", side_effect=AssertionError("No network allowed")):
        assert download_raw(raw) == raw
    raw.write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        download_raw(raw)


def test_network_failure_does_not_create_fake_data(tmp_path):
    with patch("urllib.request.urlopen", side_effect=OSError("offline")):
        with pytest.raises(OSError):
            download_raw(tmp_path / "cleveland.data")
    assert not list(tmp_path.iterdir())
