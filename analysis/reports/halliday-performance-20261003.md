# Halliday replay performance and decision audit — 3 October 2026

Source: the current `analysis/results/input-snapshot/actions.jsonl`, SHA-256 `b01b93cee5535e943fa14219ef3bdce2e4dbbf09ec3b8710098f5847be6655cc`. The recorded identity is `Halliday`. Main findings cover 110 eight-player ladder games (11,000 hands), with recorded match timestamps 03 Oct 17:30:46–03 Oct 22:39:56, Australia/Melbourne time. Three two-hand validation games are reported separately. Hand numbers are the replay’s zero-based numbers.

Analysis completed on 4 October 2026. The report date and filenames identify the 3 October replay snapshot.

## Findings

The clearest decision weakness is expensive calling with weak hands, particularly on the river. The conservative review flags 38 terminal calls under both tested public-information range models; 33 are river calls. Folding at those selected terminal decisions would have improved these recorded hand results by 1,717 chips, including 1,308 on the river. This is a retrospective what-if within the same hands, not a forecast of a strategy change or a claim that every losing call was wrong.

The large fold count mostly comes from preflop play. There are 10 range-model missed-call flags, of which 5 also have positive call EV against the actual hidden cards. No fold was proved to surrender a free check or a guaranteed profitable terminal call. A blanket instruction to fold less is unsupported by this audit.

Runout variance is material: across 94 auditable all-in runouts, actual results were -3,624 chips versus -206.1 expected with the actual hands held, a -3,417.9-chip difference. This calculation isolates the final runout after betting finished; it neither validates the earlier betting nor estimates the bot’s complete skill-adjusted win rate.

| Metric | Ladder result |
|---|---|
| Matches / hands / decisions | 110 / 11,000 / 13,994 |
| Net chips | -6,217 |
| Net big blinds / 100 hands | -28.26 |
| Mean chips per 100-hand game, approximate 95% interval | -56.52 ± 47.92 |
| Positive / negative games | 51 / 59 |
| Last 20 games | -1,653 chips; -41.33 bb/100 |

The interval treats games as independent units; shared opponents, contemporaneous bot changes, or related deals can weaken that assumption. Replay records contain no Halliday version hash, decision clock, or internal equity estimate, so these are findings about the observed identity over this period. They do not establish which current source-code branch produced any hand.

## How often does Halliday fold?

Halliday folded in 9,761/11,000 ladder hands (88.74%). It folded preflop in 9,429 hands (85.72% of all hands), and postflop in 332 hands. Folds were 69.75% of all decisions, or 79.49% of decisions facing a positive call price. These denominators measure different things.

| Street | Folds | Decisions facing a bet | Fold rate when facing a bet | Calls | Raises |
|---|---|---|---|---|---|
| Preflop | 9,429 | 11,153 | 84.54% | 667 | 1,063 |
| Flop | 160 | 577 | 27.73% | 384 | 411 |
| Turn | 109 | 347 | 31.41% | 220 | 216 |
| River | 63 | 203 | 31.03% | 133 | 137 |

Raise counts include both opening bets and raises; only raises facing a positive call price enter the facing-bet denominator. A hand can contain several decisions but only one Halliday fold. There were no folded pocket aces, and no unopened folds of TT–AA or AK. The preflop fold rate was also broadly stable across hand-number deciles, giving no positive evidence here for late-game check/fold fallback; clocks and verdicts would be needed to diagnose that mechanism.

## How often were folds unnecessary?

An unnecessary fold cannot be identified just because the hidden opponent was weak or a favorable card later arrived. The main checks below use terminal opportunities: a call closes the river action, or betting exposure is over because at most one live player would retain chips. Side-pot eligibility and already-invested chips are accounted for.

| Evidence standard | Count | Interpretation |
|---|---|---|
| Provably avoidable fold | 0 | No free-check fold or guaranteed-profitable terminal fold found. This is a lower bound, not proof that every fold was correct. |
| Public-range missed-call flag | 10 | 0.10% of all folds; 10.53% of 95 terminal folds. Both range models exceed +2 chips after Monte Carlo uncertainty. |
| Public-range flag AND profitable against actual hands | 5 | 0.05% of all folds. Strongest review candidates under this method; still model-dependent. |
| Profitable against actual hands, terminal call | 16 | 16.84% of terminal folds; 0.16% of all folds. Perfect-information hindsight. |
| Of those, river calls that would win/share | 6 | Direct hindsight on the finished board; the opponent’s cards were hidden when the fold occurred. |

The 95 terminal folds comprise 26 preflop, 1 flop, 14 turn and 54 river spots. Most folds have unresolved future betting, so this method does not estimate a complete true unnecessary-fold rate. Among the 10 model flags, only 5 were favorable against the actual hidden hands; their combined hidden-hand call EV is +35.0 chips. That is a reason to review the specific spots rather than automatically reverse every flagged fold.

Two looser hindsight counts are retained in the data but are excluded from the blunder total: 3,097 folds had positive call EV in a hypothetical checkdown where all currently live opponents match the current bet, and 388 would share the recorded final-board showdown against the opponents live at the fold. A final board was available for only 2,209 folded hands. These counts use hidden cards, conditional future boards or unrealistic future betting assumptions; they are not counts of unnecessary folds.

### Best-supported missed-call examples

| Match / hand | Holding / decision | Call price | Public model call EV, chips | Actual-hand call EV, chips |
|---|---|---|---|---|
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / h46 | Js Jh / preflop | 195 into 407 | +145.6 / +144.8 | +222.9 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / h55 | Qd 8s / preflop | 198 into 203 | +15.0 / +15.9 | +102.0 |
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` / h1 | 8c 8d / preflop | 195 into 208 | +21.7 / +29.2 | +100.6 |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` / h16 | 9d 9h / preflop | 194 into 408 | +40.7 / +73.1 | +70.2 |
| `j972wgk491evwkhkbgxnvyj4p18fkgzk` / h79 | Qh Ac / preflop | 176 into 230 | +53.5 / +52.1 | +66.5 |

The JJ fold in `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr`, hand 46, is a useful adaptation review: Jason_idea had visibly shoved in all 46 previous hands, and jongwon had called this shove. Calling 195 into 407 needs about 32.4% pot share. Both range models favor calling; the actual opponents held 5d 4c and Ad 5s. The extra caller still needs its own range; the evidence supports an opponent-specific adjustment.

## Weaknesses and their evidence

### 1. Expensive river bluff-catching with weak holdings

33 of 133 river calls were negative under both sensitivity models. Their actual net marginal result was -1,308 chips; earlier sunk investments are excluded. Typical flags are ace-high, a missed draw, or a small pair after continued aggression. The 38 total terminal-call flags occur in 27 games and include some winning hands; labels were not assigned just because the hand lost.

| Match / hand | Hole cards | Board | Call / pot before call | Model call EV: tight / loose | Hand result |
|---|---|---|---|---|---|
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` / h66 | 5s As | Jd 2d 5d 6c Qh | 146 / 256 | -136.1 / -83.9 | -200 |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` / h84 | Ah Jh | Ts 2c 7h Qd 5h | 128 / 256 | -121.6 / -89.1 | -185 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` / h33 | Kc Jc | 6d Ts Ac 6c 3h | 125 / 250 | -123.1 / -98.5 | -186 |
| `j971kadp8metddwct3kzpec8v98fje85` / h47 | Js Ad | Qh Qd 7s 2d 6d | 118 / 289 | -112.9 / -53.9 | -200 |
| `j97bmsfrarq8fgfmqjqk4dach58fk9t0` / h16 | 3s As | 3c Qh 7c Ks Js | 115 / 286 | -112.9 / -93.0 | -200 |
| `j9714b22xh0dbnssx8dn6gqvqs8fj3am` / h0 | Ac Qh | 7d Th Ts 2s Kd | 111 / 297 | -100.2 / -42.0 | -200 |

### 2. Turn calls that create expensive river decisions

There are 23 additional nonterminal call-review flags, 20 on the turn. Both range models give negative immediate checkdown EV, but future betting and implied odds prevent a firm blunder label. These flags often precede the expensive river calls, so their costs must not be added together.

Example: `j97bmsfrarq8fgfmqjqk4dach58fk9t0`, hand 16. With As 3s on 3c Qh 7c Ks, Halliday called 64 into 107; the two model EVs are −43.4 and −22.9 chips. It then called another 115 on the Js river and lost the 200-chip stack to Kh Qs. Folding the turn would have limited the loss to 21 chips; folding the river would have limited it to 85. Those are alternative stopping points, not additive savings.

### 3. Large commitments with one-pair or weak two-pair hands need review

Some stack losses cannot be robustly called blunders by the range models, yet show a practical review target: repeated raises or calls after strong opposing action with modest made hands. In `j9711athmk9nrrsvqpyp0yjnfn8fkk0v`, hand 54, Ah Js raised to 75 and then called 112 on 5h Qc Qs Jc; it had no winning runout against the actual opponent. The public models disagree about the final call, so this remains an overvaluation/range-calibration candidate. Other losses involve sets or overpairs against stronger hands and should not all be “fixed” by folding more.

### 4. Shove adaptation should remain opponent-specific

The most credible missed preflop calls cluster in games with an almost-always-shoving opponent. The audit switches that opponent to an any-two prior only after at least eight earlier hands with an observed shove rate of 80% or more; this uses public past actions only. Applying the same adjustment to callers of the shove would ignore their distinct selection. The report’s ten missed-call flags include five that would have been unfavorable against the actual held cards, illustrating the model risk.

### 5. Failed bluffs exist, but do not dominate the measured loss

The conservative high-card/no-draw definition found 6 failed-air-bet action flags and 10 failed-semibluff flags. These are outcome labels, not established strategic errors. A profitable bluffing strategy necessarily loses some called bets; this audit does not model counterfactual opponent responses to alternative bet sizes.

## What went wrong in the losing matches?

The 59 negative ladder games lost 14,389 chips in total, offset elsewhere by the positive games. The following exclusive per-hand buckets reconcile exactly to that subtotal. They explain where chips went; only the explicitly labeled call/fold buckets carry a range-model error flag. A hand can contain several questionable actions but is counted once here.

| Hand bucket in negative games | Hands | Actual chips |
|---|---|---|
| Other showdown losses | 84 | -6,543 |
| Other all-in losses; cause unresolved | 26 | -5,200 |
| Probable bad terminal call | 28 | -3,349 |
| Positive-EV all-in, lost runout | 16 | -3,200 |
| Postflop investment, then fold | 176 | -2,365 |
| Blind-only folds | 1,169 | -1,696 |
| Failed semibluff hands | 7 | -623 |
| Preflop investment, then fold | 79 | -468 |
| Probable missed terminal call | 9 | -91 |
| Failed high-card bluff hands | 4 | -77 |
| Winning / break-even hands | 4,302 | +9,223 |

### The worst game was heavily affected by runouts

`j97ezzf8me25j31ymxdvq6pakd8fk0w0` finished −846. Its 13 auditable all-ins produced −790 chips, versus about +964 expected with the hands actually held: roughly −1,754 chips of runout difference. Seven lost all-in hands had positive total hand EV before the final runout. There are also specific missed-call flags, but they do not explain the dominant loss mechanism in this game.

`j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` finished −656. Its three completed all-ins all had positive hand EV in the audit: expected total about +253, actual −600. In hand 40, Ad Ac lost despite about 83% all-in showdown share against the actual field. The game also contains the JJ missed-call candidate above. Both decision review and variance are relevant.

### Examples with clearer decision problems

`j97bmsfrarq8fgfmqjqk4dach58fk9t0` (−534) contains the bottom-pair turn/river call sequence described above. `j974pfs1yezgpyq5811ad2cr8s8fjzv0` (−493), hand 84, called 128 with Ah Jh on Ts 2c 7h Qd 5h; this ace-high call needed 33.3% equity, while the two public models implied strongly negative EV. `j971kadp8metddwct3kzpec8v98fje85` (−685), hand 47, called 118 with Ad Js on Qh Qd 7s 2d 6d and lost to trip queens. Those hands are stronger evidence of a calling leak than the mere fact that each game ended negative.

## Every negative ladder match

“Call / fold flags” are public-model terminal review flags, including a flagged decision in a hand that happened to win. “Largest loss bucket” describes gross hand losses and is not automatically a blunder diagnosis. Full action sequences and exact IDs are available in the linked CSV/JSON files.

| Match | Net chips | Call / fold flags | Largest loss bucket | Example lost hand |
|---|---|---|---|---|
| `j97ezzf8me25j31ymxdvq6pakd8fk0w0` | -846 | 0 / 5 | Positive-EV all-in, lost runout (-1,400) | h3: Qs Qc, -200 |
| `j9711athmk9nrrsvqpyp0yjnfn8fkk0v` | -693 | 0 / 0 | Other all-in losses; cause unresolved (-600) | h2: Ks Kh, -200 |
| `j971kadp8metddwct3kzpec8v98fje85` | -685 | 1 / 0 | Other all-in losses; cause unresolved (-600) | h11: 8h 8d, -200 |
| `j973m8xrhq5vvtyfd8c7mxyvyh8fjkvr` | -656 | 0 / 2 | Positive-EV all-in, lost runout (-600) | h39: Ad Js, -200 |
| `j97bmsfrarq8fgfmqjqk4dach58fk9t0` | -534 | 1 / 0 | Probable bad terminal call (-200) | h16: 3s As, -200 |
| `j970pdtxxpjdqbj57pm0hssxb58fk4cq` | -503 | 0 / 0 | Other all-in losses; cause unresolved (-400) | h2: 3c 3s, -200 |
| `j974pfs1yezgpyq5811ad2cr8s8fjzv0` | -493 | 2 / 0 | Probable bad terminal call (-240) | h60: Kh Kc, -200 |
| `j97418jfme7vwm9t84ban33djs8fjs84` | -470 | 0 / 0 | Other all-in losses; cause unresolved (-200) | h22: Js Kc, -200 |
| `j977vnk0vrtb95pjnceye3ftys8fkdqd` | -466 | 1 / 0 | Positive-EV all-in, lost runout (-400) | h25: Ac Ad, -200 |
| `j975x29dfv8g5c916v07m5bw758fk6mk` | -394 | 0 / 0 | Other all-in losses; cause unresolved (-400) | h45: 9s 9c, -200 |
| `j97c22vg42mqkf2amq3hgan5pn8fkd9z` | -350 | 2 / 0 | Probable bad terminal call (-288) | h6: 9h Th, -200 |
| `j977j6f97yt9zc2e4yeym1956h8fjg1e` | -350 | 0 / 1 | Other all-in losses; cause unresolved (-200) | h45: Ah Jh, -200 |
| `j977nzda3se2wvzg1s9cqbj4dn8fkpwd` | -332 | 0 / 0 | Other showdown losses (-345) | h75: Jd Kd, -200 |
| `j979vjkbbsane1yx9v9bg0df2x8fk24s` | -329 | 1 / 0 | Other showdown losses (-339) | h93: 8s 8c, -200 |
| `j972mgxmbp8t8nn506w6hfmx518fjytc` | -326 | 0 / 0 | Other showdown losses (-200) | h76: 3d Ad, -200 |
| `j9718a9xgzxnhwxa1mmwfnvne58fkn3j` | -307 | 0 / 0 | Other showdown losses (-200) | h24: Qc Qs, -200 |
| `j977q0ets2e8j4dvxcj1p4yyrs8fk6fd` | -305 | 1 / 0 | Probable bad terminal call (-200) | h90: Jd Jh, -200 |
| `j9721qvs31v9ebbaeespea40w98fjx68` | -303 | 1 / 0 | Other all-in losses; cause unresolved (-200) | h76: As 8h, -200 |
| `j97bbz0e77dg4b7zk6n6n0y43d8fje5b` | -292 | 2 / 0 | Probable bad terminal call (-117) | h28: Jd Td, -101 |
| `j97295bjssf4404tt0x8phvvh98fjfd5` | -291 | 4 / 0 | Probable bad terminal call (-336) | h33: Kc Jc, -186 |
| `j973h91j8edq7ka148eda5frpn8fjtr4` | -284 | 0 / 0 | Other all-in losses; cause unresolved (-200) | h30: Kd Kc, -200 |
| `j9700cn57x7b96grstqkmd5ms98fjq1s` | -275 | 0 / 0 | Failed semibluff hands (-200) | h2: Ks As, -200 |
| `j973bxved5k1spgkpkmjzy6aps8fkqwk` | -269 | 0 / 0 | Other showdown losses (-253) | h57: Ac Td, -200 |
| `j97aaa15ndw4wr733az9s5jmzd8fja7p` | -261 | 0 / 0 | Other showdown losses (-296) | h94: Ad Kh, -200 |
| `j978d1gh5sd825xqjc8grpvxph8fjpef` | -251 | 0 / 0 | Other showdown losses (-172) | h95: Td Jd, -172 |
| `j972gkt64v39e1b23dg0hsvbad8fky17` | -230 | 1 / 0 | Other showdown losses (-200) | h53: 4h 4s, -200 |
| `j97as8att7bed2ahyjgw7xx5w98fj3c6` | -230 | 0 / 0 | Other showdown losses (-205) | h71: 9s Ac, -200 |
| `j972pypxt1bwrp1b9chk952ec98fj1rs` | -225 | 0 / 0 | Other showdown losses (-332) | h79: Td Th, -200 |
| `j978t5c55vev354s4gy3dx0hb58fjbfd` | -214 | 0 / 0 | Failed semibluff hands (-200) | h34: As Kc, -200 |
| `j971cjykg135pnq1bp3gjjh73d8fjbky` | -212 | 0 / 0 | Other showdown losses (-285) | h28: Ad Kh, -200 |
| `j976ffs9jmzbddcf2esygsm5kh8fjyh1` | -203 | 0 / 0 | Other showdown losses (-406) | h40: 8h Kh, -200 |
| `j97c4zm3baywym46z484mnp7798fjmjc` | -195 | 0 / 0 | Other showdown losses (-205) | h6: Ah 4h, -200 |
| `j9766csh4g7af5q69g901253m58fjvvp` | -194 | 0 / 0 | Positive-EV all-in, lost runout (-200) | h72: Ah Kh, -200 |
| `j97cy1rxv13nj3vmj6ev2gp9358fj6kn` | -189 | 2 / 0 | Probable bad terminal call (-213) | h18: Ad Kc, -200 |
| `j97fwcptg5rqqjprv4bghw4k4n8fkrk7` | -184 | 1 / 0 | Probable bad terminal call (-200) | h57: Qs Ks, -200 |
| `j97barad4gy4c14378trk14tqs8fk3ar` | -178 | 1 / 0 | Other all-in losses; cause unresolved (-200) | h5: Ts Tc, -200 |
| `j97etncgyb7ygjr42kk2ca2s958fkqck` | -176 | 0 / 0 | Other showdown losses (-131) | h46: Ts Th, -86 |
| `j9765tstj2ewnt9vhevmfzffk98fkph1` | -176 | 0 / 0 | Other all-in losses; cause unresolved (-200) | h15: Ad Kh, -200 |
| `j978cjya3dkg56c89tmspk3j2d8fkk0n` | -135 | 1 / 0 | Positive-EV all-in, lost runout (-200) | h62: As Qc, -200 |
| `j97cc7d1gz5ajar1t1dx0f9bdd8fk89m` | -134 | 1 / 1 | Probable bad terminal call (-200) | h51: Th Tc, -200 |
| `j97er3npfg2z61jz8b1jqsqbqs8fjwf8` | -130 | 0 / 0 | Other showdown losses (-139) | h30: As Ac, -133 |
| `j977y9rns9b9ytcnx9jbdbpeh98fkavc` | -129 | 0 / 0 | Postflop investment, then fold (-95) | h46: 8h 8s, -59 |
| `j97d6t8ssfw2nc69dp5h61r3bx8fjp31` | -126 | 0 / 0 | Postflop investment, then fold (-108) | h83: Ac Qc, -95 |
| `j974dagrebak85z3kzna2kwcth8fjzzf` | -116 | 1 / 0 | Other showdown losses (-249) | h83: Th Td, -200 |
| `j976hmcq9ppqcw17bc8g9qyxn98fkngp` | -89 | 0 / 0 | Failed semibluff hands (-98) | h98: Kd Ad, -98 |
| `j976rg6mssjcfjbmpapzreakyh8fkehw` | -73 | 1 / 0 | Blind-only folds (-33) | h25: Jc Ad, -25 |
| `j9723f2j399j94q4tbpc96s5718fkpfm` | -68 | 0 / 0 | Other showdown losses (-127) | h48: 9h Ac, -106 |
| `j9714b22xh0dbnssx8dn6gqvqs8fj3am` | -64 | 1 / 0 | Probable bad terminal call (-200) | h0: Ac Qh, -200 |
| `j979v4ag5kc2w2mcekeqkm2cv18fjbd9` | -63 | 0 / 0 | Other all-in losses; cause unresolved (-400) | h1: Ad Kd, -200 |
| `j97bqfapw5q4bxshtay7014qzs8fjjhb` | -57 | 0 / 0 | Postflop investment, then fold (-145) | h42: Ah Kd, -105 |
| `j97cwn7mfw561b4n53b09g0mfd8fkeq2` | -54 | 0 / 0 | Other showdown losses (-191) | h59: Qs As, -117 |
| `j9781gjnb66ggnte5x0w3v5z8n8fjx6r` | -52 | 0 / 0 | Postflop investment, then fold (-78) | h95: 4d 4c, -50 |
| `j970cdrww523rb9cgtafsg3ca98fkm1n` | -50 | 1 / 0 | Probable bad terminal call (-121) | h53: Kd Ac, -121 |
| `j97dabwmdwk93fkb8nxbantbx58fj3tz` | -44 | 0 / 0 | Postflop investment, then fold (-106) | h60: 6d 6h, -50 |
| `j97aada5hbb8ekbmg3yh0t6ecd8fj5px` | -41 | 0 / 0 | Other showdown losses (-113) | h48: Jh 9h, -98 |
| `j978e2n65hmasa7643pnwxpj6s8fj5sj` | -35 | 0 / 0 | Failed semibluff hands (-57) | h90: Kd Ah, -57 |
| `j978vaa5vs5k162fb9c4wv8vjh8fj03e` | -27 | 3 / 0 | Probable bad terminal call (-311) | h66: 5s As, -200 |
| `j975cta3n0hnz9hjz27j4bnbm18fjkx2` | -16 | 0 / 0 | Other showdown losses (-200) | h56: Jh Th, -200 |
| `j97apzbwbfh7a9xpg7d36t037s8fk4zy` | -15 | 0 / 0 | Other showdown losses (-116) | h50: Js Ah, -116 |

## Chronology and current-version limits

| Play-time quarter, Melbourne | Games | Chips | Folds / hands | Terminal model flags |
|---|---|---|---|---|
| 03 Oct 17:30:46 – 03 Oct 18:41:31 | 28 | -1,106 | 2,497/2,800 | 15 |
| 03 Oct 18:44:33 – 03 Oct 20:04:58 | 28 | -2,491 | 2,421/2,800 | 23 |
| 03 Oct 20:07:30 – 03 Oct 21:29:54 | 27 | -670 | 2,402/2,700 | 5 |
| 03 Oct 21:31:49 – 03 Oct 22:39:56 | 27 | -1,950 | 2,441/2,700 | 5 |

The last 20 recorded ladder games lost -1,653 chips over 2,000 hands. They contain 4 bad-terminal-call flags and 1 missed-terminal-call flags. The earlier and later rates differ, but opponent mix, cards and possible same-name code replacements are confounded. No deployment boundary is inferred.

## Method, audit coverage, and limitations

The source contains 1,531,380 rows from 1,689 matches. Metadata lists 114 Halliday matches; 113 have replay rows. The missing ladder match is `j978nt1jb6cq1y87q7jvh3j5s98fj8gc` (metadata −94 chips), so it is excluded from action-level conclusions. The 113 available games contain 11,006 hands and 14,012 Halliday decisions. The three validation games contribute six hands and −156 chips; all-replay total is −6,373 chips.

Every reconstructed action pot, seat/name mapping, legal recorded amount, hole-card consistency check, final seat and bot delta, odd-chip split and pot winner passed. All 113 match totals reconcile exactly with metadata; all hands are contiguous. The independent SDK evaluated 4,808 contested pot layers. No target hand was dropped as malformed.

Counterfactual call EV is expected hero-eligible gross payout minus the additional call, with already-invested chips treated as sunk. Side pots, dead chips and stack caps are explicit. For a terminal call this accounts for the remaining investment. For nonterminal checks it assumes all currently live opponents match the current bet and then check down; this deliberately limited diagnostic omits subsequent raises, folds, implied odds and future value betting.

The oracle calculation conditions on every recorded hole card and the board visible at the decision. It never uses future board cards to select runouts. Turn and flop runouts are enumerated exactly; preflop uses 4,096 seeded uniform runouts. Oracle results are perfect-information diagnostics, not information the bot could act on. The separate recorded-final-board measure is explicitly hindsight and is conditional on a board being recorded.

The two public-information models condition only on Halliday’s cards, the current board, previous betting, and the documented near-always-shover exception. Tight preflop widths are VPIP/PFR/3-bet = 22%/12%/5%; loose widths are 45%/30%/14%. Postflop betting/calling cutoffs and bluff floors are 0.75/0.50/0.10 versus 0.55/0.30/0.30, using the repository’s action-likelihood functions. Every current live opponent is sampled jointly with collision rejection; folded hidden cards are not exposed to these models. There is no fit using future hands or revealed opponent cards. These are sensitivity assumptions, not calibrated true opponent ranges; in particular a normal preflop size likelihood is not a full model of a 100-BB shove.

Both models were evaluated for 942 decision contexts: all facing-bet terminal spots and heads-up postflop facing-bet spots. Terminal estimates use 8,192 samples per model; other estimates use 4,096. A probable call/fold flag requires both models to disagree with the action by more than two chips after a 1.96-standard-error Monte Carlo margin. This margin covers simulation noise, not model error, multiple-comparison selection, or uncertainty about opponent behavior. All 14,012 actions receive a label; “not flagged” includes unassessed strategic alternatives and is not an optimal-play judgment.

All four V100 workers executed real CUDA ranking kernels in parallel: 261,586,752 seven-card rankings. Each worker uses fixed input/output buffers of 1,179,648 bytes (1.125 MiB), plus its CUDA context. Packed GPU ranks were checked against the CPU evaluator at worker startup; replay settlement was independently checked with the SDK. The final GPU calculation completed in about 12.4 seconds on this machine; extraction, reconstruction and reporting are separate.

Final verification: all 117 repository tests passed with CUDA enabled. Removing every hidden-card and outcome field left the public-range samples unchanged. The full source SHA-256 was rechecked after computation, all 14,012 action IDs are unique, and every target chip total reconciles.

## Prioritized follow-up

| Priority | Change to investigate | How to validate |
|---|---|---|
| 1 | Tighten large river calls with ace-high, missed draws and small pairs after repeated aggression. | Replay the flagged contexts, then compare on held-out games; retain the winning value calls. |
| 2 | Review turn calls with poor immediate equity and no credible draw; avoid committing again on a missed river. | Track both streets within a hand so the same loss is not counted twice. |
| 3 | Check big one-pair raises and range updates after reraises. | Inspect logs of equity, range weights and clocks; separate coolers from optimistic opponent assumptions. |
| 4 | Adapt to publicly proven shove-heavy opponents while modeling cold callers separately. | Test the identified shove games and an independent field; do not substitute all opponents with random cards. |
| 5 | Collect version hashes, verdicts, decision timings and internal range/equity diagnostics. | Use these to distinguish strategy mistakes, stale versions, estimation failures and time-bank fallback. |

## Files and reproduction

[Every action: classifications and EVs](../results/halliday-performance-20261003/action-classifications.csv) · [Every match review](../results/halliday-performance-20261003/match-reviews.csv) · [Every hand outcome](../results/halliday-performance-20261003/hand-outcomes.csv) · [Structured summary](../results/halliday-performance-20261003/summary.json).

[Detailed classified decisions](../results/halliday-performance-20261003/classified-actions.json) retain each decision’s board, hole cards, live players, contributions and prior action sequence. [Reconstruction audit](../results/halliday-performance-20261003/reconstruction-audit.json), [source fingerprint](../results/halliday-performance-20261003/extraction.json), and [GPU work counters](../results/halliday-performance-20261003/gpu-work.json) preserve the evidence. Results are local and Git-ignored; analysis code and this report are separate from the tournament bot.

```sh
OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py extract
OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py prepare
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py compute --devices 0,1,2,3
.venv-estimators/bin/python -B analysis/halliday_report.py
.venv-estimators/bin/python -B analysis/render_halliday_report.py
.venv-estimators/bin/python -B -m unittest discover -s tests -p test_halliday_performance.py -v
```

Re-extraction audits whatever is in the input snapshot at that time and can change the counts. Preserve this result directory, or choose a fresh `--directory`, when comparing later snapshots. The human case-study prose refers to this fingerprinted snapshot and should be reviewed if the inputs change.
