"""Shared public-context features and NumPy inference for offline replicas.

No learned opponent policy is included in the submitted Halliday bot. Training
lives in opponent_model; this module has no PyTorch or CUDA dependency.
"""
import math
import numpy as np

BASE_FIELDS = ("match", "street", "seat", "players", "pct", "strength", "draw",
               "facing", "can_raise", "pre_raises", "cbet", "action", "amount",
               "pot", "minimum", "maximum", "call", "stack", "top", "bet",
               "agg_high", "fold_high", "fold_low", "hand")
EXTRA_FIELDS = ("live", "street_raises", "limpers", "allin", "own_raises",
                "rank_high", "rank_low", "suited", "pair", "board_paired",
                "board_suited", "board_high", "hand_category")
FIELDS = BASE_FIELDS + EXTRA_FIELDS
COL = {name: i for i, name in enumerate(FIELDS)}
RANKS = '23456789TJQKA'


def extras(hole, board, seat, folded, stacks, street_raises, limpers, own_raises, category):
    ranks = sorted((RANKS.index(c[0]) for c in hole), reverse=True) if hole else [np.nan,np.nan]
    board_ranks = [c[0] for c in board]
    return (sum(not x for x in folded), street_raises, limpers,
            sum(not folded[i] and stacks[i]==0 for i in range(len(stacks)) if i!=seat), own_raises,
            *ranks, bool(hole and hole[0][1]==hole[1][1]), bool(hole and ranks[0]==ranks[1]),
            len(board_ranks)-len(set(board_ranks)), max((sum(c[1]==s for c in board) for s in 'cdhs'),default=0),
            max((RANKS.index(c[0]) for c in board),default=0), category)


def features(rows):
    """Only own cards and public context; labels, outcomes and match IDs excluded."""
    # Clean the small matrix once, rather than allocating and scanning each
    # column on every access (43 calls per single-action inference).
    rows = np.nan_to_num(np.atleast_2d(rows), nan=0.0)
    c = lambda name: rows[:,COL[name]]
    street = c('street')
    values = [*(street==i for i in range(4)), c('pct'),c('strength'),c('draw'),c('facing'),c('can_raise'),
              np.minimum(c('pre_raises'),5)/5,c('cbet'), np.log1p(c('pot'))/math.log(1601),
              c('call')/np.maximum(1,c('pot')+c('call')),c('call')/np.maximum(1,c('stack')),
              c('stack')/200,c('top')/200,c('bet')/200,c('minimum')/200,c('maximum')/200,
              c('seat')/np.maximum(1,c('players')-1),c('seat')==0,c('seat')==1,c('seat')==2,c('players')/8,
              c('agg_high'),c('fold_high'),c('fold_low'),c('live')/8,np.minimum(c('street_raises'),5)/5,
              c('limpers')/8,c('allin')/8,np.minimum(c('own_raises'),5)/5,
              c('rank_high')/12,c('rank_low')/12,c('suited'),c('pair'),c('board_paired')/3,
              c('board_suited')/5,c('board_high')/12,c('hand_category')/8,
              np.log1p(c('stack')/np.maximum(1,c('pot')))/math.log(201)]
    return np.column_stack(values).astype(np.float32)


def legal_actions(rows):
    rows = np.atleast_2d(rows)
    facing = rows[:,COL['facing']]>0
    return np.column_stack([facing,~facing,facing,rows[:,COL['can_raise']]>0])


def size_targets(rows):
    """Public legal raise targets; a mixture can preserve shoves and small bets."""
    rows = np.atleast_2d(rows)
    c = lambda name: rows[:,COL[name]]
    pot = c('pot')+c('call')
    top = c('top')
    targets = np.column_stack([c('minimum'),np.full(len(rows),5),np.full(len(rows),6),3*top,
                               top+.25*pot,top+.5*pot,top+.75*pot,top+pot,top+1.5*pot,c('maximum')])
    return np.minimum(np.maximum(targets,c('minimum')[:,None]),c('maximum')[:,None]).astype(np.int64)


def size_labels(rows):
    targets=size_targets(rows)
    return np.abs(targets-rows[:,COL['amount'],None]).argmin(1)


def state_row(state, stats, scaffold):
    """Runtime counterpart of strict replay reconstruction, using public state."""
    pre=[h for h in state.history if h[0]=='preflop']
    raises=[h for h in pre if h[2]=='raise']
    street_raises=sum(h[0]==state.street and h[2]=='raise' for h in state.history)
    limpers=0
    for h in pre:
        if h[2]=='raise':break
        limpers+=h[2]=='call'
    live=[state.player_at(i) for i,f in enumerate(state.folded) if not f and i!=state.seat]
    seen=[stats[p] for p in live if p in stats and stats[p][0]>=10]
    agg=sum(x[1]/x[0] for x in seen)/len(seen) if seen else 0
    folds=sum(x[2]/max(1,x[3]) for x in seen)/len(seen) if seen else .3
    street={'preflop':0,'flop':1,'turn':2,'river':3}[state.street]
    made,draw=scaffold.strength(state.hole,state.board) if street else (np.nan,False)
    category=scaffold.evaluate(scaffold.parse_cards(state.hole+state.board))[0] if street else 0
    row=np.zeros(len(FIELDS),dtype=np.float32)
    values=dict(street=street,seat=state.seat,players=len(state.players),pct=scaffold.hand_percentile(state.hole),
                strength=made,draw=draw,facing=state.to_call>0,can_raise=state.can_raise,pre_raises=len(raises),
                cbet=street==1 and bool(raises) and raises[-1][1]==state.seat and street_raises==0,
                pot=state.pot,minimum=state.min_raise_to,maximum=state.max_raise_to,call=state.to_call,
                stack=state.my_stack,top=max(state.street_bets),bet=state.street_bets[state.seat],
                agg_high=agg>.3,fold_high=folds>.5,fold_low=folds<.25)
    for name,value in values.items():row[COL[name]]=value
    row[len(BASE_FIELDS):]=extras(state.hole,state.board,state.seat,state.folded,state.stacks,street_raises,
                                  limpers,sum(h[1]==state.seat and h[2]=='raise' for h in state.history),category)
    return row


def softmax(values, mask=None):
    values=np.asarray(values)
    if mask is not None:
        values=np.where(mask,values,-1e9)
    p=np.exp(values-values.max(axis=-1,keepdims=True))
    return p/p.sum(axis=-1,keepdims=True)


class Policy:
    """Small shared MLP with bot/version offsets; seeded sampling is external."""
    def __init__(self, path):
        with np.load(path,allow_pickle=False) as data:
            self.weights={k:data[k].copy() for k in data.files if k!='metadata'}
        self.version=1

    def predict(self, rows, bot, epoch):
        w=self.weights
        x=features(rows)
        h=np.concatenate([x,np.broadcast_to(w['bot.weight'][bot],(len(x),len(w['bot.weight'][bot]))),
                          np.broadcast_to(w['epoch.weight'][epoch],(len(x),len(w['epoch.weight'][epoch])))],axis=1)
        h=np.maximum(0,h@w['hidden.0.weight'].T+w['hidden.0.bias'])
        h=np.maximum(0,h@w['hidden.2.weight'].T+w['hidden.2.bias'])
        logits=h@w['action.weight'].T+w['action.bias']+w['bot_action.weight'][bot]+w['epoch_action.weight'][epoch]
        sizing=h@w['sizing.weight'].T+w['sizing.bias']+w['bot_size.weight'][bot]+w['epoch_size.weight'][epoch]
        return softmax(logits,legal_actions(rows)),softmax(sizing)
