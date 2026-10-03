// Seven-card Hold'em ranking: category and five descending base-16 kickers.
__device__ int straight_high(unsigned mask) {
    for (int high = 14; high >= 6; --high) {
        unsigned run = 31u << (high - 4);
        if ((mask & run) == run) return high;
    }
    return (mask & 0x403cu) == 0x403cu ? 5 : 0;
}

extern "C" __global__ void rank_hands(const int *hands, int *out, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    int ranks[15] = {}, suits[4] = {};
    unsigned masks[4] = {}, mask = 0, flush = 0;
    for (int j = 0; j < 7; ++j) {
        int card = hands[i * 7 + j], rank = card % 13 + 2, suit = card / 13;
        ++ranks[rank]; ++suits[suit];
        masks[suit] |= 1u << rank;
        mask |= 1u << rank;
    }
    for (int s = 0; s < 4; ++s) if (suits[s] >= 5) flush = masks[s];
    if (flush) {
        int high = straight_high(flush);
        if (high) { out[i] = (8 << 20) | (high << 16); return; }
    }
    int quad = 0, trip = 0, pair = 0;
    for (int r = 14; r >= 2; --r) {
        if (ranks[r] == 4 && !quad) quad = r;
        if (ranks[r] >= 3 && !trip) trip = r;
    }
    for (int r = 14; r >= 2; --r) {
        if (ranks[r] >= 2 && r != trip) { pair = r; break; }
    }
    if (quad) {
        for (int r = 14; r >= 2; --r) if (ranks[r] && r != quad) {
            out[i] = (7 << 20) | (quad << 16) | (r << 12); return;
        }
    }
    if (trip && pair) { out[i] = (6 << 20) | (trip << 16) | (pair << 12); return; }
    if (flush) {
        int value = 5 << 20, shift = 16;
        for (int r = 14; r >= 2 && shift >= 0; --r) if (flush & (1u << r)) {
            value |= r << shift; shift -= 4;
        }
        out[i] = value; return;
    }
    int high = straight_high(mask);
    if (high) { out[i] = (4 << 20) | (high << 16); return; }
    if (trip) {
        int value = (3 << 20) | (trip << 16), shift = 12;
        for (int r = 14; r >= 2 && shift >= 8; --r) if (ranks[r] && r != trip) {
            value |= r << shift; shift -= 4;
        }
        out[i] = value; return;
    }
    int second = 0;
    if (pair) for (int r = pair - 1; r >= 2; --r) {
        if (ranks[r] >= 2) { second = r; break; }
    }
    if (second) {
        for (int r = 14; r >= 2; --r) if (ranks[r] && r != pair && r != second) {
            out[i] = (2 << 20) | (pair << 16) | (second << 12) | (r << 8); return;
        }
    }
    int value = pair ? ((1 << 20) | (pair << 16)) : 0;
    int shift = pair ? 12 : 16, minimum = pair ? 4 : 0;
    for (int r = 14; r >= 2 && shift >= minimum; --r) if (ranks[r] && r != pair) {
        value |= r << shift; shift -= 4;
    }
    out[i] = value;
}
