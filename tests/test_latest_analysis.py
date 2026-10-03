"""Input integrity and explicit version selection for refreshed analyses."""
import json
from pathlib import Path
import tempfile
import unittest

from analysis.freeze_snapshot import freeze
from analysis.halliday_performance import extract


class SnapshotTests(unittest.TestCase):
    def inputs(self, root):
        source = root/'input'
        source.mkdir()
        matches = [dict(id=mid, names=['Halliday', 'other']) for mid in ('old', 'new')]
        (source/'matches.json').write_text(json.dumps(matches))
        (source/'state.json').write_text(json.dumps({'collected': {m['id']: {'status': 'collected'} for m in matches}}))
        (source/'actions.jsonl').write_text(''.join(json.dumps(dict(match=m['id'], hand=0, holes={'Halliday': ['As', 'Ks']}))+'\n' for m in matches))
        return source

    def test_preallocated_incomplete_upload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.inputs(root)
            with (source/'actions.jsonl').open('ab') as stream:
                stream.write(b'\0' * 100)
            with self.assertRaisesRegex(ValueError, 'NUL'):
                freeze(source, root/'run')

    def test_missing_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.inputs(root)
            (source/'matches.json').write_text('[]')
            with self.assertRaisesRegex(ValueError, 'missing metadata'):
                freeze(source, root/'run')

    def test_explicit_newest_selection_never_readds_historical_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.inputs(root)
            original = {p.name: p.read_bytes() for p in source.iterdir()}
            audit = freeze(source, root/'run')
            self.assertEqual(audit['matches_with_actions'], 2)
            extract(root/'run/source', root/'audit', ['new'])
            events = [json.loads(line) for line in (root/'audit/halliday-events.jsonl').read_text().splitlines()]
            self.assertEqual([e['match'] for e in events], ['new'])
            selected = json.loads((root/'audit/matches-snapshot.json').read_text())
            self.assertEqual([m['id'] for m in selected], ['new'])
            self.assertEqual(original, {p.name: p.read_bytes() for p in source.iterdir()})


if __name__ == '__main__':
    unittest.main()
