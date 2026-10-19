from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('archive_customizer', ROOT/'工具'/'icon_customizer.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class IconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette = tool.read_palette(ROOT/'配色方案'/'默认配色.json')
        cls.renderer = tool.Renderer()

    def test_all_prebuilt_assets_have_transparency_and_ico_sizes(self):
        self.assertEqual(len(self.palette), 24)
        for item in self.palette:
            with self.subTest(format=item['id']):
                with Image.open(ROOT/'成品图标'/'PNG'/f"{item['id']}.png") as image:
                    self.assertEqual(image.width, image.height)
                    self.assertEqual(image.convert('RGBA').getextrema()[3], (0, 255))
                with Image.open(ROOT/'成品图标'/'ICO'/f"{item['id']}.ico") as image:
                    self.assertEqual(sorted(image.ico.sizes()), sorted((n, n) for n in tool.SIZES))
                    for n in tool.SIZES:
                        self.assertEqual(image.ico.getimage((n, n)).convert('RGBA').getextrema()[3], (0, 255))

    def test_hair_and_body_colors_are_independent(self):
        item = self.palette[0]
        character = tool.Renderer(style='character')
        base = np.array(character.render(item, 1280))
        hair = np.array(character.render(dict(item, hair='#F062A3'), 1280))
        body = np.array(character.render(dict(item, body='#22A886'), 1280))
        self.assertFalse(np.array_equal(base[:440], hair[:440]))
        self.assertTrue(np.array_equal(base[470:], hair[470:]))
        self.assertFalse(np.array_equal(base[470:], body[470:]))
        self.assertTrue(np.array_equal(base[:440], body[:440]))
        self.assertTrue(np.array_equal(base[:, :, 3], hair[:, :, 3]))
        self.assertTrue(np.array_equal(base[:, :, 3], body[:, :, 3]))

    def test_invalid_names_colors_and_duplicate_ids_are_rejected(self):
        base = self.palette[0]
        for invalid in [dict(base, id='../escape'), dict(base, hair='red'), dict(base, label='TOO-LONG-LABEL')]:
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    tool.validate_palette([invalid])
        with self.assertRaises(ValueError):
            tool.validate_palette([base, base])

    def test_batch_export_includes_complete_files_and_palette(self):
        chosen = [x for x in self.palette if x['id'] in ['7z', 'lzma', 'qcow2']]
        with tempfile.TemporaryDirectory(prefix='archive-moe-tests-') as temporary:
            self.assertTrue(Path(temporary).name.startswith('archive-moe-tests-'))
            destination = Path(temporary)/'export'
            tool.export_batch(self.renderer, chosen, destination)
            self.assertEqual(tool.read_palette(destination/'palette.json'), chosen)
            self.assertTrue((destination/'preview.png').is_file())
            with zipfile.ZipFile(str(destination)+'.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len([x for x in archive.namelist() if x.endswith('.ico')]), 3)
            for item in chosen:
                with Image.open(destination/'ico'/f"{item['id']}.ico") as image:
                    self.assertEqual(len(image.ico.sizes()), 7)
                    for size in tool.SIZES:
                        expected = self.renderer.render(item, size)
                        self.assertTrue(np.array_equal(np.array(image.ico.getimage((size, size)).convert('RGBA')), np.array(expected)))

    def test_native_small_frames_are_crisp_and_keep_full_labels(self):
        from compact_icons import label_lines
        for item in self.palette:
            with self.subTest(format=item['label']):
                image = self.renderer.render(item, 16)
                self.assertLessEqual(len(image.getcolors()), 4)
                self.assertEqual(set(image.getchannel('A').getdata()), {0, 255})
                self.assertEqual(''.join(label_lines(item['label'], 16)), item['label'])
                self.assertEqual(image.getpixel((4, 0))[:3], tool.parse_hex(item['body']))
                # Native 16px artwork must not silently become a scaled copy.
                downscaled = self.renderer.render(item, 1024).resize((16, 16), Image.Resampling.LANCZOS)
                self.assertFalse(np.array_equal(np.array(image), np.array(downscaled)))

    def test_adaptive_style_switches_to_character_only_at_large_sizes(self):
        item = self.palette[0]
        adaptive = tool.Renderer(style='adaptive')
        character = tool.Renderer(style='character')
        for size in [16, 24, 32, 48]:
            self.assertTrue(np.array_equal(np.array(adaptive.render(item, size)), np.array(self.renderer.render(item, size))))
        for size in [64, 128, 256]:
            self.assertTrue(np.array_equal(np.array(adaptive.render(item, size)), np.array(character.render(item, size))))


if __name__ == '__main__':
    unittest.main()
