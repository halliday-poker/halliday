"""Public-event isolation, early inference and uncertainty-weighted counter behavior."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/macpoker-src'));sys.path.insert(0,str(ROOT))
from bot.group_observer import GroupObserver, F, FEATURES
from bot.groups import GroupModel, confidence, posterior
from bot.main import MyBot
from bot.params import DEFAULT_PARAMS
from bot.strategy import decide
from macpoker import GameState


def action(obs,seat,kind,amount=0,street='preflop'):
    obs.on_action(dict(seat=seat,action=kind,amount=amount,street=street))


def prototype(name,mean,counter=None,adaptive=0):
    target=dict(range_call_margin_river=.005 if name=='bluffy' else .08,
                range_bluff_floor=.45 if name=='bluffy' else .1,
                bluff_frequency=.3 if name=='bluffy' else .8,
                cbet_pot_fraction=.9,late_pot_fraction=.9)
    if counter:target.update(counter)
    return dict(name=name,prior=.5,mean=mean,concentration=[60]*len(FEATURES),
        counter=target,range_prior={k:v for k,v in target.items() if k.startswith('range_')},adaptive=adaptive)


def fake_groups():
    return [prototype('bluffy',[.65,.5,.35,.05,.15,.8,.4,.6,.5],adaptive=1),
            prototype('honest',[.15,.1,.02,.005,.75,.2,.02,.15,.01])]


def river(**updates):
    fields=dict(hole=['As','7d'],board=['Ac','Jc','9h','3s','2d'],players=[0,1],seat=0,button=0,
        folded=[False,False],stacks=[170,170],pot=100,to_call=30,street_bets=[0,30],
        min_raise_to=60,max_raise_to=170,can_raise=True,street='river',hand=30,clock_ms=30000,
        history=[['river',1,'raise',30]])
    fields.update(updates);return GameState(fields)


class PublicObservationTests(unittest.TestCase):
    def test_counts_follow_players_across_seat_rotations_and_only_completed_hands(self):
        obs=GroupObserver()
        obs.on_hand_start(dict(players=[10,11,12,13],stacks=[200]*4,button=0))
        action(obs,3,'raise',200)
        self.assertEqual(obs.hands[13],0)
        self.assertEqual(obs.counts[13][F['shove']],[0,0])
        obs.on_hand_end({})
        obs.on_hand_start(dict(players=[13,10,11,12],stacks=[200]*4,button=0))
        action(obs,0,'raise',200);obs.on_hand_end({})
        self.assertEqual(obs.counts[13][F['shove']],[2,2])
        self.assertEqual(obs.counts[10][F['shove']],[0,2])

    def test_threebet_chance_and_raise_to_sizing(self):
        obs=GroupObserver();obs.on_hand_start(dict(players=[0,1,2,3],stacks=[200]*4))
        action(obs,3,'raise',6);action(obs,0,'raise',18);action(obs,1,'fold');action(obs,2,'fold');action(obs,3,'call',12)
        obs.on_street(dict(street='flop',board=['As','7c','2d']))
        action(obs,3,'raise',39,street='flop');action(obs,0,'call',39,street='flop');obs.on_hand_end({})
        self.assertEqual(obs.counts[0][F['threebet']],[1,1])
        self.assertEqual(obs.counts[3][F['large']],[1,1])
        self.assertEqual(obs.counts[0][F['fold']],[0,1])

    def test_only_revealed_river_cards_are_ranked_and_only_on_our_turn(self):
        obs=GroupObserver();obs.on_hand_start(dict(players=[0,1],stacks=[200]*2,hole=['As','Ad']))
        obs.on_street(dict(street='river',board=['2c','5d','8s','Th','Kd']))
        action(obs,1,'raise',10,street='river');action(obs,0,'call',10,street='river')
        with patch('bot.group_observer.evaluate_hand',side_effect=AssertionError('Must defer')):
            obs.on_hand_end(dict(revealed={'1':['3h','7h']},holes={'0':['As','Ad']}))
        self.assertEqual(obs.counts[1][F['weak_show']],[0,0])
        obs.learn_pending()
        self.assertEqual(obs.counts[1][F['weak_show']],[1,1])
        self.assertEqual(obs.counts[0][F['weak_show']],[0,0])
        obs.learn_pending();self.assertEqual(obs.counts[1][F['weak_show']],[1,1])

    def test_spectator_holes_are_ignored_after_everyone_folds(self):
        obs=GroupObserver();obs.on_hand_start(dict(players=[0,1],stacks=[200]*2))
        obs.on_street(dict(street='river',board=['2c','5d','8s','Th','Kd']))
        action(obs,1,'raise',10,street='river');action(obs,0,'fold',street='river')
        obs.on_hand_end(dict(holes={'1':['3h','7h']},revealed={'1':['3h','7h']}));obs.learn_pending()
        self.assertEqual(obs.counts[1][F['weak_show']],[0,0])

    def test_drift_requires_repeated_supported_changes(self):
        obs=GroupObserver();p=7
        for j in range(len(FEATURES)):
            obs.early[p][j]=[2,15];obs.recent[p][j]=[2,15]
        obs.hands[p]=50
        self.assertEqual(obs.drift(p),0)
        obs.recent[p][F['vpip']]=[14,15]
        self.assertGreater(obs.drift(p),.5)
        obs.hands[p]=20;self.assertEqual(obs.drift(p),0)


class GroupInferenceTests(unittest.TestCase):
    def test_no_data_is_the_prior_and_cannot_trigger_a_counter(self):
        groups=fake_groups();counts=[[0,0] for _ in FEATURES]
        self.assertEqual(posterior(counts,groups),(.5,.5))
        self.assertEqual(confidence((.9,.1),groups,0),0)
        obs=GroupObserver();model=GroupModel(obs,groups,dict(temperature=1,threshold=.7))
        self.assertIs(model.parameters(1,DEFAULT_PARAMS),DEFAULT_PARAMS)

    def test_distinctive_early_observations_receive_soft_not_absolute_weight(self):
        groups=fake_groups();counts=[[mean*10,10] for mean in groups[0]['mean']]
        p=posterior(counts,groups)
        self.assertGreater(p[0],.95)
        self.assertGreater(confidence(p,groups,10),.5)
        self.assertLess(confidence(p,groups,10),1)

    def test_variance_makes_a_signature_less_diagnostic(self):
        groups=fake_groups();counts=[[mean*20,20] for mean in groups[0]['mean']]
        specific=posterior(counts,groups)[0]
        broad=deepcopy(groups)
        for g in broad:g['concentration']=[3]*len(FEATURES)
        self.assertLess(posterior(counts,broad)[0],specific)

    def test_table_context_changes_the_expected_observation(self):
        groups=fake_groups();counts=[[mean*20,20] for mean in groups[0]['mean']]
        context=deepcopy(groups)
        for j,g in enumerate(context):g['contexts']={'short':dict(mean=groups[1-j]['mean'],concentration=[60]*len(FEATURES))}
        self.assertGreater(posterior(counts,context,seats=6)[0],.9)
        self.assertLess(posterior(counts,context,seats=2)[0],.1)

    def test_bluff_counter_calls_a_marginal_hand_that_folds_against_value(self):
        groups=fake_groups();obs=GroupObserver();obs.table_size=6;obs.hands[1]=40
        model=GroupModel(obs,groups,dict(temperature=1,threshold=.7))
        settings=[]
        for group in groups:
            obs.counts[1]=[[mean*80,80] for mean in group['mean']];obs.revision+=1
            settings.append(model.parameters(1,DEFAULT_PARAMS))
        s=river();eq=s.to_call/(s.pot+s.to_call)+.04
        self.assertEqual(decide(s,eq,params=settings[0],ranged=True).kind,'call')
        self.assertEqual(decide(s,eq,params=settings[1],ranged=True).kind,'fold')

    def test_mixing_is_private_reproducible_bounded_and_preserves_value(self):
        groups=fake_groups();base_state=random.getstate()
        bots=[MyBot(seed='same'),MyBot(seed='same')]
        values=[]
        with patch('bot.main.GROUPS',groups):
            for bot in bots:
                bot.groups=GroupModel(bot.group_observer,groups,dict(temperature=1,threshold=.7))
                bot.group_observer.hands[1]=40
                bot.group_observer.counts[1]=[[mean*100,100] for mean in groups[0]['mean']]
                base=bot.groups.parameters(1,DEFAULT_PARAMS,strength=DEFAULT_PARAMS['group_strength'])
                p=bot.decision_parameters(river(to_call=0,street_bets=[0,0],history=[]))
                self.assertAlmostEqual(p['range_call_margin_river'],base['range_call_margin_river'])
                self.assertLess(abs(p['late_pot_fraction']/base['late_pot_fraction']-1),DEFAULT_PARAMS['group_mix'])
                self.assertEqual(decide(river(to_call=0),1.0,params=p,ranged=True).kind,'raise')
                values.append(p['late_pot_fraction'])
        self.assertEqual(values[0],values[1]);self.assertNotEqual(values[0],base['late_pot_fraction'])
        self.assertEqual(random.getstate(),base_state)

    def test_new_game_has_no_old_opponent_state(self):
        a,b=MyBot(seed=1),MyBot(seed=1)
        a.group_observer.hands[7]=100
        self.assertEqual(b.group_observer.hands[7],0)


class OfflinePrefixTests(unittest.TestCase):
    def test_later_actions_do_not_mutate_saved_early_prefixes(self):
        from analysis.fit_opponent_groups import extract
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);(run/'fit').mkdir();(run/'input/source').mkdir(parents=True)
            names=['A','B','C','D'];events=[]
            for hand in range(10):
                log=[(3,'fold',0),(0,'fold',0),(1,'fold',0)] if hand<5 else [(3,'raise',8),(0,'fold',0),(1,'fold',0),(2,'fold',0)]
                for seat,kind,amount in log:
                    events.append(dict(match='game',hand=hand,bot=names[seat],seat=seat,street='preflop',action=kind,amount=amount))
                events.append(dict(match='game',hand=hand,event='hand_end',board=[],holes={'D':['As','Ah']}))
            raw=''.join(json.dumps(e)+'\n' for e in events).encode()
            (run/'input/source/actions.jsonl').write_bytes(raw)
            metadata=[dict(id='upload',kind='validation',at=1_800_000_000_000,names=['D','house:call']),
                      dict(id='game',kind='ladder',at=1_800_000_001_000,names=names)]
            (run/'input/source/matches.json').write_text(json.dumps(metadata))
            (run/'fit/runtime-fit.json').write_text(json.dumps(dict(bots={'D':{}},source_sha256=sha256(raw).hexdigest())))
            extract(run)
            with np.load(run/'group-prefixes.npz') as result:
                self.assertEqual(result['rows'][:,2].tolist(),[5,10])
                self.assertEqual(result['counts'][:,F['pfr'],0].tolist(),[0,5])
                self.assertEqual(result['counts'][:,F['pfr'],1].tolist(),[5,10])


if __name__=='__main__':unittest.main()
