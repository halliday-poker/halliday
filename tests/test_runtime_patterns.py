"""Upload boundaries, public runtime state and resumable complete duplicate sets."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from harness import eval as harness
from opponent_model.runtime_patterns import newest_selection
from opponent_model.recency_prior import prior_weights
from opponent_model.data import COL,FIELDS
from sparring.competitors.catalog import validate_catalog
from sparring.competitors.competitor_base import FittedBot
from sparring.param import ARCHETYPES
from analysis.audit_pattern_simulation import normalized_events, reconstruct_trace, eligible, broad_shovers
from analysis.freeze_snapshot import freeze


class UploadSelectionTests(unittest.TestCase):
    def test_every_validation_is_a_boundary_and_includes_its_own_game(self):
        t=1791030000000
        matches=[dict(id='v1',kind='validation',names=['a','house:call'],at=t),
                 dict(id='old',kind='ladder',names=['a','b'],at=t+1),
                 dict(id='failed',kind='validation',names=['a','house:call'],at=t+2,verdict='RTE'),
                 dict(id='new',kind='ladder',names=['a','b'],at=t+3)]
        result=newest_selection(matches,['a'])['a']
        self.assertEqual(result['upload'],'failed')
        self.assertEqual(result['match_ids'],['failed','new'])

    def test_latest_upload_without_ladder_data_does_not_revert_to_old_version(self):
        t=1791030000000
        matches=[dict(id='old',kind='ladder',names=['a','b'],at=t),
                 dict(id='new',kind='validation',names=['house:call','a'],at=t+1)]
        self.assertEqual(newest_selection(matches,['a'])['a']['match_ids'],['new'])

    def test_collection_timestamps_do_not_imply_upload_order(self):
        matches=[dict(id='v',kind='validation',names=['a','house:call'],at=1791030000)]
        result=newest_selection(matches,['a'])['a']
        self.assertIsNone(result['upload']);self.assertTrue(result['exclusion_reason'])


class PublicRuntimeTests(unittest.TestCase):
    def test_rotating_seats_settle_scores_by_fixed_player_id(self):
        record=dict(name='example',style=ARCHETYPES['tag'],patterns={'preflop_progress':[0]*4})
        bot=FittedBot(record,Path.cwd(),seed=1)
        bot.on_match_start({'player':0,'num_players':3})
        bot.on_hand_start({})
        before=bot.history_vector.copy()
        bot.on_action(dict(players=[2,0,1],seat=1,street='preflop',action='raise',amount=200))
        np.testing.assert_array_equal(before,bot.history_vector)
        bot.on_hand_end(dict(players=[2,0,1],deltas=[10,-3,-7],revealed={'1':['As','Ad']}))
        self.assertEqual(bot.public_history.score,{0:-3,1:-7,2:10})
        bot.on_hand_start({})
        self.assertAlmostEqual(bot.history_vector[0],-.003)
        self.assertGreater(bot.history_vector[7],before[7])

    def test_invalid_progress_parameters_rejected(self):
        for slopes in ([0,1],[0,0,0,float('nan')],[0,0,0,9]):
            with self.assertRaises(ValueError):
                validate_catalog(dict(schema_version=1,bots={'a':dict(name='A',style=ARCHETYPES['tag'],patterns={'preflop_progress':slopes})}))


class RecencyPriorTests(unittest.TestCase):
    def rows(self,n):
        rows=np.zeros((n,len(FIELDS)))
        for name,value in dict(street=1,strength=.5,can_raise=1,action=3,amount=20,pot=30,minimum=2,maximum=200).items():
            rows[:,COL[name]]=value
        return rows

    def test_full_newest_weight_and_tenfold_decay_until_target(self):
        rows=self.rows(222);ages=np.array([0]*2+[1]*20+[2]*200)
        weights,joint,evidence=prior_weights(rows,ages)
        np.testing.assert_array_equal(weights['size'][:2],[1,1])
        np.testing.assert_allclose(weights['size'][2:22],.1)
        np.testing.assert_allclose(weights['size'][22:],.01)
        self.assertEqual(evidence['size']['status'],'still_sparse')
        self.assertAlmostEqual(evidence['size']['effective_opportunities'],6)

    def test_stop_adding_old_versions_when_effective_target_reached(self):
        rows=self.rows(802);ages=np.array([0]*2+[1]*600+[2]*200)
        weights,_,evidence=prior_weights(rows,ages)
        np.testing.assert_allclose(weights['size'][2:602],.08)
        self.assertEqual(float(weights['size'][602:].sum()),0)
        self.assertAlmostEqual(evidence['size']['effective_opportunities'],50)

    def test_sufficient_newest_and_unknown_age_never_use_older_data(self):
        rows=self.rows(100);ages=np.array([0]*50+[1]*25+[-1]*25)
        weights,_,evidence=prior_weights(rows,ages)
        self.assertEqual(float(weights['size'][50:].sum()),0)
        self.assertEqual(evidence['size']['status'],'latest_sufficient')

    def test_elapsed_time_discounts_longer_upload_gaps(self):
        rows=self.rows(22);ages=np.array([0]*2+[1]*10+[2]*10)
        weights,_,evidence=prior_weights(rows,ages,{1:6,2:12})
        np.testing.assert_allclose(weights['size'][:2],1)
        np.testing.assert_allclose(weights['size'][2:12],.05)
        np.testing.assert_allclose(weights['size'][12:],.0025)
        self.assertAlmostEqual(evidence['size']['older_versions'][0]['time_discount'],.5)

    def test_missing_newest_replay_uses_only_discounted_prior_support(self):
        rows=self.rows(20);ages=np.array([1]*10+[2]*10)
        weights,joint,evidence=prior_weights(rows,ages,{1:6,2:12})
        np.testing.assert_allclose(weights['size'][:10],.05)
        np.testing.assert_allclose(weights['size'][10:],.0025)
        self.assertTrue(np.all(joint<1))
        self.assertEqual(evidence['size']['latest_opportunities'],0)
        self.assertEqual(evidence['size']['status'],'still_sparse')


class SimulationTests(unittest.TestCase):
    def test_wide_shover_sensitivity_uses_only_observed_prefix(self):
        row=dict(street='preflop',terminal_call=True,prior_hands=7,opponents=[1],
                 seats=['Halliday','b'],prior_preflop_shoves={'b':2},
                 history=[dict(bot='b',street='preflop',action='raise',amount=200)])
        self.assertEqual(broad_shovers(row),[1])
        self.assertEqual(broad_shovers(dict(row,prior_hands=6)),[])
        self.assertEqual(broad_shovers(dict(row,prior_hands=20)),[])
        self.assertEqual(broad_shovers(dict(row,history=[])),[])

    def test_exact_budget_preserves_complete_distinct_opponent_tables(self):
        pool=[(f'house:{name}',1) for name in ('call','random','fold','raise','shove','other')]
        tables=harness.draw_tables(pool,1,[4,5,5,6],'budget',game_budget=30000)
        self.assertEqual(sum(len(t)+1 for t in tables),30000)
        self.assertTrue(all(3<=len(t)<=5 and len(set(t))==len(t) for t in tables))
        self.assertEqual(tables,harness.draw_tables(pool,1,[4,5,5,6],'budget',game_budget=30000))
        with self.assertRaisesRegex(ValueError,'complete'):
            harness.draw_tables(pool,1,[4,6],'budget',game_budget=9)

    def test_trace_resume_checks_provenance_and_retains_private_spectator_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=dict(cand_idx=0,candidate='house:call',opponents=['house:call']*3,
                     table=0,game=0,seed='trace-test',deals=3,time_ms=30000,increment_ms=100,
                     trace_dir=tmp,resume=False,source_hashes={'house:call':'test'})
            first=harness._play_game(job)
            self.assertEqual(sum(first['chips']),0)
            path=next(Path(tmp).glob('*.gz'))
            with gzip.open(path,'rt') as stream:trace=json.load(stream)
            self.assertEqual(len(trace['hands']),3)
            self.assertEqual(len(trace['hands'][0]['holes']),4)
            self.assertTrue(trace['decisions'])
            self.assertNotIn('holes',trace['decisions'][0]['view'])
            second=harness._play_game(dict(job,resume=True))
            self.assertEqual(first,second)
            with self.assertRaisesRegex(ValueError,'changed'):
                harness._play_game(dict(job,resume=True,deals=4))
            with self.assertRaises(FileExistsError):harness._play_game(job)

    def test_full_trace_roundtrip_and_strict_missing_state_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'traces').mkdir()
            job=dict(cand_idx=0,candidate='house:call',opponents=['house:call']*3,
                table=0,game=1,seed='audit-roundtrip',deals=100,time_ms=30000,increment_ms=100,
                trace_dir=str(root/'traces'),resume=False)
            result=harness._play_game(job)
            with gzip.open(next((root/'traces').glob('*.gz')),'rt') as f:trace=json.load(f)
            names=['Halliday','a','b','c']
            rows,hands=reconstruct_trace(trace,'m',names)
            self.assertEqual(len(hands),100)
            self.assertEqual(sum(h['chips'] for h in hands),result['chips'][0])
            self.assertTrue(rows)
            source=root/'source';source.mkdir()
            events=[e for h in trace['hands'] for e in normalized_events(h,names,'m')]
            (source/'actions.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            metadata=[dict(id='m',names=names,chips=result['chips'],kind='ladder',
                           at=1791030000000,collected_at=1791030001)]
            (source/'matches.json').write_text(json.dumps(metadata))
            original=json.dumps(dict(collected={}))
            (source/'state.json').write_text(original)
            with self.assertRaisesRegex(ValueError,'incomplete'):
                freeze(source,root/'strict')
            manifest=freeze(source,root/'recovered',recover_state=True)
            self.assertEqual(manifest['recovered_collector_state'][0]['hands'],100)
            self.assertEqual((source/'state.json').read_text(),original)
            self.assertEqual((root/'recovered/source/state-collector.json').read_text(),original)
            metadata[0]['chips'][0]+=1
            (source/'matches.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError,'inconsistent metadata'):
                freeze(source,root/'bad',recover_state=True)


if __name__=='__main__':unittest.main()
