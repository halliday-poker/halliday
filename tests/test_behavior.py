"""Public-context isolation, upload semantics, replica probabilities and inference."""
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import tempfile
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/macpoker-src'))
sys.path.insert(0,str(ROOT))
from sparring.competitors.policy import COL,FIELDS,features,legal_actions,size_targets,state_row,Policy
from sparring.param import ARCHETYPES,ParamBot
from opponent_model.predict import param_probabilities
from opponent_model.validation import epoch_map,upload_events,match_split
from opponent_model.data import reconstruct_hand
from macpoker import GameState


class BehaviorTests(unittest.TestCase):
    def test_replay_and_runtime_context_agree_through_actual_rotating_games(self):
        from sparring import param
        from macpoker.match import MatchRunner,MatchConfig
        from macpoker.transport import InProcessTransport
        captured=[]
        class Capturer(ParamBot):
            def act(self,state):
                self.me=state.player
                captured.append((state.hand,str(state.player),state_row(state,self.stats,param)))
                return super().act(state)
        names=['0','1','2']
        bots=[Capturer(dict(ARCHETYPES[style],adaptive=1),seed=i) for i,style in enumerate(('lag','tag','station'))]
        result=MatchRunner(MatchConfig(seats=3,deals=30,seed='feature-parity'),
                           [InProcessTransport(bot,name) for bot,name in zip(bots,names)]).run()
        self.assertEqual(result.verdicts,['OK']*3)
        stats=defaultdict(lambda:[0,0,0,0]);reconstructed=[]
        for hand in result.hands:
            holes={names[hand['seat_map'][int(seat)]]:cards for seat,cards in hand['holes'].items()}
            events=[]
            for event in hand['events']:
                if event['type']=='action':
                    events.append(dict(event,bot=names[hand['seat_map'][event['seat']]],holes=holes))
                elif event['type']=='street':
                    events.append(dict(event,event='board'))
                elif event['type']=='hand_end':
                    events.append(dict(event,event='hand_end',holes=holes))
            rows,_=reconstruct_hand(events,dict(names=names),0,stats)
            reconstructed.extend((hand['hand'],bot,row) for bot,row in rows)
        self.assertEqual(len(captured),len(reconstructed))
        for runtime,replay in zip(captured,reconstructed):
            self.assertEqual(runtime[:2],replay[:2])
            np.testing.assert_allclose(features(runtime[2]),features(replay[2]),atol=1e-7)

    def test_context_features_never_use_action_labels_or_match_identity(self):
        row=np.zeros((1,len(FIELDS)));row[0,COL['players']]=8
        expected=features(row)
        for name in ('match','action','amount','hand'):
            row[0,COL[name]]=999
        np.testing.assert_array_equal(features(row),expected)

    def test_failed_uploads_and_unknown_play_times_are_not_epoch_boundaries(self):
        matches=[dict(id='bad',names=['a','house:call'],kind='validation',collected_at=10,played_at=10),
                 dict(id='good',names=['a','house:call'],kind='validation',collected_at=20,played_at=20),
                 dict(id='unknown',names=['a','house:call'],kind='validation',collected_at=30,played_at=None),
                 dict(id='ladder',names=['a','b'],kind='ladder',collected_at=40,played_at=40)]
        meta={mid:dict(value=dict(names=['a','house:call'],result=dict(verdicts=[verdict,'OK'])))
              for mid,verdict in [('bad','RTE'),('good','OK'),('unknown','OK')]}
        events,audit=upload_events(matches,meta)
        mapping,info=epoch_map(matches,['a'],'upload',events=events)
        self.assertEqual(info['boundaries']['a'],[20])
        self.assertEqual(mapping['a'].tolist(),[0,1,0,1])
        self.assertEqual(audit['failed_or_unknown'],1)

    def test_match_split_is_independent_of_bots_and_order(self):
        matches=[dict(id=str(i),names=['a','b']) for i in range(100)]
        np.testing.assert_array_equal(match_split(matches),match_split(list(reversed(matches)))[::-1])
        for m in matches:m['names']=['different']
        np.testing.assert_array_equal(match_split(matches),match_split([dict(id=str(i)) for i in range(100)]))

    def test_raise_targets_respect_minimum_and_stack_cap(self):
        rows=np.zeros((2,len(FIELDS)))
        rows[:,COL['minimum']]=[12,200];rows[:,COL['maximum']]=200
        rows[:,COL['pot']]=[60,900];rows[:,COL['call']]=[6,190]
        targets=size_targets(rows)
        self.assertTrue((targets>=rows[:,COL['minimum'],None]).all())
        self.assertTrue((targets<=200).all())
        self.assertTrue((targets[1]==200).all())

    def test_analytic_scaffold_probabilities_match_actual_random_decisions(self):
        # Facing a turn bet with a draw exercises value-raise, bluff and call
        # branches, including coercion of an attempted raise when not legal.
        from unittest.mock import patch
        style=dict(ARCHETYPES['tag'],aggression=.6,bluff=.4,stickiness=.5,adaptive=0)
        state=dict(hole=['As','Ks'],board=['2s','7s','Jh','Qc'],history=[['preflop',1,'raise',6],['turn',1,'raise',20]],
                   street='turn',seat=0,players=[0,1],folded=[False,False],stacks=[180,180],
                   street_bets=[0,20],to_call=20,pot=60,min_raise_to=40,max_raise_to=180,can_raise=True)
        row=np.zeros((1,len(FIELDS)))
        for name,value in dict(street=2,facing=1,can_raise=1,strength=.4,draw=1,call=20,pot=60,stack=180).items():
            row[0,COL[name]]=value
        for can_raise in (True,False):
            state['can_raise']=can_raise;row[0,COL['can_raise']]=can_raise
            bot=ParamBot(style,seed=324);counts=np.zeros(4)
            with patch('sparring.param.strength',return_value=(.4,True)):
                for _ in range(6000):
                    action=bot.postflop(GameState(state),style)
                    counts[{'fold':0,'check':1,'call':2,'raise':3}[action.kind]]+=1
            np.testing.assert_allclose(param_probabilities(row,style,contamination=0)[0],counts/counts.sum(),atol=.012)

    def test_numpy_policy_matches_torch_and_masks_illegal_actions(self):
        import torch
        from opponent_model.behavior import Network
        torch.manual_seed(12)
        rows=np.zeros((3,len(FIELDS)),dtype=np.float32)
        rows[:,COL['players']]=8;rows[:,COL['facing']]=[0,1,1];rows[:,COL['can_raise']]=[1,0,1]
        x=features(rows);network=Network(x.shape[1],2,2)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'policy.npz'
            np.savez(path,**{k:v.detach().numpy() for k,v in network.state_dict().items()})
            a,s=Policy(path).predict(rows,1,1)
            with torch.no_grad():
                aa,ss=network(torch.from_numpy(x),torch.ones(3,dtype=torch.long),torch.ones(3,dtype=torch.long),torch.from_numpy(legal_actions(rows)))
            np.testing.assert_allclose(a,aa.softmax(1).numpy(),atol=1e-7)
            np.testing.assert_allclose(s,ss.softmax(1).numpy(),atol=1e-7)
            self.assertEqual(a[0,0],0);self.assertEqual(a[1,3],0)


if __name__=='__main__':unittest.main()
