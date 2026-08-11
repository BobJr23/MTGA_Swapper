# Tests for the AssetBundle CRC restoration that keeps MTGA willing to load swapped art.
# Real .mtga bundles are not in the repo, so these cover the filename contract, the CRC
# solver, and the scan behaviour -- the parts that decide whether a bundle gets touched.

import zlib

import pytest

from src.bundle_crc import (
    PATCH_BYTES,
    expected_crc_for,
    scan_and_repair,
    solve_crc_patch,
    verify_bundle_crc,
)

CARD_ART_NAME = "434585_CardArt_89f11d38-bef421b0105f753d63db6d910c111a3c.mtga"


def test_expected_crc_reads_the_crc_group_from_a_card_art_name():
    # The manifest's "crc" field matched this filename group for all 27318 AssetBundle
    # entries, which is why the manifest never has to be opened.
    assert expected_crc_for(CARD_ART_NAME) == 0x89F11D38


def test_expected_crc_survives_the_mod_backup_prefix():
    # change_grp_id restores MOD_ backups, and those have to be verifiable too.
    assert expected_crc_for(f"MOD_{CARD_ART_NAME}") == 0x89F11D38


def test_expected_crc_accepts_a_full_path():
    full_path = rf"C:\Program Files\MTGA\MTGA_Data\Downloads\AssetBundle\{CARD_ART_NAME}"
    assert expected_crc_for(full_path) == 0x89F11D38


def test_expected_crc_is_case_insensitive():
    assert expected_crc_for(CARD_ART_NAME.upper().replace(".MTGA", ".mtga")) == 0x89F11D38


@pytest.mark.parametrize(
    "filename",
    [
        # ALT_/Raw_ bundles carry a single hash and no crc in the manifest.
        "ALT_Card_ade8907f6a02cd4b469ba85756e75362.mtga",
        "Raw_ArtCropDatabase_4654b71a4035925c0f972278859206ed.mtga",
        "Manifest_d37592d6114d02e688822cba97a028a0.mtga",
        # Audio packs are listed with crc: null.
        "AFR_9267b12b73f8f5ff6a329239e6537a12.pck",
        # The asset editor also writes this, and it is not a manifest bundle at all.
        "resources.assets",
        # Groups of the wrong length must not be mistaken for a CRC.
        "434585_CardArt_89f11d3-bef421b0105f753d63db6d910c111a3c.mtga",
        "434585_CardArt_89f11d38-bef421b0105f753d63db6d910c111a3.mtga",
    ],
)
def test_expected_crc_is_none_for_bundles_the_game_does_not_crc_check(filename):
    # Returning None is what keeps these files from being patched needlessly.
    assert expected_crc_for(filename) is None


@pytest.mark.parametrize(
    "prefix, suffix",
    [
        (b"", b""),
        (b"header", b""),
        (b"", b"trailer"),
        (b"header", b"trailer"),
        (bytes(range(256)) * 8, bytes(range(255, -1, -1)) * 8),
    ],
)
@pytest.mark.parametrize("target", [0x00000000, 0x89F11D38, 0xFFFFFFFF, 0x2FC74949])
def test_solve_crc_patch_hits_the_target_exactly(prefix, suffix, target):
    patch = solve_crc_patch(prefix, suffix, target)
    assert len(patch) == PATCH_BYTES
    assert zlib.crc32(prefix + patch + suffix) & 0xFFFFFFFF == target


def test_solve_crc_patch_is_deterministic():
    first = solve_crc_patch(b"abc", b"def", 0x12345678)
    second = solve_crc_patch(b"abc", b"def", 0x12345678)
    assert first == second


def test_verify_reports_ok_for_a_bundle_with_no_crc_in_its_name(tmp_path):
    not_checked = tmp_path / "ALT_Card_ade8907f6a02cd4b469ba85756e75362.mtga"
    not_checked.write_bytes(b"not a crc checked bundle")

    is_valid, detail = verify_bundle_crc(not_checked)

    assert is_valid
    assert "not CRC-checked" in detail


def test_verify_reports_failure_when_a_crc_named_bundle_cannot_be_read(tmp_path):
    unreadable = tmp_path / CARD_ART_NAME
    unreadable.write_bytes(b"not a unity bundle")

    is_valid, detail = verify_bundle_crc(unreadable)

    assert not is_valid
    assert "could not be read" in detail


def test_scan_skips_files_the_game_does_not_crc_check(tmp_path):
    (tmp_path / "ALT_Card_ade8907f6a02cd4b469ba85756e75362.mtga").write_bytes(b"skip me")
    (tmp_path / "Raw_credits_544110d95d8d4832bbbf6baea321145c.mtga").write_bytes(b"skip")

    checked, repaired, messages = scan_and_repair([tmp_path])

    assert (checked, repaired, messages) == (0, 0, [])


def test_scan_counts_and_reports_a_crc_checked_bundle_it_cannot_validate(tmp_path):
    (tmp_path / CARD_ART_NAME).write_bytes(b"not a unity bundle")

    checked, repaired, messages = scan_and_repair([tmp_path])

    assert checked == 1
    assert repaired == 0
    assert len(messages) == 1


def test_scan_accepts_a_single_file_target(tmp_path):
    bundle_path = tmp_path / CARD_ART_NAME
    bundle_path.write_bytes(b"not a unity bundle")

    checked, _, _ = scan_and_repair([bundle_path])

    assert checked == 1


def test_scan_repair_reports_a_failure_instead_of_raising(tmp_path):
    # A file that cannot be parsed must be reported, not allowed to abort the sweep.
    (tmp_path / CARD_ART_NAME).write_bytes(b"not a unity bundle")

    checked, repaired, messages = scan_and_repair([tmp_path], repair=True)

    assert checked == 1
    assert repaired == 0
    assert "repair failed" in messages[0]
