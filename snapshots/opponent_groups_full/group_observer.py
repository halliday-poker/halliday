"""Small public-event sufficient statistics shared by online and offline grouping.

Only completed hands enter the classifier. Opponent cards are consumed only from
the SDK's revealed showdown field, never from act-state or spectator hole cards.
Player IDs are local to a game and survive seat rotations. No state is global.
"""
from collections import defaultdict

if __package__:
    from .engine import evaluate_hand
else:
    from engine import evaluate_hand


FEATURES = ('vpip', 'pfr', 'threebet', 'shove', 'fold', 'bet', 'raise', 'large', 'weak_show')
F = {name: i for i, name in enumerate(FEATURES)}


def empty():
    return [[0.0, 0.0] for _ in FEATURES]


class GroupObserver:
    def __init__(self):
        self.counts = defaultdict(empty)
        self.early = defaultdict(empty)
        self.recent = defaultdict(empty)
        self.hands = defaultdict(int)
        self.revision = 0
        self._pending = []
        self._players = []
        self._hand = {}

    def on_hand_start(self, info):
        self._players = list(info['players'])
        self.table_size = len(self._players)
        self._start = list(info['stacks'])
        self._bets = [0] * len(self._players)
        button = info.get('button', 0)
        n = len(self._players)
        sb, bb = (button, (button+1)%n) if n == 2 else ((button+1)%n, (button+2)%n)
        self._bets[sb], self._bets[bb] = min(1,self._start[sb]), min(2,self._start[bb])
        self._pot = sum(self._bets)
        self._raises = 0
        self._folded = set()
        self._board = []
        self._hand = {p:empty() for p in self._players}
        self._river_bet = set()

    def on_street(self, event):
        self._bets = [0] * len(self._players)
        self._board = list(event['board'])

    def on_action(self, event):
        seat, kind, amount = event['seat'], event['action'], event['amount']
        player = self._players[seat]
        row = self._hand[player]
        current = max(self._bets)
        facing = current > self._bets[seat]
        if event['street'] == 'preflop':
            row[F['vpip']][0] = max(row[F['vpip']][0], kind in ('call','raise'))
            row[F['pfr']][0] = max(row[F['pfr']][0], kind == 'raise')
            row[F['shove']][0] = max(row[F['shove']][0], kind == 'raise' and amount >= self._start[seat])
            if self._raises == 1 and kind != 'check' and not row[F['threebet']][1]:
                row[F['threebet']] = [float(kind == 'raise'), 1.0]
            self._raises += kind == 'raise'
        else:
            if facing:
                row[F['fold']][0] += kind == 'fold'
                row[F['fold']][1] += 1
                row[F['raise']][0] += kind == 'raise'
                row[F['raise']][1] += 1
            else:
                row[F['bet']][0] += kind == 'raise'
                row[F['bet']][1] += 1
            if kind == 'raise':
                size = (amount-current)/max(1, self._pot+current-self._bets[seat])
                row[F['large']][0] += size >= .75
                row[F['large']][1] += 1
                if event['street'] == 'river':
                    self._river_bet.add(player)
        if kind == 'raise':
            self._pot += amount-self._bets[seat]
            self._bets[seat] = amount
        elif kind == 'call':
            self._pot += amount
            self._bets[seat] += amount
        elif kind == 'fold':
            self._folded.add(player)

    def on_hand_end(self, info):
        revealed = info.get('revealed', {})
        shown = []
        if len(self._players)-len(self._folded) > 1 and len(self._board) == 5:
            for seat, cards in revealed.items():
                player = self._players[int(seat)]
                if player in self._river_bet and player not in self._folded:
                    shown.append((player,list(cards),list(self._board)))
        # Expensive card ranking is deferred to act(), inside the bot's clock.
        self._pending.extend(shown)
        for player,row in self._hand.items():
            for feature in ('vpip','pfr','shove'):
                row[F[feature]][1] = 1.0
            for j,(success,total) in enumerate(row):
                self.counts[player][j][0] += success
                self.counts[player][j][1] += total
                if self.hands[player] < 15:
                    self.early[player][j][0] += success
                    self.early[player][j][1] += total
                # A 12-hand half-life; always decay, including absent opportunities.
                for k,value in enumerate((success,total)):
                    self.recent[player][j][k] = self.recent[player][j][k]*.9438743127+value
            self.hands[player] += 1
        self.revision += 1
        self._hand = {}

    def learn_pending(self):
        for player,cards,board in self._pending:
            hand = evaluate_hand(cards+board)
            board_hand = evaluate_hand(board)
            weak = hand[0] == 0 or hand == board_hand
            row = self.counts[player][F['weak_show']]
            row[0] += weak
            row[1] += 1
        if self._pending:
            self.revision += 1
        self._pending.clear()

    def drift(self, player):
        """Evidence of changed conditional action rates, not proof of adaptation."""
        if self.hands[player] < 30:
            return 0.0
        score = 0.0
        for feature in ('vpip','pfr','fold','bet'):
            a,n = self.early[player][F[feature]]
            b,m = self.recent[player][F[feature]]
            if min(n,m) < 8:
                continue
            left,right = (a+1)/(n+2),(b+1)/(m+2)
            variance = left*(1-left)/(n+3)+right*(1-right)/(m+3)
            z2 = (left-right)**2/max(variance,1e-6)
            score = max(score,min(1.0,max(0.0,(z2-6.0)/10.0)))
        return score
