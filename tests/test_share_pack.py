# Unit tests for share pack creation and loading.
# These cover the parts that need no MTGA install, no Unity bundles, and no GUI.

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from src.share_pack import (
    collect_pack_art_ids,
    export_pack,
    filter_changes_for_art_ids,
    find_colliding_image_names,
    get_swapped_images_directory,
    image_filename_for,
    normalize_art_id,
    parse_image_filename,
    read_pack,
    record_swapped_image,
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


def test_filter_normalizes_the_art_ids_it_is_given():
    # An unpadded or int member must still match, or cards silently vanish
    # from the pack instead of failing loudly.
    changes = {"100119": {"ArtId": "001234", "Tags": ""}}
    assert filter_changes_for_art_ids(changes, {"1234"}) == changes
    assert filter_changes_for_art_ids(changes, {1234}) == changes


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


def test_get_swapped_images_directory_creates_it(tmp_path):
    images_directory = get_swapped_images_directory(tmp_path)
    assert images_directory == tmp_path / "swapped_images"
    assert images_directory.is_dir()


def test_record_copies_a_png_verbatim(tmp_path):
    source = tmp_path / "my-art.png"
    source.write_bytes(b"pretend-png-bytes")
    images_directory = get_swapped_images_directory(tmp_path)

    destination = record_swapped_image(source, "1234", 0, images_directory)

    assert destination.name == "001234.png"
    assert destination.read_bytes() == b"pretend-png-bytes"


def test_record_converts_a_non_png_source(tmp_path):
    source = tmp_path / "my-art.bmp"
    Image.new("RGB", (2, 2), "red").save(source)
    images_directory = get_swapped_images_directory(tmp_path)

    destination = record_swapped_image(source, "123456", 1, images_directory)

    assert destination.name == "123456_1.png"
    with Image.open(destination) as saved_image:
        assert saved_image.format == "PNG"


def test_record_overwrites_a_previous_swap_of_the_same_texture(tmp_path):
    images_directory = get_swapped_images_directory(tmp_path)
    first = tmp_path / "first.png"
    first.write_bytes(b"first")
    second = tmp_path / "second.png"
    second.write_bytes(b"second")

    record_swapped_image(first, "123456", 0, images_directory)
    destination = record_swapped_image(second, "123456", 0, images_directory)

    assert destination.read_bytes() == b"second"
    assert len(list(images_directory.iterdir())) == 1


def test_collect_art_ids_ignores_stray_files(tmp_path):
    images_directory = get_swapped_images_directory(tmp_path)
    (images_directory / "123456.png").write_bytes(b"x")
    (images_directory / "654321_2.png").write_bytes(b"x")
    (images_directory / "notes.txt").write_text("ignore me")

    assert collect_pack_art_ids(images_directory) == {"123456", "654321"}


def test_collect_art_ids_on_a_missing_directory_is_empty(tmp_path):
    assert collect_pack_art_ids(tmp_path / "nope") == set()


def test_find_colliding_image_names(tmp_path):
    images_directory = get_swapped_images_directory(tmp_path)
    (images_directory / "123456.png").write_bytes(b"mine")
    pack_images = [Path("/pack/123456.png"), Path("/pack/654321.png")]

    assert find_colliding_image_names(pack_images, images_directory) == ["123456.png"]


def test_export_writes_the_changes_file_and_every_image(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()
    (images_directory / "123456.png").write_bytes(b"art-one")
    (images_directory / "654321_2.png").write_bytes(b"art-two")
    zip_path = tmp_path / "pack.zip"

    image_count, card_count = export_pack(zip_path, {"100119": {"ArtId": "123456"}}, images_directory)

    assert (image_count, card_count) == (2, 1)
    with zipfile.ZipFile(zip_path) as pack_file:
        assert sorted(pack_file.namelist()) == [
            "exported_changes.json",
            "images/123456.png",
            "images/654321_2.png",
        ]
        assert pack_file.read("images/123456.png") == b"art-one"
        assert json.loads(pack_file.read("exported_changes.json")) == {"100119": {"ArtId": "123456"}}


def test_export_leaves_stray_files_out_of_the_pack(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()
    (images_directory / "123456.png").write_bytes(b"art")
    (images_directory / "notes.txt").write_text("ignore me")

    image_count, _ = export_pack(tmp_path / "pack.zip", {}, images_directory)

    assert image_count == 1
    with zipfile.ZipFile(tmp_path / "pack.zip") as pack_file:
        assert "images/notes.txt" not in pack_file.namelist()


def test_export_does_not_count_crops_as_a_card(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()
    changes = {"100119": {"ArtId": "123456"}, "crops": {"123456": []}}

    _, card_count = export_pack(tmp_path / "pack.zip", changes, images_directory)

    assert card_count == 1


def test_export_always_writes_the_changes_member_even_when_empty(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()

    export_pack(tmp_path / "pack.zip", {}, images_directory)

    with zipfile.ZipFile(tmp_path / "pack.zip") as pack_file:
        assert json.loads(pack_file.read("exported_changes.json")) == {}


def test_read_pack_round_trips_an_export(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()
    (images_directory / "123456.png").write_bytes(b"art-one")
    zip_path = tmp_path / "pack.zip"
    export_pack(zip_path, {"100119": {"ArtId": "123456"}}, images_directory)

    pack = read_pack(zip_path)
    try:
        assert [path.name for path in pack.image_paths] == ["123456.png"]
        assert pack.image_paths[0].read_bytes() == b"art-one"
        assert json.loads(pack.changes_path.read_text()) == {"100119": {"ArtId": "123456"}}
    finally:
        pack.cleanup()


def test_cleanup_removes_the_extraction_directory(tmp_path):
    images_directory = tmp_path / "images_source"
    images_directory.mkdir()
    export_pack(tmp_path / "pack.zip", {}, images_directory)

    pack = read_pack(tmp_path / "pack.zip")
    extraction_directory = pack.extraction_directory
    pack.cleanup()

    assert not extraction_directory.exists()


def test_read_pack_rejects_a_zip_with_no_known_members(tmp_path):
    zip_path = tmp_path / "random.zip"
    with zipfile.ZipFile(zip_path, "w") as pack_file:
        pack_file.writestr("holiday-photo.jpg", b"not a pack")

    with pytest.raises(ValueError):
        read_pack(zip_path)


def test_read_pack_ignores_path_traversal_and_absolute_members(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("../evil.png", b"escape")
        pack_file.writestr("images/../../evil.png", b"escape")
        pack_file.writestr("/tmp/evil.png", b"escape")
        pack_file.writestr("images/nested/evil.png", b"escape")

    pack = read_pack(zip_path)
    try:
        assert pack.image_paths == []
        assert list(pack.extraction_directory.rglob("evil.png")) == []
        # Where a successful "../evil.png" escape would actually land.
        assert not (pack.extraction_directory.parent / "evil.png").exists()
    finally:
        pack.cleanup()


def test_read_pack_ignores_non_image_members_under_images(tmp_path):
    zip_path = tmp_path / "pack.zip"
    with zipfile.ZipFile(zip_path, "w") as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("images/readme.txt", b"nope")

    pack = read_pack(zip_path)
    try:
        assert pack.image_paths == []
    finally:
        pack.cleanup()


def test_read_pack_rejects_windows_drive_relative_members(tmp_path):
    # "images/D:123456.png" would otherwise validate -- os.path.basename strips the
    # "D:" so it parses as ArtId 123456 -- and then re-anchor the write to
    # D:\123456.png, outside the extraction directory.
    zip_path = tmp_path / "drive.zip"
    with zipfile.ZipFile(zip_path, "w") as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("images/D:123456.png", b"escape")
        pack_file.writestr("images/C:123456.png", b"escape")

    pack = read_pack(zip_path)
    try:
        assert pack.image_paths == []
    finally:
        pack.cleanup()


def test_read_pack_ignores_duplicate_image_members(tmp_path):
    zip_path = tmp_path / "dupes.zip"
    with zipfile.ZipFile(zip_path, "w") as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("images/123456.png", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            pack_file.writestr("images/123456.png", b"second")

    pack = read_pack(zip_path)
    try:
        assert len(pack.image_paths) == 1
    finally:
        pack.cleanup()
