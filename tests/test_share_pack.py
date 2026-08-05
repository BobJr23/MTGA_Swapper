# Unit tests for share pack creation and loading.
# These cover the parts that need no MTGA install, no Unity bundles, and no GUI.

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from src.share_pack import (
    MAX_MEMBER_BYTES,
    _index_backup_bundles,
    apply_pack_images,
    collect_pack_art_ids,
    export_pack,
    filter_changes_for_art_ids,
    find_bundle_for_art_id,
    find_colliding_image_names,
    get_swapped_images_directory,
    image_filename_for,
    normalize_art_id,
    parse_image_filename,
    read_pack,
    record_swapped_image,
    recover_images_from_backups,
    validate_changes_data,
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


def test_read_pack_ignores_oversized_members(tmp_path):
    # A hostile pack must not be able to stream unbounded data onto the disk.
    zip_path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("images/123456.png", b"\0" * (MAX_MEMBER_BYTES + 1))

    pack = read_pack(zip_path)
    try:
        assert pack.image_paths == []
    finally:
        pack.cleanup()


def test_find_bundle_matches_on_the_padded_art_id(tmp_path):
    (tmp_path / "123456_CardArt_abc.mtga").write_bytes(b"bundle")

    assert find_bundle_for_art_id(tmp_path, "123456") == "123456_CardArt_abc.mtga"


def test_find_bundle_does_not_match_a_shorter_art_id(tmp_path):
    # "1234" unpadded would prefix-match 123456_CardArt and swap the wrong card.
    (tmp_path / "123456_CardArt_abc.mtga").write_bytes(b"bundle")

    assert find_bundle_for_art_id(tmp_path, "1234") is None


def test_find_bundle_ignores_non_mtga_files(tmp_path):
    (tmp_path / "123456_CardArt_abc.txt").write_text("not a bundle")

    assert find_bundle_for_art_id(tmp_path, "123456") is None


def test_find_bundle_returns_none_when_the_card_art_is_not_downloaded(tmp_path):
    assert find_bundle_for_art_id(tmp_path, "123456") is None


def test_validate_accepts_a_normal_payload():
    changes = {"100119": {"ArtId": "123456", "Tags": "1696804317"}}
    validate_changes_data(changes, {"ArtId", "Tags"})


def test_validate_rejects_a_sql_injection_key():
    # This exact key rewrites every row of Cards via change_grp_id's f-string SET clause.
    changes = {"1": {"ArtId = ?, Order_Title = ? WHERE 1=1 --": 999999}}
    with pytest.raises(ValueError):
        validate_changes_data(changes, {"ArtId", "Order_Title"})


def test_validate_allows_crops_and_localizations():
    changes = {
        "100119": {"ArtId": "123456", "Localizations_enUS": {"1": "Bolt"}},
        "crops": {"123456": []},
    }
    validate_changes_data(changes, {"ArtId"})


def test_validate_rejects_a_non_object_entry():
    with pytest.raises(ValueError):
        validate_changes_data({"100119": "not an object"}, {"ArtId"})


def test_find_bundle_does_not_match_a_longer_art_id(tmp_path):
    # '7' sorts before '_', so a bare prefix test picks the 7-digit card every time.
    (tmp_path / "1234567_CardArt_xyz.mtga").write_bytes(b"wrong card")
    (tmp_path / "123456_CardArt_abc.mtga").write_bytes(b"right card")

    assert find_bundle_for_art_id(tmp_path, "123456") == "123456_CardArt_abc.mtga"
    assert find_bundle_for_art_id(tmp_path, "1234567") == "1234567_CardArt_xyz.mtga"


def test_find_bundle_accepts_a_precomputed_listing(tmp_path):
    assert (
        find_bundle_for_art_id(tmp_path, "123456", ["123456_CardArt_abc.mtga"])
        == "123456_CardArt_abc.mtga"
    )


def test_read_pack_refuses_a_pack_that_exceeds_the_total_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("src.share_pack.MAX_TOTAL_BYTES", 8)
    zip_path = tmp_path / "big.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as pack_file:
        pack_file.writestr("exported_changes.json", "{}")
        pack_file.writestr("images/123456.png", b"\0" * 64)

    with pytest.raises(ValueError):
        read_pack(zip_path)


def test_apply_pack_images_skips_an_image_with_too_many_pixels(tmp_path, monkeypatch):
    # Monkeypatched rather than building a real 64-megapixel image.
    monkeypatch.setattr("src.share_pack.MAX_IMAGE_PIXELS", 4)
    images_source = tmp_path / "pack_images"
    images_source.mkdir()
    image_path = images_source / "123456.png"
    Image.new("RGB", (8, 8), "red").save(image_path)
    # Empty but present: otherwise the hoisted listing's OSError guard returns first
    # and the pixel check never runs.
    (tmp_path / "bundles").mkdir()

    applied_count, problem_messages = apply_pack_images(
        [image_path], tmp_path / "bundles", tmp_path / "backups", tmp_path / "store"
    )

    assert applied_count == 0
    assert any("too large to apply" in message for message in problem_messages)


def test_backup_index_anchors_the_art_id(tmp_path):
    # Same hazard as find_bundle_for_art_id: '7' sorts before '_', so an unanchored
    # match would map 123456 onto the 7-digit card's backup.
    (tmp_path / "MOD_1234567_CardArt_xyz.mtga").write_bytes(b"wrong")
    (tmp_path / "MOD_123456_CardArt_abc.mtga").write_bytes(b"right")

    index = _index_backup_bundles(tmp_path)

    assert index["123456"] == "MOD_123456_CardArt_abc.mtga"
    assert index["1234567"] == "MOD_1234567_CardArt_xyz.mtga"


def test_backup_index_ignores_non_backup_files(tmp_path):
    (tmp_path / "123456_CardArt_abc.mtga").write_bytes(b"not a MOD_ file")
    (tmp_path / "MOD_notes.txt").write_text("nope")
    (tmp_path / "MOD_abc_CardArt.mtga").write_bytes(b"non-numeric art id")

    assert _index_backup_bundles(tmp_path) == {}


def test_recover_leaves_an_already_recorded_swap_alone(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "MOD_123456_CardArt_abc.mtga").write_bytes(b"would fail to parse")
    images = tmp_path / "images"
    images.mkdir()
    (images / "123456.png").write_bytes(b"my real recorded swap")

    recovered_count, problem_messages = recover_images_from_backups(
        ["123456"], backups, images
    )

    # Recorded swaps are authoritative: the bundle is never even opened.
    assert recovered_count == 0
    assert problem_messages == []
    assert (images / "123456.png").read_bytes() == b"my real recorded swap"


def test_recover_reports_a_missing_backup(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    images = tmp_path / "images"

    recovered_count, problem_messages = recover_images_from_backups(
        ["123456"], backups, images
    )

    assert recovered_count == 0
    assert any("no backup found" in message for message in problem_messages)


def test_recover_reports_an_unreadable_backup(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "MOD_123456_CardArt_abc.mtga").write_bytes(b"not a unity bundle")
    images = tmp_path / "images"

    recovered_count, problem_messages = recover_images_from_backups(
        ["123456"], backups, images
    )

    assert recovered_count == 0
    assert len(problem_messages) == 1
    assert not list(images.glob("*.png"))


def test_recover_handles_a_missing_backup_directory(tmp_path):
    recovered_count, problem_messages = recover_images_from_backups(
        ["123456"], tmp_path / "nope", tmp_path / "images"
    )

    assert recovered_count == 0
    assert any("Backup directory unavailable" in message for message in problem_messages)
