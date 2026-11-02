"""Import images into Unity sprites without replacing the rest of their atlas.

Coordinates below follow UnityPy's sprite exporter: atlas/mesh coordinates are
bottom-up, while imported images and Texture2D.image are ordinary Pillow images.
Preparing a replacement never mutates a Unity object or writes a bundle.
"""
from dataclasses import dataclass
import math

from PIL import Image, ImageDraw, ImageOps
from PIL.Image import Transpose


@dataclass
class SpriteReplacement:
    updates: list
    preview: Image.Image


@dataclass
class SpriteRegion:
    texture: object
    box: tuple
    size: tuple
    rotation: int = 0
    alpha_texture: object = None
    positions: tuple = ()
    atlas_positions: tuple = ()
    triangles: tuple = ()

    @classmethod
    def from_reader(cls, reader, environment):
        from UnityPy.export.SpriteHelper import SpriteSettings
        from UnityPy.helpers.MeshHelper import MeshHandler

        sprite = reader.read()
        atlas = sprite.m_SpriteAtlas.read() if sprite.m_SpriteAtlas else None
        if atlas is None and sprite.m_AtlasTags:
            for obj in sprite.assets_file.objects.values():
                if obj.type.name == 'SpriteAtlas':
                    candidate = obj.read()
                    if candidate.m_Name == sprite.m_AtlasTags[0]:
                        atlas = candidate
                        break
            if atlas is None:
                raise ValueError('The sprite atlas is missing. Download the asset in Arena first.')
        if atlas is not None:
            matches = [data for key, data in atlas.m_RenderDataMap
                       if key == sprite.m_RenderDataKey]
            if len(matches) != 1:
                raise ValueError('Could not identify the selected sprite in its atlas.')
            data = matches[0]
        else:
            data = sprite.m_RD
        texture = data.texture.read()
        alpha = data.alphaTexture.read() if data.alphaTexture else None
        # A bundle save must include every texture being edited. Never silently
        # follow an external pointer and save only the sprite's metadata bundle.
        objects = list(environment.objects)
        if any(not any(obj is tex.object_reader for obj in objects)
               for tex in (texture, alpha) if tex is not None):
            raise ValueError('The sprite texture is in another bundle and cannot be edited here.')
        rect = data.textureRect
        box = tuple(round(value) for value in (
            rect.x, rect.y, rect.x + rect.width, rect.y + rect.height))
        settings = SpriteSettings(data.settingsRaw)
        region = cls(texture, box, sprite.image.size,
                     rotation=int(settings.packingRotation) if settings.packed else 0,
                     alpha_texture=alpha)
        if int(settings.packingMode) == 0:
            mesh = MeshHandler(sprite.m_RD, reader.version)
            mesh.process()
            vertices = mesh.m_Vertices
            if not vertices:
                raise ValueError('The sprite has no editable mesh vertices.')
            axes = list(zip(*vertices))
            if mesh.m_UV0 and any(u or v for u, v in mesh.m_UV0):
                constant = next((i for i in (2, 1, 0) if len(set(axes[i])) == 1), None)
                if constant is None:
                    raise ValueError('Three-dimensional sprite meshes are not supported.')
                axes.pop(constant)
                width, height = texture.image.size
                region.atlas_positions = tuple((round(u * width), round(v * height))
                                               for u, v in mesh.m_UV0)
            else:
                axes = axes[:2]
            minimum = (min(axes[0]), min(axes[1]))
            positions = tuple(((x - minimum[0]) * sprite.m_PixelsToUnits,
                               (y - minimum[1]) * sprite.m_PixelsToUnits)
                              for x, y in zip(*axes))
            # The exporter rounds UV-rendered vertices but passes fractional
            # mask vertices straight to Pillow. Match both paths exactly.
            region.positions = (tuple((round(x), round(y)) for x, y in positions)
                                if region.atlas_positions else positions)
            region.triangles = tuple(triangle for submesh in mesh.get_triangles()
                                     for triangle in submesh)
            if not region.triangles:
                raise ValueError('The sprite has no editable mesh triangles.')
        region.validate()
        return region

    def validate(self):
        width, height = self.texture.image.size
        x0, y0, x1, y1 = self.box
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError('The sprite region lies outside its atlas texture.')
        if self.rotation not in range(5):
            raise ValueError('This sprite uses an unsupported packing rotation.')
        if any(value <= 0 for value in self.size):
            raise ValueError('The sprite has invalid dimensions.')
        if self.alpha_texture is not None and self.alpha_texture.image.size != (width, height):
            raise ValueError('The sprite alpha texture has different dimensions.')
        for points, bounds, tolerance in ((self.positions, self.size, .5),
                                          (self.atlas_positions, (width, height), 0)):
            if any(not math.isfinite(v) or not 0 <= v <= limit + tolerance
                   for point in points for v, limit in zip(point, bounds)):
                raise ValueError('Sprite mesh coordinates lie outside the image.')
        if self.atlas_positions and len(self.positions) != len(self.atlas_positions):
            raise ValueError('Sprite mesh coordinates are incomplete.')
        if any(len(t) != 3 or any(i < 0 or i >= len(self.positions) for i in t)
               for t in self.triangles):
            raise ValueError('The sprite mesh contains invalid triangle indices.')

    def fit(self, image):
        fitted = ImageOps.contain(image.convert('RGBA'), self.size, Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', self.size)
        # No alpha mask here: imported transparent pixels must erase old pixels.
        canvas.paste(fitted, ((self.size[0] - fitted.width) // 2,
                              (self.size[1] - fitted.height) // 2))
        return canvas

    def _pack(self, image):
        inverse = {1: Transpose.FLIP_LEFT_RIGHT, 2: Transpose.FLIP_TOP_BOTTOM,
                   3: Transpose.ROTATE_180, 4: Transpose.ROTATE_90}
        return image.transpose(inverse[self.rotation]) if self.rotation else image

    def _patch(self, atlas, image):
        from UnityPy.export.SpriteHelper import copy_triangle

        if self.atlas_positions:
            # Work in a cropped canvas: Pillow's polygon edges are inclusive,
            # but textureRect's maximum coordinates are exclusive. In particular
            # an affine/rotated triangle must not clear the next atlas pixel.
            cropped = atlas.crop(self.box)
            for triangle in self.triangles:
                copy_triangle(image, tuple(self.positions[i] for i in triangle),
                              cropped, tuple((self.atlas_positions[i][0] - self.box[0],
                                              self.atlas_positions[i][1] - self.box[1])
                                             for i in triangle))
            atlas.paste(cropped, self.box[:2])
        else:
            mask = None
            if self.triangles:
                mask = Image.new('1', image.size)
                draw = ImageDraw.Draw(mask)
                for triangle in self.triangles:
                    draw.polygon([self.positions[i] for i in triangle], fill=1)
                mask = self._pack(mask)
            packed = self._pack(image)
            if packed.size != (self.box[2] - self.box[0], self.box[3] - self.box[1]):
                raise ValueError('Sprite dimensions do not match its packed rectangle.')
            atlas.paste(packed, self.box[:2], mask)

    def replace(self, image):
        """Build atlas copies and the rendered preview, preserving neighboring pixels."""
        from UnityPy.export.SpriteHelper import copy_triangle

        self.validate()
        fitted = self.fit(image)
        source = fitted.transpose(Transpose.FLIP_TOP_BOTTOM)
        atlas = self.texture.image.convert('RGBA').transpose(Transpose.FLIP_TOP_BOTTOM)
        self._patch(atlas, source)
        updates = [(self.texture, atlas.transpose(Transpose.FLIP_TOP_BOTTOM))]
        if self.alpha_texture is not None:
            alpha = self.alpha_texture.image.convert('RGBA').transpose(Transpose.FLIP_TOP_BOTTOM)
            channel = source.getchannel('A')
            self._patch(alpha, Image.merge('RGBA', (channel, channel, channel,
                                                   Image.new('L', channel.size, 255))))
            updates.append((self.alpha_texture, alpha.transpose(Transpose.FLIP_TOP_BOTTOM)))
        if self.atlas_positions:
            preview = Image.new('RGBA', self.size)
            for triangle in self.triangles:
                copy_triangle(atlas, tuple(self.atlas_positions[i] for i in triangle),
                              preview, tuple(self.positions[i] for i in triangle))
            preview = preview.transpose(Transpose.FLIP_TOP_BOTTOM)
        elif self.triangles:
            mask = Image.new('1', source.size)
            draw = ImageDraw.Draw(mask)
            for triangle in self.triangles:
                draw.polygon([self.positions[i] for i in triangle], fill=1)
            preview = Image.composite(source, Image.new('RGBA', source.size), mask)
            preview = preview.transpose(Transpose.FLIP_TOP_BOTTOM)
        else:
            preview = fitted
        return SpriteReplacement(updates, preview)
