from types import SimpleNamespace

import pytest
from PIL import Image


def texture(image):
    return SimpleNamespace(image=image, m_MipCount=3)


def test_rectangle_replaces_only_selected_region_and_fits_without_stretching():
    from src.sprite_edit import SpriteRegion
    original = Image.new('RGBA', (12, 10), 'blue')
    region = SpriteRegion(texture(original), (3, 2, 7, 6), (4, 4))
    result = region.replace(Image.new('RGBA', (8, 4), 'red'))
    atlas = result.updates[0][1]
    assert atlas.size == original.size
    # Unity's rectangle origin is at the bottom of the ordinary Pillow image.
    assert atlas.getpixel((4, 4)) == (0, 0, 0, 0)
    assert atlas.getpixel((4, 5)) == (255, 0, 0, 255)
    assert atlas.getpixel((4, 7)) == (0, 0, 0, 0)
    assert atlas.getpixel((2, 5)) == (0, 0, 255, 255)
    assert atlas.getpixel((7, 5)) == (0, 0, 255, 255)
    assert original.getpixel((4, 5)) == (0, 0, 255, 255)
    assert result.preview.size == (4, 4)


@pytest.mark.parametrize('rotation', range(5))
def test_packed_rotation_round_trips_to_the_imported_orientation(rotation):
    from src.sprite_edit import SpriteRegion
    from PIL.Image import Transpose
    image = Image.new('RGBA', (3, 2))
    image.putdata([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255),
                   (255, 255, 0, 255), (255, 0, 255, 255), (0, 255, 255, 255)])
    box = (1, 2, 3, 5) if rotation == 4 else (1, 2, 4, 4)
    region = SpriteRegion(texture(Image.new('RGBA', (8, 8), 'black')), box, image.size,
                          rotation=rotation)
    result = region.replace(image)
    raw = result.updates[0][1].transpose(Transpose.FLIP_TOP_BOTTOM).crop(box)
    export_rotation = {1: Transpose.FLIP_LEFT_RIGHT, 2: Transpose.FLIP_TOP_BOTTOM,
                       3: Transpose.ROTATE_180, 4: Transpose.ROTATE_270}
    if rotation:
        raw = raw.transpose(export_rotation[rotation])
    exported = raw.transpose(Transpose.FLIP_TOP_BOTTOM)
    assert exported.tobytes() == image.tobytes()


def test_tight_triangle_preserves_neighbor_inside_its_bounding_rectangle():
    from src.sprite_edit import SpriteRegion
    original = Image.new('RGBA', (10, 10), 'blue')
    region = SpriteRegion(texture(original), (2, 2, 7, 7), (4, 4),
        positions=((0, 0), (4, 0), (0, 4)),
        atlas_positions=((2, 2), (6, 2), (2, 6)), triangles=((0, 1, 2),))
    result = region.replace(Image.new('RGBA', (4, 4), 'red'))
    atlas = result.updates[0][1]
    assert atlas.getpixel((3, 6)) == (255, 0, 0, 255)
    assert atlas.getpixel((6, 3)) == (0, 0, 255, 255)
    assert original.getpixel((3, 6)) == (0, 0, 255, 255)


def test_rotated_tight_mesh_cannot_touch_pixels_outside_its_rectangle():
    from src.sprite_edit import SpriteRegion
    original = Image.new('RGBA', (10, 10), 'blue')
    region = SpriteRegion(texture(original), (2, 2, 6, 6), (4, 4),
        positions=((0, 0), (4, 0), (0, 4)),
        atlas_positions=((6, 2), (6, 6), (2, 2)), triangles=((0, 1, 2),))
    result = region.replace(Image.new('RGBA', (4, 4), 'red'))
    atlas = result.updates[0][1]
    for y in range(10):
        for x in range(10):
            if not (2 <= x < 6 and 4 <= y < 8):
                assert atlas.getpixel((x, y)) == original.getpixel((x, y))


def test_split_alpha_updates_alpha_region_without_changing_neighbors():
    from src.sprite_edit import SpriteRegion
    alpha = texture(Image.new('RGB', (8, 8), (200, 200, 200)))
    region = SpriteRegion(texture(Image.new('RGBA', (8, 8), 'blue')),
                          (2, 2, 6, 6), (4, 4), alpha_texture=alpha)
    result = region.replace(Image.new('RGBA', (4, 4), (255, 0, 0, 40)))
    assert len(result.updates) == 2
    alpha_image = result.updates[1][1]
    assert alpha_image.getpixel((3, 3))[:3] == (40, 40, 40)
    assert alpha_image.getpixel((1, 3))[:3] == (200, 200, 200)


def test_invalid_region_refuses_to_patch_the_atlas():
    from src.sprite_edit import SpriteRegion
    original = Image.new('RGBA', (8, 8), 'blue')
    with pytest.raises(ValueError, match='outside'):
        SpriteRegion(texture(original), (5, 5, 10, 10), (5, 5)).replace(original)
    assert original.getpixel((5, 5)) == (0, 0, 255, 255)
