# nn_meta.student — Phase F: teacher→student standalone signal NN.
#
# Stage 1 (clone): per-bar 3-class policy (flat/long/short) imitates the
# frozen baseline's position state. Go/no-go: reconstructed trades must
# reproduce the teacher's option P&L on validation within tolerance.
# Stage 2 (fine-tune): counterfactual relabeling — bars inside winning
# teacher trades keep their direction (weight ∝ realized option return),
# bars inside losing trades are relabeled FLAT (weight ∝ |loss|) — the
# student learns to hold winners and skip losers, still fully supervised.
