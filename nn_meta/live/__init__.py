# nn_meta.live — live signal scanner (alert-only).
#
# Design (see memory nn-meta-live-trading-plan): every 15m during RTH, pull
# live underlying bars, re-fire the frozen proposal strategy on the last CLOSED
# bar, (optionally) score with the NN ensemble, and push an alert naming the
# suggested contract. The human places the order. New files only — this package
# imports the backtest modules read-only and never edits them.
