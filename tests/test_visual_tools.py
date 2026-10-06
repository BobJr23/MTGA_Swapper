import unittest
import tempfile
import json
from pathlib import Path

class VisualToolTests(unittest.TestCase):
    def test_uv_coordinates_use_unity_bottom_origin(self):
        from src.crop_preview import pixel_box
        self.assertEqual(pixel_box((100, 80), (0.5, 0.25, 0.1, 0.2)), (10.0, 44.0, 60.0, 64.0))

    def test_crop_falls_back_from_suffix_to_base_but_not_another_card(self):
        from src.crop_preview import resolve_crop
        rows = [('Assets/000115_AIF', 'Normal', 1, .5, 0, .25, 1)]
        self.assertEqual(resolve_crop(rows, 'Assets/000115_AIF_depth', 'Normal'), (1, .5, 0, .25))
        self.assertEqual(resolve_crop(rows, 'Assets/000116_AIF', 'Normal'), (1, 1, 0, 0))

    def test_role_index_preserves_shader_slot_and_consumer(self):
        from src.asset_catalog import AssetCatalog
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder); (d/'ALT').mkdir(); (d/'AssetBundle').mkdir()
            path='Assets/Core/Art/CDC/Images/frame.png'
            (d/'Manifest_test.mtga').write_text(json.dumps({'Assets':[{'Name':'Bucket_test.mtga','IndexedAssets':[path]}]}))
            (d/'ALT'/'ALT_Card_test.mtga').write_text(json.dumps({'ALT_Card.TextureOverride':{'Nodes':[{'NodeId':'n1','Payload':{'TextureOverrideEntries':[{'Property':'_MainTex','TextureRef':{'Guid':'g','RelativePath':path}}]}}]}}))
            catalog=AssetCatalog.load(d)
            record=catalog.search('Frame texture', 'frame')[0]
            self.assertEqual(record.path,path)
            self.assertEqual(record.consumers[0].property,'_MainTex')
            self.assertEqual(record.consumers[0].node_id,'n1')
            self.assertFalse(record.available)

    def test_newer_audio_manifest_does_not_hide_visual_assets(self):
        from src.asset_catalog import AssetCatalog
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            (d/'Manifest_visual.mtga').write_text(json.dumps({'Assets':[{'Name':'art.mtga','IndexedAssets':['Assets/Core/CardArt/001_AIF.png']}]}))
            audio=d/'Manifest_Audio.mtga'
            audio.write_text(json.dumps({'Assets':[{'Name':'music.pck'}]}))
            import os
            os.utime(audio, (2000000000,2000000000))
            self.assertEqual(len(AssetCatalog.load(d).records),1)

    def test_container_pointer_is_resolved_before_object_editing(self):
        from types import SimpleNamespace
        from src.asset_catalog import resolve_object, AssetRecord
        reader=SimpleNamespace(path_id=73)
        pointer=SimpleNamespace(deref=lambda:reader)
        environment=SimpleNamespace(container={'assets/frame.mat':pointer},objects=[])
        record=AssetRecord('Assets/frame.mat','frame.mtga',Path('frame.mtga'),'Material')
        self.assertIs(resolve_object(environment,record),reader)

    def test_atlas_uses_sprite_name_not_container_texture_order(self):
        from types import SimpleNamespace
        from src.asset_catalog import resolve_object, AssetRecord
        sprite=SimpleNamespace(path_id=22)
        pointer=SimpleNamespace(deref=lambda:sprite)
        atlas=SimpleNamespace(m_PackedSpriteNamesToIndex=['frame_body'],m_PackedSprites=[pointer])
        obj=SimpleNamespace(type=SimpleNamespace(name='SpriteAtlas'),read=lambda:atlas)
        environment=SimpleNamespace(container={},objects=[obj])
        record=AssetRecord('Assets/UI/frame_body.png','Atlas_UI.mtga',Path('Atlas_UI.mtga'),'UI sprite')
        self.assertIs(resolve_object(environment,record),sprite)

    def test_crop_staging_can_be_rolled_back(self):
        import sqlite3
        from src.crop_preview import stage_crops
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE Crops (Path TEXT,Format TEXT,X REAL,Y REAL,Z REAL,W REAL,Generated INTEGER, PRIMARY KEY(Path,Format))')
        stage_crops(db,'art',{'Normal':(1,.5,0,.25)})
        self.assertEqual(db.execute('SELECT COUNT(*) FROM Crops').fetchone()[0],1)
        db.rollback()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM Crops').fetchone()[0],0)
        db.close()

    def test_theme_only_changes_selected_reference_and_keeps_rules(self):
        from src.theme_editor import ThemeDocument
        document={'ALT_Card.MaterialOverride':{'Nodes':[{'NodeId':'n','Payload':{'MaterialRef':{'Guid':'old','RelativePath':'old.mat'},'Other':5}},{'NodeId':'rule','Evaluator':{'ExpectedValues':[7]}}]}}
        theme=ThemeDocument(document)
        binding=theme.bindings()[0]
        theme.replace(binding, {'Guid':'new','RelativePath':'new.mat'})
        result=theme.result()
        self.assertEqual(result['ALT_Card.MaterialOverride']['Nodes'][0]['Payload']['MaterialRef']['RelativePath'],'new.mat')
        self.assertEqual(result['ALT_Card.MaterialOverride']['Nodes'][0]['Payload']['Other'],5)
        self.assertEqual(result['ALT_Card.MaterialOverride']['Nodes'][1],document['ALT_Card.MaterialOverride']['Nodes'][1])
        self.assertEqual(document['ALT_Card.MaterialOverride']['Nodes'][0]['Payload']['MaterialRef']['Guid'],'old')

    def test_theme_save_backs_up_and_rejects_concurrent_edit(self):
        from src.theme_editor import ThemeDocument
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ALT.mtga'; p.write_text(json.dumps({'ALT_Card.MaterialOverride':{'Nodes':[]}}))
            theme=ThemeDocument.load(p)
            p.write_text('{}')
            with self.assertRaises(RuntimeError): theme.save()
            self.assertEqual(p.read_text(),'{}')

    def test_theme_bundle_crc_does_not_touch_existing_member_bytes(self):
        from UnityPy.files import BundleFile
        from UnityPy.enums import ArchiveFlags
        from UnityPy.streams import EndianBinaryReader
        import UnityPy
        from src.theme_bundle import save_edited_bundle
        from src.bundle_crc import compute_bundle_crc
        bundle=BundleFile.__new__(BundleFile)
        bundle.signature='UnityFS'; bundle.version=6
        bundle.version_player='2022.3.62f2'; bundle.version_engine='2022.3.62f2'
        bundle.dataflags=ArchiveFlags(64); bundle._uses_block_alignment=True
        member=EndianBinaryReader(b'palette bytes must stay untouched'); member.flags=0
        bundle.files={'palette.resS':member}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/('Palette_89f11d38-'+'a'*32+'.mtga')
            original=bundle.save(); p.write_bytes(original)
            env=UnityPy.load(p.read_bytes())
            backup=save_edited_bundle(env,p,original)
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(compute_bundle_crc(p),0x89f11d38)
            self.assertEqual(bytes(UnityPy.load(p.read_bytes()).file.files['palette.resS'].bytes),b'palette bytes must stay untouched')

    def test_preview_samples_the_lower_half_for_bottom_origin_crop(self):
        from PIL import Image
        from src.crop_preview import render_crop
        image=Image.new('RGBA',(20,20),'red')
        image.paste((0,0,255,255),(0,10,20,20))
        preview=render_crop(image,(1,.5,0,0),(20,10),max_size=(20,10))
        self.assertEqual(preview.getpixel((10,7)),(0,0,255,255))

    def test_preview_rejects_nan_and_negative_scales(self):
        from src.crop_preview import pixel_box
        for crop in ((float('nan'),1,0,0),(-1,1,0,0),(1,0,0,0)):
            with self.assertRaises(ValueError): pixel_box((100,100),crop)

    def test_theme_save_preserves_original_backup_and_roundtrips(self):
        from src.theme_editor import ThemeDocument
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'ALT.mtga'
            p.write_text(json.dumps({'ALT_Card.MaterialOverride':{'Nodes':[{'NodeId':'n','Payload':{'MaterialRef':{'Guid':'old','RelativePath':'old.mat'}}}]}}))
            original=p.read_bytes(); theme=ThemeDocument.load(p)
            binding=theme.bindings()[0]
            theme.replace(binding,{'Guid':'new','RelativePath':'new.mat'})
            backup=theme.save()
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(ThemeDocument.load(p).reference(binding)['Guid'],'new')
            self.assertFalse(theme.changes)

    def test_reset_color_restores_preset_and_import_does_not_enable_other_groups(self):
        from copy import deepcopy
        from src.theme_editor import refresh_color_schemes
        source={'ColorScheme':0,'DefaultSettings':{'Text':{'r':0.,'g':0.,'b':0.,'a':1.}},
                'FieldTypeOverrides':[{'ColorScheme':1,'Settings':{'Text':{'r':1.,'g':1.,'b':1.,'a':1.}}}]}
        data=deepcopy(source)
        data['DefaultSettings']['Text']['r']=.5
        refresh_color_schemes(data,source)
        self.assertEqual(data['ColorScheme'],999)
        self.assertEqual(data['FieldTypeOverrides'][0]['ColorScheme'],1)
        data['DefaultSettings']['Text']['r']=0.
        refresh_color_schemes(data,source)
        self.assertEqual(data,source)

    def test_crop_preset_export_keeps_other_changes_and_rejects_bad_json(self):
        from src.crop_preview import write_crop_changes
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'changes.json'
            p.write_text(json.dumps({'cards':{'keep':7}}))
            rows=[('Assets/Core/CardArt/001000/001155_AIF','Normal',1.,.5,0.,.25,0)]
            write_crop_changes(rows,p)
            data=json.loads(p.read_text())
            self.assertEqual(data['cards'],{'keep':7})
            self.assertEqual(data['crops']['1155'][0]['w'],.25)
            p.write_text('{broken')
            with self.assertRaises(ValueError): write_crop_changes(rows,p)
            self.assertEqual(p.read_text(),'{broken')

    def test_crop_export_merges_padded_aliases_using_existing_art_identity(self):
        from src.crop_preview import write_crop_changes
        path='Assets/Core/CardArt/001000/001155_AIF'
        def entry(context, x):
            return dict(path=path,format=context,x=x,y=1,z=0,w=0,generated=0)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'changes.json'
            p.write_text(json.dumps({'crops':{'1155':[entry('Normal',.7)],
                '001155':[entry('Normal',.9),entry('Borderless',.6)]}}))
            write_crop_changes([(path,'RoomLeft',.5,1,0,0,0)],p)
            crops=json.loads(p.read_text())['crops']
            self.assertEqual(set(crops),{'1155'})
            self.assertEqual({c['format']:c['x'] for c in crops['1155']},
                             {'Normal':.7,'Borderless':.6,'RoomLeft':.5})

    def test_palette_changes_only_rgba_leaves(self):
        from src.theme_editor import color_fields, recolor
        data={'m_Name':'Frame','Colors':[{'Color':{'r':1.,'g':.5,'b':0.,'a':.7},'Index':4}]}
        fields=color_fields(data)
        self.assertEqual(len(fields),1)
        updated=recolor(data, fields[0], '#204060')
        self.assertEqual(updated['Colors'][0]['Color'],{'r':32/255,'g':64/255,'b':96/255,'a':.7})
        self.assertEqual(data['Colors'][0]['Color']['r'],1.)

if __name__=='__main__': unittest.main()
