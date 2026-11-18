import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "recover_cd.py"
spec = importlib.util.spec_from_file_location("recover_cd", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
recover_cd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recover_cd
spec.loader.exec_module(recover_cd)


class OutputLayoutTests(unittest.TestCase):
    def test_cd_folder_has_assets_in_requested_locations(self):
        layout = recover_cd.output_layout(Path("/archive"), "All Occasions")

        self.assertEqual(layout.root, Path("/archive/all-occasions"))
        self.assertEqual(layout.png_dir, layout.root / "PNG")
        self.assertEqual(layout.svg_dir, layout.root / "SVG")
        self.assertEqual(layout.font_path("Birthday Fun"), layout.root / "Birthday Fun.ttf")
        self.assertEqual(layout.contact_sheet(1), layout.root / "contact-sheet-01.png")

    def test_slugify_normalizes_disc_names(self):
        self.assertEqual(recover_cd.slugify('Provo Craft: All Occasions!'), 'provo-craft-all-occasions')

    def test_optical_device_from_drutil_status_prefers_raw_device(self):
        status = """Vendor   Product           Rev
 TSSTcorp CDDVDW SN-208AB   LA02

           Type: CD-ROM               Name: /dev/disk12
"""
        self.assertEqual(recover_cd.optical_device_from_drutil_status(status), Path('/dev/rdisk12'))

    def test_volume_name_from_hmount_output_uses_classic_hfs_name(self):
        output = 'Volume name is "All Occasions" (locked)\nVolume has 91815936 bytes free\n'
        self.assertEqual(recover_cd.volume_name_from_hmount_output(output), 'All Occasions')

    def test_announce_writes_a_visible_step_message(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            recover_cd.announce('Extracting TIFF files')
        self.assertEqual(stream.getvalue(), 'Extracting TIFF files\n')

    def test_eject_optical_disc_uses_the_detected_non_raw_device(self):
        commands: list[list[str]] = []
        original_run = recover_cd.run
        recover_cd.run = commands.append
        try:
            stream = io.StringIO()
            with redirect_stdout(stream):
                recover_cd.eject_optical_disc(Path('/dev/rdisk12'))
        finally:
            recover_cd.run = original_run

        self.assertEqual(commands, [['diskutil', 'eject', '/dev/disk12']])
        self.assertEqual(stream.getvalue(), 'Ejecting CD: /dev/disk12\n')

    def test_png_conversion_command_preserves_transparent_white_background(self):
        command = recover_cd.png_conversion_command(Path('artwork.tiff'), Path('artwork.png'))

        self.assertEqual(command, [
            'magick', 'artwork.tiff', '-transparent', 'white', '-depth', '1',
            '-strip', '-compress', 'Zip', 'artwork.png',
        ])

    def test_raw_capture_command_reads_multiple_raw_sectors_per_io(self):
        command = recover_cd.raw_capture_command(Path('/dev/rdisk12'), Path('disc.cdr'))

        self.assertEqual(command, [
            'dd', 'if=/dev/rdisk12', 'of=disc.cdr', 'bs=301056', 'status=progress',
        ])

    def test_fingerprint_command_reads_aligned_sector_batches(self):
        command = recover_cd.fingerprint_command(Path('/dev/rdisk12'))

        self.assertEqual(command, [
            'dd', 'if=/dev/rdisk12', 'bs=301056', 'count=2',
        ])

    def test_missing_hfs_path_error_is_optional_font_folder(self):
        error = RuntimeError('Command failed: hcd Garden Party:FONT:MAC\nhcd: "Garden Party:FONT:MAC": no such file or directory')

        self.assertTrue(recover_cd.is_missing_hfs_path_error(error))


if __name__ == "__main__":
    unittest.main()
