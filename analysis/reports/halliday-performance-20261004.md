# Halliday performance and decision audit — 04 October 2026

Source: `analysis/results/input-snapshot/actions.jsonl`, SHA-256 `10331deef87e5cacb4e09ac79c5ebe2d4aeb4ff477b153d20cdb7de8fbd01d9a`. The recorded name is `Halliday`. Main results cover 140 ladder matches, 14,000 hands, and 17,847 decisions. These are eight-seat, 200-chip-per-hand games with a two-chip big blind. Recorded match times span 03 Oct 17:30:46–04 Oct 00:29:38, Australia/Melbourne. Hand numbers are zero-based.

## Main findings

Halliday lost 6,772 chips overall (-24.19 big blinds per 100 hands). It folded 12,456 times (88.97% of hands). The strongest decision-review finding is expensive calling: 38 terminal calls were negative under both public-information range models, including 33 on the river. Folding instead at those selected decisions would have improved the recorded outcomes by 1,717 chips. This is a retrospective comparison within the same hands, not a predicted gain on new games.

There were 10 model-supported missed-call flags (0.08% of folds), of which 5 also had positive call expectation against the actual hidden hands. The audit found 0 provably avoidable folds. Most folds leave future betting unresolved, so these figures do not establish the true unnecessary-fold rate. They do not support indiscriminately widening the bot's range.

Losses also reflect unlucky runouts: 117 auditable all-in hands returned -3,515 chips against +906.0 expected with the recorded hands, a -4,421.0-chip difference. This isolates cards dealt after betting ended. It does not certify the earlier decisions or provide a complete skill-adjusted win rate.

Recency matters: the latest 20 ladder games returned -383 chips over 2,000 hands and contain 0 terminal call/fold flags under this method. The strongest calling-leak examples therefore describe earlier observed play. Changes in opponents, cards and possible same-name bot replacements prevent attributing that difference to a specific code update.

| Metric | Ladder result |
|---|---|
| Matches / hands / actions | 140 / 14,000 / 17,847 |
| Net chips / bb per 100 hands | -6,772 / -24.19 |
| Positive / negative games | 65 / 75 |
| Mean chips/game, approximate 95% interval | -48.37 ± 42.01 |
| Latest 20 games: net chips / bb per 100 hands | -383 / -9.57 |

The interval treats matches as independent observations. Shared opponents, related deals and bot changes weaken that assumption. No version hash or decision-time equity/range/clock trace is recorded, so these findings cannot be attributed to the current source branch.

## How often does it fold?

Halliday folded in 12,456/14,000 hands (88.97%): 11,970 preflop (85.50% of all hands), and 486 postflop. Folds were 69.79% of all actions and 79.63% of decisions facing a positive call price. A hand can have several decisions but at most one Halliday fold.

| Street | Folds | Decisions facing a bet | Fold rate facing a bet | Calls | Raises / opening bets |
|---|---|---|---|---|---|
| Preflop | 11,970 | 14,161 | 84.53% | 838 | 1,363 |
| Flop | 245 | 759 | 32.28% | 473 | 521 |
| Turn | 153 | 463 | 33.05% | 284 | 303 |
| River | 88 | 260 | 33.85% | 163 | 176 |

There were 0 preflop folds of pocket aces. Across ten-hand blocks within games, all-street fold rates ranged from 87.86% to 89.86%. There is no obvious late-game jump to universal folding in these aggregate counts. Timing and verdict records would be needed to diagnose a time-bank fallback.

## How often were folds unnecessary?

A terminal call closes the river betting, or closes betting with at most one live player retaining chips. These opportunities allow a direct call-versus-fold comparison without assuming later betting behavior. Side pots, dead money, stack caps and sunk investments are included.

| Evidence | Count | Meaning |
|---|---|---|
| Provably avoidable fold | 0 | A free check or a guaranteed profitable terminal call was available. |
| Probable missed terminal call under both public-range models | 10 | 0.08% of all folds; 8.13% of the 123 terminal folds. |
| Public-model flag also positive against recorded hidden hands | 5 | 0.04% of all folds; useful review candidates, still model-dependent. |
| Profitable call against actual hands, with no later betting | 20 | 16.26% of terminal folds; hindsight only. |
| Of those, river calls that would win or share | 9 | Finished-board hindsight; opponent cards were not visible at the decision. |

Only 123/12,456 folds (0.99%) meet the terminal condition. Their street counts are preflop: 27, flop: 2, turn: 17, river: 77. This limited coverage is why the report gives flagged cases rather than a single supposedly exact unnecessary-fold percentage.

Among the 10 public-model flags, 5 were not favorable against the actual hidden cards. The combined actual-hand call expectation of all 10 flags is +35.0 chips. This is a warning about model uncertainty, not a reason to judge a decision by the hidden cards alone.

The data also contains 3,943 positive hidden-card checkdown estimates and 497 folds that would share the recorded final board. Only 2,817 folded hands have a five-card board recorded. These figures assume hidden cards, a selected future board, or unresolved opponents checking down; they are not blunder counts.

### Missed-call cases supported by both models and actual-hand expectation

| Match / hand | Holding / street | Call / pot before call | Public EV: tight / loose | Actual-hand call EV |
|---|---|---|---|---|
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / h46 | Js Jh / preflop | 195 / 407 | +145.6 / +144.8 | +222.9 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / h55 | Qd 8s / preflop | 198 / 203 | +15.0 / +15.9 | +102.0 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / h1 | 8c 8d / preflop | 195 / 208 | +21.7 / +29.2 | +100.6 |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / h16 | 9d 9h / preflop | 194 / 408 | +40.7 / +73.1 | +70.2 |
| `j972wgk491evwkhkbgxnvyj4p18fkgzk` / h79 | Qh Ac / preflop | 176 / 230 | +53.5 / +52.1 | +66.5 |

In `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr`, hand 46, Js Jh folded facing 195 into 407. The prior 46 hands already identified shove-heavy player(s) Jason_idea; the call price was 32.4% of the resulting pot. The audit broadens only publicly demonstrated near-always shovers, after at least eight prior hands and an 80% shove rate. Other players calling those shoves retain separate ranges.

## Weaknesses and action classifications

### 1. Expensive river calls with weak showdown value

Both models flag 33/163 river calls (20.25%). Folding at those decisions changes the recorded results by +1,308 chips, excluding earlier sunk investments. The 38 total bad-terminal-call flags span 27 games; 3 occurred in hands that won chips. Thus the label is based on decision expectation, not simply losing the hand. Weak pairs and ace-high after sustained aggression are the clearest review targets.

| Match / hand | Hole cards | Board | Call / pot | Public EV: tight / loose | Hand chips |
|---|---|---|---|---|---|
| `j97295bjssf4404tt0x8phvvh98fjfd5` / h33 | Kc Jc | 6d Ts Ac 6c 3h | 125 / 250 | -123.1 / -98.5 | -186 |
| `j97bmsfrarq8fgfmqjqk4dach58fk9t0` / h16 | 3s As | 3c Qh 7c Ks Js | 115 / 286 | -112.9 / -93.0 | -200 |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` / h84 | Ah Jh | Ts 2c 7h Qd 5h | 128 / 256 | -121.6 / -89.1 | -185 |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` / h66 | 5s As | Jd 2d 5d 6c Qh | 146 / 256 | -136.1 / -83.9 | -200 |
| `j979byv2162hsqb5wx5zmbsvw18fjz8r` / h29 | Jh Jc | Kd As 3c 9h 6d | 151 / 255 | -139.0 / -71.8 | 206 |
| `j971kadp8metddwct3kzpec8v98fje85` / h47 | Js Ad | Qh Qd 7s 2d 6d | 118 / 289 | -112.9 / -53.9 | -200 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / h62 | Ac Kd | 3d 5h Qd Th 5s | 80 / 160 | -75.1 / -45.5 | -117 |
| `j9714b22xh0dbnssx8dn6gqvqs8fj3am` / h0 | Ac Qh | 7d Th Ts 2s Kd | 111 / 297 | -100.2 / -42.0 | -200 |

### 2. Turn calls that lead into costly river decisions

There are 23 additional call-review flags, 20 on the turn. Both models give negative checkdown expectation, but implied odds, future folds and future bets prevent a firm blunder diagnosis. Turn and river costs from the same hand must not be added as independent savings.

Example: `j97bmsfrarq8fgfmqjqk4dach58fk9t0`, hand 16, holding 3s As. On 3c Qh 7c Ks, Halliday called 64 into 107 (model EV -43.4/-22.9). It then called 115 on 3c Qh 7c Ks Js and finished -200 chips. Folding the earlier decision would limit the loss to 21 chips; folding the river would limit it to 85. These are alternative stopping points.

| Action # | Street / board | Player | Action | Amount |
|---|---|---|---|---|
| 1 | preflop / (preflop) | pocket-nuts | fold | 0 |
| 2 | preflop / (preflop) | love-of-da-game | fold | 0 |
| 3 | preflop / (preflop) | catherine | fold | 0 |
| 4 | preflop / (preflop) | merch where | raise | 5 |
| 5 | preflop / (preflop) | tungbot | fold | 0 |
| 6 | preflop / (preflop) | radishv2 | fold | 0 |
| 7 | preflop / (preflop) | BigBaller | fold | 0 |
| 8 | preflop / (preflop) | Halliday | call | 3 |
| 9 | flop / 3c Qh 7c | Halliday | check | 0 |
| 10 | flop / 3c Qh 7c | merch where | raise | 16 |
| 11 | flop / 3c Qh 7c | Halliday | call | 16 |
| 12 | turn / 3c Qh 7c Ks | Halliday | check | 0 |
| 13 | turn / 3c Qh 7c Ks | merch where | raise | 64 |
| 14 | turn / 3c Qh 7c Ks | Halliday | call | 64 |
| 15 | river / 3c Qh 7c Ks Js | Halliday | check | 0 |
| 16 | river / 3c Qh 7c Ks Js | merch where | raise | 115 |
| 17 | river / 3c Qh 7c Ks Js | Halliday | call | 115 |

For raises, amount is the total street bet target; for calls, it is the additional chips paid. This trace reproduces observed actions, not a simulation of an alternative strategy.

### 3. Adaptation and range calibration

A very high preflop fold rate can coexist with overly optimistic river calls: the two decisions face different opponent selection. Prioritize stronger responses to repeated postflop aggression and selective widening against demonstrated shove-heavy players. Do not assign a shove caller the same loose range as the shover. One-pair stack commitments need review, but a cooler is not automatically a mistake.

### 4. Bluff outcomes are review labels, not automatic blunders

The audit labels 10 failed high-card/no-draw bets and 14 failed semibluff actions. A profitable bluff strategy loses some called bets. The replay does not reveal how opponents would react to different bet sizes, so this audit cannot establish optimal bluff frequency or missed value bets.

| Action classification | Ladder actions | Evidence level |
|---|---|---|
| certain_avoidable_fold | 0 | Provable dominance in the audited context |
| probable_bad_terminal_call | 38 | Both public models below −2 chips, including sampling margin |
| probable_missed_terminal_call | 10 | Both public models above +2 chips, including sampling margin |
| possible_nonterminal_bad_call | 23 | Review candidate; future betting omitted |
| possible_nonterminal_overfold | 0 | Review candidate; future betting omitted |
| hindsight_losing_call_only | 108 | Hidden-card evidence only |
| hindsight_missed_call_only | 15 | Hidden-card evidence only |
| failed_air_bet / failed_semibluff | 10 / 14 | Outcome labels |
| All remaining actions | 17629 | No error established; alternatives may be unassessed |

## What happened in negative-chip matches?

The 75 negative ladder games total -17,657 chips. 24 contain a probable terminal call/fold flag; 51 have no such flag. A negative result alone is insufficient to conclude that the bot played badly. The following exclusive hand categories reconcile to the negative-game total; the amounts include full hand results, not the marginal cost of a flagged action.

| Hand category inside negative games | Hands | Actual chips |
|---|---|---|
| Other showdown losses; decision quality unresolved | 103 | -8,576 |
| Other all-in losses; decision quality unresolved | 32 | -6,400 |
| Positive-EV all-in, lost runout | 18 | -3,600 |
| Postflop investment, then fold | 260 | -3,388 |
| Probable bad terminal call | 28 | -3,349 |
| Blind-only folds | 1,487 | -2,161 |
| Failed semibluff hands | 10 | -924 |
| Preflop investment, then fold | 87 | -508 |
| Failed high-card bluff hands | 6 | -148 |
| Probable missed terminal call | 9 | -91 |
| Winning / break-even hands | 5,460 | +11,488 |

### Worst five games: decision flags versus all-in runouts

`j97ezzf8me25j31ymxdvq6pakd8fk0w0`: -846 chips, 0 bad-call flags and 5 missed-call flags. Its 13 auditable all-in hands returned -790 chips versus +963.8 expected against the recorded hands (-1,753.8 runout difference). Flagged hand numbers: 1, 15, 16, 55, 69. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j9711athmk9nrrsvqpyp0yjnfn8fkk0v`: -693 chips, 0 bad-call flags and 0 missed-call flags. Its 4 auditable all-in hands returned -800 chips versus -477.3 expected against the recorded hands (-322.7 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j971kadp8metddwct3kzpec8v98fje85`: -685 chips, 1 bad-call flags and 0 missed-call flags. Its 4 auditable all-in hands returned -800 chips versus -358.5 expected against the recorded hands (-441.5 runout difference). Flagged hand numbers: 47. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr`: -656 chips, 0 bad-call flags and 2 missed-call flags. Its 3 auditable all-in hands returned -600 chips versus +253.2 expected against the recorded hands (-853.2 runout difference). Flagged hand numbers: 16, 46. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j97fr9gpkeexf47trcw1z88re58fjfjd`: -537 chips, 0 bad-call flags and 0 missed-call flags. Its 1 auditable all-in hands returned -200 chips versus -200.0 expected against the recorded hands (+0.0 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

### Every losing game

Call/fold flags are model-dependent. The largest loss category is descriptive and may include sound decisions. “Fold-at-call saving” changes only flagged terminal calls, includes flagged calls that won, and does not include missed-call estimates. It must not be added to the all-in runout difference because the same hands can appear in both.

| Match | Chips | Call / fold flags | Fold-at-call saving | All-in runout difference | Largest loss category | Hands to review |
|---|---|---|---|---|---|---|
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` | -846 | 0 / 5 | +0 | -1754 | Positive-EV all-in, lost runout (-1,400) | h1 fold, h15 fold, h16 fold, h55 fold, h69 fold |
| `j9711athmk9nrrsvqpyp0yjnfn8fkk0v` | -693 | 0 / 0 | +0 | -323 | Other all-in losses; decision quality unresolved (-600) | h2 largest loss; unflagged |
| `j971kadp8metddwct3kzpec8v98fje85` | -685 | 1 / 0 | +118 | -442 | Other all-in losses; decision quality unresolved (-600) | h47 call |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` | -656 | 0 / 2 | +0 | -853 | Positive-EV all-in, lost runout (-600) | h16 fold, h46 fold |
| `j97fr9gpkeexf47trcw1z88re58fjfjd` | -537 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-357) | h47 largest loss; unflagged |
| `j97bmsfrarq8fgfmqjqk4dach58fk9t0` | -534 | 1 / 0 | +115 | -151 | Probable bad terminal call (-200) | h16 call |
| `j970pdtxxpjdqbj57pm0hssxb58fk4cq` | -503 | 0 / 0 | +0 | -25 | Other all-in losses; decision quality unresolved (-400) | h2 largest loss; unflagged |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` | -493 | 2 / 0 | +162 | +0 | Probable bad terminal call (-240) | h36 call, h84 call |
| `j97418jfme7vwm9t84ban33djs8fjs84` | -470 | 0 / 0 | +0 | +0 | Other all-in losses; decision quality unresolved (-200) | h22 largest loss; unflagged |
| `j977vnk0vrtb95pjnceye3ftys8fkdqd` | -466 | 1 / 0 | +29 | -643 | Positive-EV all-in, lost runout (-400) | h91 call |
| `j976fxh6jsgha7b4z7asd5d3vn8fkcpv` | -407 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-387) | h20 largest loss; unflagged |
| `j975x29dfv8g5c916v07m5bw758fk6mk` | -394 | 0 / 0 | +0 | -13 | Other all-in losses; decision quality unresolved (-400) | h45 largest loss; unflagged |
| `j97c22vg42mqkf2amq3hgan5pn8fkd9z` | -350 | 2 / 0 | +199 | +0 | Probable bad terminal call (-288) | h6 call, h8 call |
| `j977j6f97yt9zc2e4yeym1956h8fjg1e` | -350 | 0 / 1 | +0 | -26 | Other all-in losses; decision quality unresolved (-200) | h70 fold |
| `j97840xbm6ydsxq68j8kex19ch8fjyta` | -340 | 0 / 0 | +0 | -51 | Other all-in losses; decision quality unresolved (-200) | h85 largest loss; unflagged |
| `j973kra8fwxpw24evsxateqbx18fjpyk` | -334 | 0 / 0 | +0 | -314 | Positive-EV all-in, lost runout (-200) | h51 largest loss; unflagged |
| `j977nzda3se2wvzg1s9cqbj4dn8fkpwd` | -332 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-345) | h75 largest loss; unflagged |
| `j979vjkbbsane1yx9v9bg0df2x8fk24s` | -329 | 1 / 0 | +19 | +0 | Other showdown losses; decision quality unresolved (-339) | h91 call |
| `j972mgxmbp8t8nn506w6hfmx518fjytc` | -326 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-200) | h76 largest loss; unflagged |
| `j9718a9xgzxnhwxa1mmwfnvne58fkn3j` | -307 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-200) | h24 largest loss; unflagged |
| `j97fb258vkgcfw7pyjkh52fvxd8fkmxs` | -306 | 0 / 0 | +0 | +65 | Other all-in losses; decision quality unresolved (-200) | h10 largest loss; unflagged |
| `j977q0ets2e8j4dvxcj1p4yyrs8fk6fd` | -305 | 1 / 0 | +98 | +0 | Probable bad terminal call (-200) | h90 call |
| `j9721qvs31v9ebbaeespea40w98fjx68` | -303 | 1 / 0 | +77 | -194 | Other all-in losses; decision quality unresolved (-200) | h36 call |
| `j97bbz0e77dg4b7zk6n6n0y43d8fje5b` | -292 | 2 / 0 | +58 | +0 | Probable bad terminal call (-117) | h22 call, h80 call |
| `j97295bjssf4404tt0x8phvvh98fjfd5` | -291 | 4 / 0 | +138 | +0 | Probable bad terminal call (-336) | h18 call, h33 call, h51 call, h62 call |
| `j973h91j8edq7ka148eda5frpn8fjtr4` | -284 | 0 / 0 | +0 | -64 | Other all-in losses; decision quality unresolved (-200) | h30 largest loss; unflagged |
| `j9700cn57x7b96grstqkmd5ms98fjq1s` | -275 | 0 / 0 | +0 | -106 | Failed semibluff hands (-200) | h2 largest loss; unflagged |
| `j973bxved5k1spgkpkmjzy6aps8fkqwk` | -269 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-253) | h57 largest loss; unflagged |
| `j97aaa15ndw4wr733az9s5jmzd8fja7p` | -261 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-296) | h94 largest loss; unflagged |
| `j978d1gh5sd825xqjc8grpvxph8fjpef` | -251 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-172) | h95 largest loss; unflagged |
| `j97bbbevw8nejqnp358sywrn3x8fj7x8` | -232 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-200) | h90 largest loss; unflagged |
| `j972gkt64v39e1b23dg0hsvbad8fky17` | -230 | 1 / 0 | +9 | +0 | Other showdown losses; decision quality unresolved (-200) | h16 call |
| `j97as8att7bed2ahyjgw7xx5w98fj3c6` | -230 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-205) | h71 largest loss; unflagged |
| `j972pypxt1bwrp1b9chk952ec98fj1rs` | -225 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-332) | h79 largest loss; unflagged |
| `j978t5c55vev354s4gy3dx0hb58fjbfd` | -214 | 0 / 0 | +0 | -38 | Failed semibluff hands (-200) | h34 largest loss; unflagged |
| `j971cjykg135pnq1bp3gjjh73d8fjbky` | -212 | 0 / 0 | +0 | +64 | Other showdown losses; decision quality unresolved (-285) | h28 largest loss; unflagged |
| `j976ffs9jmzbddcf2esygsm5kh8fjyh1` | -203 | 0 / 0 | +0 | +13 | Other showdown losses; decision quality unresolved (-406) | h40 largest loss; unflagged |
| `j97c4zm3baywym46z484mnp7798fjmjc` | -195 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-205) | h6 largest loss; unflagged |
| `j9766csh4g7af5q69g901253m58fjvvp` | -194 | 0 / 0 | +0 | -217 | Positive-EV all-in, lost runout (-200) | h72 largest loss; unflagged |
| `j97cy1rxv13nj3vmj6ev2gp9358fj6kn` | -189 | 2 / 0 | +170 | -13 | Probable bad terminal call (-213) | h18 call, h36 call |
| `j97fwcptg5rqqjprv4bghw4k4n8fkrk7` | -184 | 1 / 0 | +51 | +0 | Probable bad terminal call (-200) | h57 call |
| `j97barad4gy4c14378trk14tqs8fk3ar` | -178 | 1 / 0 | +171 | -102 | Other all-in losses; decision quality unresolved (-200) | h43 call |
| `j97etncgyb7ygjr42kk2ca2s958fkqck` | -176 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-131) | h46 largest loss; unflagged |
| `j9765tstj2ewnt9vhevmfzffk98fkph1` | -176 | 0 / 0 | +0 | -38 | Other all-in losses; decision quality unresolved (-200) | h15 largest loss; unflagged |
| `j97b5cncaqcscv22j7x1vxtdjx8fjbjj` | -174 | 0 / 0 | +0 | -153 | Failed semibluff hands (-200) | h20 largest loss; unflagged |
| `j9707pjc3cknz7f8575xm0e1e18fjy05` | -170 | 0 / 0 | +0 | -365 | Positive-EV all-in, lost runout (-200) | h57 largest loss; unflagged |
| `j9740mhws1x66vnfx02zts7nf58fjx9s` | -164 | 0 / 0 | +0 | -114 | Other all-in losses; decision quality unresolved (-200) | h69 largest loss; unflagged |
| `j973sdcr7p0c3y6xbrn4gxsprs8fjj6j` | -163 | 0 / 0 | +0 | -3 | Other all-in losses; decision quality unresolved (-400) | h60 largest loss; unflagged |
| `j97dx5x9yswbs04h1nach6fb5s8fjqf4` | -149 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-296) | h63 largest loss; unflagged |
| `j978cjya3dkg56c89tmspk3j2d8fkk0n` | -135 | 1 / 0 | -237 | -326 | Positive-EV all-in, lost runout (-200) | h47 call |
| `j97cc7d1gz5ajar1t1dx0f9bdd8fk89m` | -134 | 1 / 1 | +145 | +13 | Probable bad terminal call (-200) | h49 fold, h51 call |
| `j97er3npfg2z61jz8b1jqsqbqs8fjwf8` | -130 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-139) | h30 largest loss; unflagged |
| `j977y9rns9b9ytcnx9jbdbpeh98fkavc` | -129 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-95) | h46 largest loss; unflagged |
| `j97d6t8ssfw2nc69dp5h61r3bx8fjp31` | -126 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-108) | h83 largest loss; unflagged |
| `j974dagrebak85z3kzna2kwcth8fjzzf` | -116 | 1 / 0 | +22 | +139 | Other showdown losses; decision quality unresolved (-249) | h74 call |
| `j978nt1jb6cq1y87q7jvh3j5s98fj8gc` | -94 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-99) | h53 largest loss; unflagged |
| `j976hmcq9ppqcw17bc8g9qyxn98fkngp` | -89 | 0 / 0 | +0 | +0 | Failed semibluff hands (-98) | h98 largest loss; unflagged |
| `j976rg6mssjcfjbmpapzreakyh8fkehw` | -73 | 1 / 0 | +15 | +0 | Blind-only folds (-33) | h25 call |
| `j9723f2j399j94q4tbpc96s5718fkpfm` | -68 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-127) | h48 largest loss; unflagged |
| `j9714b22xh0dbnssx8dn6gqvqs8fj3am` | -64 | 1 / 0 | +111 | +316 | Probable bad terminal call (-200) | h0 call |
| `j979v4ag5kc2w2mcekeqkm2cv18fjbd9` | -63 | 0 / 0 | +0 | +324 | Other all-in losses; decision quality unresolved (-400) | h1 largest loss; unflagged |
| `j976kd1nsb2ty517pw0efknym98fkg1x` | -63 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-92) | h47 largest loss; unflagged |
| `j97bqfapw5q4bxshtay7014qzs8fjjhb` | -57 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-145) | h42 largest loss; unflagged |
| `j97cwn7mfw561b4n53b09g0mfd8fkeq2` | -54 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-191) | h59 largest loss; unflagged |
| `j9781gjnb66ggnte5x0w3v5z8n8fjx6r` | -52 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-78) | h95 largest loss; unflagged |
| `j970cdrww523rb9cgtafsg3ca98fkm1n` | -50 | 1 / 0 | +77 | +0 | Probable bad terminal call (-121) | h53 call |
| `j9721p4hnf36qh4n7wbcq1gymn8fjm3f` | -47 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-126) | h88 largest loss; unflagged |
| `j97aebk5dd84qtjmea54a6te1d8fjq07` | -46 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-60) | h41 largest loss; unflagged |
| `j97dabwmdwk93fkb8nxbantbx58fj3tz` | -44 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-106) | h60 largest loss; unflagged |
| `j979143nh186jascck40ed9h4s8fj5a7` | -42 | 0 / 0 | +0 | +0 | Blind-only folds (-32) | h32 largest loss; unflagged |
| `j97aada5hbb8ekbmg3yh0t6ecd8fj5px` | -41 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-113) | h48 largest loss; unflagged |
| `j978e2n65hmasa7643pnwxpj6s8fj5sj` | -35 | 0 / 0 | +0 | +0 | Failed semibluff hands (-57) | h90 largest loss; unflagged |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` | -27 | 3 / 0 | +206 | +24 | Probable bad terminal call (-311) | h0 call, h66 call, h90 call |
| `j975cta3n0hnz9hjz27j4bnbm18fjkx2` | -16 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-200) | h56 largest loss; unflagged |
| `j97apzbwbfh7a9xpg7d36t037s8fk4zy` | -15 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-116) | h50 largest loss; unflagged |

## Chronology and limits on current-version conclusions

| Time quarter, Melbourne | Games | Chips | Folds / hands | Terminal flags |
|---|---|---|---|---|
| 03 Oct 17:30:46 – 03 Oct 19:03:18 | 35 | -2,910 | 3,107/3,500 | 19 |
| 03 Oct 19:06:14 – 03 Oct 20:55:41 | 35 | -1,402 | 3,024/3,500 | 23 |
| 03 Oct 20:58:20 – 03 Oct 22:27:57 | 35 | -1,768 | 3,173/3,500 | 5 |
| 03 Oct 22:30:07 – 04 Oct 00:29:38 | 35 | -692 | 3,152/3,500 | 1 |

The latest 20 games contain 0 bad-terminal-call flags and 0 missed-terminal-call flags, with 1,764 folds (88.20% of hands). No flag is not a certificate of correct play: this method does not solve all preflop, raise-sizing, bluff and future-street decisions. Timestamp units are normalized for ordering. The report does not infer deployment boundaries from a name or a validation game.

## All probable blunders: action-level review list

The full CSV includes every action. This shorter list contains only provable or probable terminal decision flags. “Actual EV” uses hidden cards and must not be substituted for the public-information decision models. Positive hand chips do not remove a decision flag.

| Match / hand / action # | Class | Cards / board | Call / pot | Public call EV: tight / loose | Actual call EV | Hand chips |
|---|---|---|---|---|---|---|
| `j974dagrebak85z3kzna2kwcth8fjzzf` / 74 / 17 | bad_terminal_call | 7d Kd / 9s 3c Jh Qs 9h | 22 / 77 | -21.8 / -20.2 | -22.0 | -49 |
| `j978cjya3dkg56c89tmspk3j2d8fkk0n` / 47 / 15 | bad_terminal_call | 4s 4c / 7h 3c Jc 7c | 170 / 237 | -86.6 / -26.9 | +186.1 | 207 |
| `j97barad4gy4c14378trk14tqs8fk3ar` / 43 / 15 | bad_terminal_call | Jh Th / Kh Ah 4c 9s | 171 / 235 | -56.4 / -48.9 | -69.5 | -200 |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / 16 / 10 | missed_terminal_call | 9d 9h / (preflop) | 194 / 408 | +40.7 / +73.1 | +70.2 | -6 |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / 46 / 9 | missed_terminal_call | Js Jh / (preflop) | 195 / 407 | +145.6 / +144.8 | +222.9 | -5 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / 1 / 9 | missed_terminal_call | 8c 8d / (preflop) | 195 / 208 | +21.7 / +29.2 | +100.6 | -5 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / 15 / 8 | missed_terminal_call | 6s 6c / (preflop) | 198 / 403 | +34.8 / +51.8 | -67.2 | -2 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / 16 / 9 | missed_terminal_call | As Jc / (preflop) | 195 / 606 | +41.1 / +46.9 | -154.3 | -5 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / 55 / 8 | missed_terminal_call | Qd 8s / (preflop) | 198 / 203 | +15.0 / +15.9 | +102.0 | -2 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / 69 / 10 | missed_terminal_call | 9s 9d / (preflop) | 195 / 406 | +33.9 / +70.4 | -61.1 | -5 |
| `j976xc3rrc1640xgtgw3rp71ah8fjvgp` / 46 / 20 | bad_terminal_call | Jc Jd / Kh Qc 8d 5c Ah | 12 / 75 | -11.2 / -3.1 | -12.0 | -28 |
| `j97fwcptg5rqqjprv4bghw4k4n8fkrk7` / 57 / 17 | bad_terminal_call | Qs Ks / 9d Ac Ts 6s 4c | 51 / 361 | -49.4 / -25.2 | -51.0 | -200 |
| `j971kadp8metddwct3kzpec8v98fje85` / 47 / 18 | bad_terminal_call | Js Ad / Qh Qd 7s 2d 6d | 118 / 289 | -112.9 / -53.9 | -118.0 | -200 |
| `j97bbz0e77dg4b7zk6n6n0y43d8fje5b` / 22 / 16 | bad_terminal_call | Kd Qh / 2s As 3s Ks 3d | 21 / 86 | -18.6 / -7.2 | -21.0 | -52 |
| `j97bbz0e77dg4b7zk6n6n0y43d8fje5b` / 80 / 14 | bad_terminal_call | As Jh / 3d 9c 9s 7s Qs | 37 / 95 | -33.1 / -12.1 | -37.0 | -65 |
| `j9747adj32h8tb2vjggd8kve058fkpv6` / 74 / 17 | bad_terminal_call | Tc Ac / 2s 2c Jh 6c 9d | 28 / 84 | -26.5 / -7.8 | -28.0 | -55 |
| `j972gkt64v39e1b23dg0hsvbad8fky17` / 16 / 14 | bad_terminal_call | Kd 9d / Tc Js 6s Td Ts | 9 / 37 | -8.0 / -3.7 | -9.0 | -23 |
| `j977vnk0vrtb95pjnceye3ftys8fkdqd` / 91 / 16 | bad_terminal_call | Ts Th / Kd Ac 3d 6s 7d | 29 / 117 | -24.5 / -8.1 | -29.0 | -70 |
| `j97bmsfrarq8fgfmqjqk4dach58fk9t0` / 16 / 17 | bad_terminal_call | 3s As / 3c Qh 7c Ks Js | 115 / 286 | -112.9 / -93.0 | -115.0 | -200 |
| `j97c22vg42mqkf2amq3hgan5pn8fkd9z` / 6 / 12 | bad_terminal_call | 9h Th / As Tc 6d Kh | 164 / 239 | -112.8 / -74.5 | -164.0 | -200 |
| `j97c22vg42mqkf2amq3hgan5pn8fkd9z` / 8 / 17 | bad_terminal_call | Ts Ah / 4c 7h 2d 4s 9c | 35 / 142 | -32.4 / -10.3 | -35.0 | -88 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / 18 / 17 | bad_terminal_call | 3d 3c / 7d Js 4s 9h 2c | 25 / 87 | -23.5 / -9.3 | +87.0 | 57 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / 33 / 14 | bad_terminal_call | Kc Jc / 6d Ts Ac 6c 3h | 125 / 250 | -123.1 / -98.5 | -125.0 | -186 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / 51 / 14 | bad_terminal_call | 9c Ac / Ts 6s 4d Qh 6h | 20 / 46 | -17.5 / -7.4 | -20.0 | -33 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / 62 / 19 | bad_terminal_call | Ac Kd / 3d 5h Qd Th 5s | 80 / 160 | -75.1 / -45.5 | -80.0 | -117 |
| `j97cc7d1gz5ajar1t1dx0f9bdd8fk89m` / 49 / 10 | missed_terminal_call | Jd Jc / (preflop) | 182 / 227 | +94.1 / +90.7 | -126.3 | -18 |
| `j97cc7d1gz5ajar1t1dx0f9bdd8fk89m` / 51 / 13 | bad_terminal_call | Th Tc / As 8h 2c 3c | 145 / 257 | -75.5 / -14.0 | -132.4 | -200 |
| `j974dc0xqb3tv788pqtx2qs5118fj5nr` / 14 / 14 | bad_terminal_call | 3c 3h / Qc 2c 5d 8d Js | 49 / 122 | -46.0 / -25.8 | -49.0 | -84 |
| `j974s0bzmh9pw0t4gyjfg9ndgs8fk7a8` / 76 / 14 | bad_terminal_call | 5c 5s / Qd Ad Jh As 7s | 41 / 98 | -40.0 / -27.6 | -41.0 | -68 |
| `j974s0bzmh9pw0t4gyjfg9ndgs8fk7a8` / 94 / 17 | bad_terminal_call | Kh Qc / 2d 7s Jh As 2c | 21 / 85 | -20.3 / -13.2 | -21.0 | -52 |
| `j974s0bzmh9pw0t4gyjfg9ndgs8fk7a8` / 97 / 15 | bad_terminal_call | 8d 8h / Td Ah 2s Jd Js | 39 / 138 | -36.4 / -18.4 | -39.0 | -88 |
| `j9721qvs31v9ebbaeespea40w98fjx68` / 36 / 18 | bad_terminal_call | Qh 9h / 4h 9c 6c Th Kd | 77 / 163 | -39.7 / -12.4 | -77.0 | -117 |
| `j977q0ets2e8j4dvxcj1p4yyrs8fk6fd` / 90 / 15 | bad_terminal_call | Jd Jh / Qh Kc 3s 4h 2c | 98 / 305 | -78.5 / -14.7 | -98.0 | -200 |
| `j97cy1rxv13nj3vmj6ev2gp9358fj6kn` / 18 / 12 | bad_terminal_call | Ad Kc / Qs 2h 3c | 166 / 241 | -72.9 / -23.4 | -152.9 | -200 |
| `j97cy1rxv13nj3vmj6ev2gp9358fj6kn` / 36 / 14 | bad_terminal_call | Jh 9h / Ks 2h 5c Ah 8c | 4 / 22 | -4.0 / -3.7 | -4.0 | -13 |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` / 0 / 15 | bad_terminal_call | Kd Jd / Td Tc 2h 7d Ah | 27 / 86 | -26.0 / -11.9 | -27.0 | -55 |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` / 66 / 17 | bad_terminal_call | 5s As / Jd 2d 5d 6c Qh | 146 / 256 | -136.1 / -83.9 | -146.0 | -200 |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` / 90 / 17 | bad_terminal_call | 4h 4d / Kc 7h Td Jh Kh | 33 / 81 | -32.2 / -23.1 | -33.0 | -56 |
| `j970cdrww523rb9cgtafsg3ca98fkm1n` / 53 / 21 | bad_terminal_call | Kd Ac / Js Td Jh 5h 6s | 77 / 180 | -67.9 / -17.9 | -77.0 | -121 |
| `j9753q4prs3c6bhs199tsmh9q58fkqsx` / 20 / 15 | bad_terminal_call | 7d 7c / 9d 9h Ah Kc Qh | 29 / 93 | -27.5 / -19.6 | -29.0 | -58 |
| `j979vjkbbsane1yx9v9bg0df2x8fk24s` / 91 / 14 | bad_terminal_call | Ah 2h / 6d Js Tc 7d 6h | 19 / 61 | -18.0 / -10.3 | -19.0 | -39 |
| `j972wgk491evwkhkbgxnvyj4p18fkgzk` / 79 / 10 | missed_terminal_call | Qh Ac / (preflop) | 176 / 230 | +53.5 / +52.1 | +66.5 | -24 |
| `j9714b22xh0dbnssx8dn6gqvqs8fj3am` / 0 / 17 | bad_terminal_call | Ac Qh / 7d Th Ts 2s Kd | 111 / 297 | -100.2 / -42.0 | -111.0 | -200 |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` / 36 / 14 | bad_terminal_call | Th Ah / 8c 8s 5c 6s 4h | 34 / 79 | -19.7 / -5.2 | -34.0 | -55 |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` / 84 / 21 | bad_terminal_call | Ah Jh / Ts 2c 7h Qd 5h | 128 / 256 | -121.6 / -89.1 | -128.0 | -185 |
| `j979byv2162hsqb5wx5zmbsvw18fjz8r` / 29 / 19 | bad_terminal_call | Jh Jc / Kd As 3c 9h 6d | 151 / 255 | -139.0 / -71.8 | +255.0 | 206 |
| `j976rg6mssjcfjbmpapzreakyh8fkehw` / 25 / 17 | bad_terminal_call | Jc Ad / 8d Ts 4c 5h 2h | 15 / 40 | -10.1 / -2.8 | -15.0 | -25 |
| `j977j6f97yt9zc2e4yeym1956h8fjg1e` / 70 / 18 | missed_terminal_call | 6s 6c / 3h 3s 4h 4s | 157 / 256 | +34.7 / +83.2 | -118.3 | -43 |

## Method, verification and limitations

The source contains 1,674,234 rows from 1,809 matches. Metadata lists 143 Halliday matches; 143 have replay actions (0 missing). The 3 validation games contribute 6 hands and -156 chips and are excluded from ladder rates. All replays combined: 14,006 hands, 17,865 actions, -6,928 chips.

Every recorded pot, legal action amount, seat/name mapping, hole-card consistency check, final seat/bot delta, odd-chip allocation and pot winner was checked. All 143 match totals reconcile; hands are contiguous, and 0 target hands failed reconstruction. The independent SDK evaluated 6,023 contested pot layers.

Call EV is expected hero-eligible gross payout minus the additional call. Already invested chips are sunk. For terminal decisions, no additional future betting is required. Nonterminal estimates assume all currently live players match the current bet, within stack caps, then check down. They omit future raises, folds, implied odds and value bets.

The actual-hand calculation conditions on all recorded hole cards, including folded cards, and only the board visible at the decision. Flop/turn runouts are enumerated exactly; preflop uses 4,096 seeded runouts. Future board cards do not choose the sampled runouts. Fractional tied payouts are used for EV, while actual settlement separately checks integer odd chips.

Public models see only Halliday’s hole cards, the visible board and preceding public actions. They do not see hidden opponent cards or future outcomes. Tight preflop VPIP/PFR/3-bet widths are 22%/12%/5%; loose widths are 45%/30%/14%. Postflop bet/call cutoffs and bluff floors are 0.75/0.50/0.10 versus 0.55/0.30/0.30. An opponent publicly observed to shove in at least 80% of eight or more prior hands receives an any-two preflop prior when shoving. Other players retain their own likelihood updates. Hole cards are sampled jointly with collision rejection.

Both models scored 1,196 facing-bet contexts: every terminal opportunity and heads-up postflop opportunities. Terminal estimates use 8,192 samples per model; others use 4,096. A probable flag requires both models to disagree with the action by more than two chips after a 1.96-standard-error sampling margin. That margin covers Monte Carlo noise, not range-model error or the many decisions screened. Both models share the repository’s action-likelihood functions, so they are sensitivity checks, not independent empirical validation or a poker solver. Preflop raise size is not fully modeled as a range signal.

All actions receive a classification, but checks and raises are not exhaustively optimized. A not-flagged action may have unassessed alternatives. The total error rate cannot be inferred from the fraction of labels marked probable. Neither lost chips nor a hidden-card winner alone proves a blunder.

| GPU worker | Games scored | Seven-card rankings | Device buffers |
|---|---|---|---|
| cuda:0 | 35 | 83,569,563 | 1,179,648 bytes |
| cuda:1 | 35 | 82,534,284 | 1,179,648 bytes |
| cuda:2 | 37 | 83,097,419 | 1,179,648 bytes |
| cuda:3 | 36 | 84,554,985 | 1,179,648 bytes |

4 V100 workers ran in parallel and executed 333,756,251 actual CUDA seven-card rankings. The computation stage took 16.9 seconds, including worker startup and result serialization. Each worker also needs a CUDA context beyond the listed buffers. Packed GPU rankings are checked against CPU evaluation at startup. Extraction, reconstruction, verification and rendering are separate stages.

Final verification: 7 audit tests passed. All 17,865 action IDs and 14,006 hand IDs are unique, all 143 match totals and exclusive loss buckets reconcile, and prior histories contain no future actions. Both public-range models were reproduced exactly in 10 representative contexts after removing every field outside the explicit public-information allowlist. The source SHA-256 was unchanged after computation. Source-code fingerprints, tested context IDs and test output are retained alongside this report.

## Prioritized improvements to test

| Priority | Change to investigate | Validation |
|---|---|---|
| 1 | Calibrate large river calls after repeated aggression, particularly ace-high and weak pairs. | Replay flagged contexts and test on untouched matches; preserve profitable calls. |
| 2 | Review marginal turn calls and the planned response to a blank river. | Measure complete hand outcomes; avoid double-counting alternative fold points. |
| 3 | Distinguish known frequent shovers from selective callers of their shoves. | Use earlier public actions only; test different field compositions. |
| 4 | Audit range updates and one-pair stack commitments after reraises. | Log equity/ranges/timing and compare predictions with held-out evidence. |
| 5 | Record version hashes, verdicts and decision diagnostics. | Separate historical leaks, current behavior, range errors and clock fallback. |

## Files and reproduction

[Every action and classification](../results/halliday-performance-20261004/action-classifications.csv) · [Probable blunders](../results/halliday-performance-20261004/blunders.csv) · [Every match review](../results/halliday-performance-20261004/match-reviews.csv) · [Every hand outcome](../results/halliday-performance-20261004/hand-outcomes.csv) · [Summary JSON](../results/halliday-performance-20261004/summary.json).

[Detailed actions with full prior histories](../results/halliday-performance-20261004/classified-actions.json), [reconstruction audit](../results/halliday-performance-20261004/reconstruction-audit.json), [input fingerprints](../results/halliday-performance-20261004/extraction.json), [GPU work](../results/halliday-performance-20261004/gpu-work.json), and [final verification](../results/halliday-performance-20261004/verification.json) retain the evidence. Large result files are local and Git-ignored. Preserve the result directory when collecting a newer snapshot.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py extract --snapshot analysis/results/input-snapshot --directory analysis/results/halliday-performance-20261004
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py prepare --directory analysis/results/halliday-performance-20261004
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py compute --devices 0,1,2,3 --directory analysis/results/halliday-performance-20261004
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_report.py --directory analysis/results/halliday-performance-20261004
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/verify_halliday_report.py --directory analysis/results/halliday-performance-20261004
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/render_halliday_report.py --directory analysis/results/halliday-performance-20261004
```
