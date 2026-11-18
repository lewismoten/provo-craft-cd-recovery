import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "recover_cd.py"
spec = importlib.util.spec_from_file_location("recover_cd", SCRIPT)
recover_cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover_cd)


class OutputLayoutTests(unittest.TestCase):
    def test_cd_folder_has_assets_in_requested_locations(self):
        layout = recover_cd.output_layout(Path("/archive"), "All Occasions")

        self.assertEqual(layout.root, Path("/archive/all-occasions"))
        self.assertEqual(layout.gif_dir, layout.root / "GIF")
        self.assertEqual(layout.svg_dir, layout.root / "SVG")
        self.assertEqual(layout.font_path("Birthday Fun"), layout.root / "Birthday Fun.ttf")
        self.assertEqual(layout.contact_sheet(1), layout.root / "contact-sheet-01.png")

    def test_slugify_normalizes_disc_names(self):
        self.assertEqual(recover_cd.slugify('Provo Craft: All Occasions!'), 'provo-craft-all-occasions')


if __name__ == "__main__":
    unittest.main()
