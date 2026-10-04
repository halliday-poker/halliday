"""Isolation when SDK and harness loaders coexist in one Python process."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/macpoker-src'))
sys.path.insert(0,str(ROOT))
from harness import eval as harness
from macpoker.sdk import load_bot_from_file


class LoaderTests(unittest.TestCase):
    def test_sdk_sibling_does_not_replace_candidate_and_is_restored(self):
        source=('from macpoker import Bot\nimport shared_settings\n'
                'class Probe(Bot):\n'
                '    def __init__(self): self.marker=shared_settings.MARKER\n'
                '    def act(self,state): return state.check()\n')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules), \
                patch.object(harness,'_bot_dirs',set()), patch.object(harness,'_loaded',{}):
            first=Path(tmp)/'sdk';second=Path(tmp)/'harness'
            for path, marker in ((first,'external-sdk'),(second,'harness-candidate')):
                path.mkdir()
                (path/'main.py').write_text(source)
                (path/'shared_settings.py').write_text(f'MARKER={marker!r}\n')
            external=load_bot_from_file(str(first/'main.py'))
            candidate=harness.make_bot(str(second),'loader-check')
            self.assertEqual(external.marker,'external-sdk')
            self.assertEqual(candidate.marker,'harness-candidate')
            self.assertEqual(sys.modules['shared_settings'].MARKER,'external-sdk')


if __name__=='__main__':unittest.main()
