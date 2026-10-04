# GPU validation for the call-calibration study

The CUDA tests compare the batch ranking kernel with the independent SDK and
check fixed-sample CPU/GPU equity parity, weighted ranges, rejection sampling,
exact enumeration and cooperative deadlines. The runtime verifier also checks
48 fixed-sample cases against the frozen main engine.

GPU availability does not guarantee faster games: range construction and game
logic remain on CPU. The study times identical 120-game workloads with 12 CPU
workers and 12 CUDA workers, then projects total study time from measured per-game worker time and startup
overhead. The recorded
backend choice, model fit devices and actual audit work are included in the
[comparison evidence](../analysis/reports/evidence/call-calibration-20261004/).

Full [reproduction commands](../analysis/reports/call-calibration-20261004-reproduce.md)
include the model/runtime checks and the test suite. Timed GPU sampling can
change sample counts and actions; fixed-sample parity does not certify CPU
clock compliance. Submission code retains its normal CPU path.
