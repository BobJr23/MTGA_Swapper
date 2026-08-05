# Unit tests for share pack creation and loading.
# These cover the parts that need no MTGA install, no Unity bundles, and no GUI.

import pytest

from src.share_pack import (
    filter_changes_for_art_ids,
    image_filename_for,
    normalize_art_id,
    parse_image_filename,
)


def test_texture_zero_uses_a_bare_art_id_filename():
    assert image_filename_for("123456", 0) == "123456.png"


def test_nonzero_texture_index_gets_a_suffix():
    assert image_filename_for("654321", 2) == "654321_2.png"


def test_short_art_ids_are_zero_padded_to_six_digits():
    assert normalize_art_id("1234") == "001234"
    assert normalize_art_id(1234) == "001234"
    assert image_filename_for("1234", 0) == "001234.png"


def test_long_art_ids_are_left_alone():
    assert normalize_art_id("1234567") == "1234567"


def test_short_art_id_does_not_prefix_match_a_longer_one():
    # Bundle lookup is filename.startswith(art_id). Unpadded, "1234" matches
    # 123456_CardArt_*.mtga and would swap a completely different card's art.
    art_id, _ = parse_image_filename(image_filename_for("1234", 0))
    assert art_id == "001234"
    assert not "123456_CardArt_x.mtga".startswith(art_id)


@pytest.mark.parametrize("art_id,texture_index", [("123456", 0), ("123456", 3), ("001234", 0)])
def test_filenames_round_trip(art_id, texture_index):
    filename = image_filename_for(art_id, texture_index)
    assert parse_image_filename(filename) == (art_id, texture_index)


def test_parse_rejects_files_that_are_not_png():
    assert parse_image_filename("123456.jpg") is None
    assert parse_image_filename("notes.txt") is None


def test_parse_rejects_non_numeric_names_and_indexes():
    assert parse_image_filename("lightning-bolt.png") is None
    assert parse_image_filename("123456_abc.png") is None
    assert parse_image_filename("123_456_2.png") is None


def test_parse_rejects_unicode_digits_that_int_cannot_parse():
    # "²".isdigit() is True but int("²") raises ValueError. A stray file must be
    # skipped, not crash the export that is walking the folder.
    assert parse_image_filename("123456_².png") is None
    assert parse_image_filename("².png") is None


def test_filter_keeps_matching_cards_and_drops_the_rest():
    changes = {
        "100119": {"ArtId": "123456", "Tags": "1696804317"},
        "100120": {"ArtId": "999999", "Tags": ""},
    }
    filtered = filter_changes_for_art_ids(changes, {"123456"})
    assert filtered == {"100119": {"ArtId": "123456", "Tags": "1696804317"}}


def test_filter_matches_art_ids_regardless_of_padding_or_type():
    # save_grp_id_info writes whatever sqlite hands back, which can be an int.
    changes = {"100119": {"ArtId": 1234, "Tags": ""}}
    assert filter_changes_for_art_ids(changes, {"001234"}) == changes


def test_filter_narrows_crops_by_art_id():
    changes = {
        "100119": {"ArtId": "123456"},
        "crops": {
            "123456": [{"path": "a", "format": "b", "x": 0, "y": 0, "z": 1, "w": 1, "generated": 0}],
            "999999": [{"path": "c", "format": "d", "x": 0, "y": 0, "z": 1, "w": 1, "generated": 0}],
        },
    }
    filtered = filter_changes_for_art_ids(changes, {"123456"})
    assert set(filtered["crops"]) == {"123456"}


def test_filter_omits_the_crops_key_when_nothing_matches():
    changes = {"100119": {"ArtId": "123456"}, "crops": {"999999": []}}
    filtered = filter_changes_for_art_ids(changes, {"123456"})
    assert "crops" not in filtered


def test_filter_skips_entries_with_no_art_id():
    changes = {"100119": {"Tags": "1696804317"}}
    assert filter_changes_for_art_ids(changes, {"123456"}) == {}
