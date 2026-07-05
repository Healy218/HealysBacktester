# tests/test_ranking_dropdown.py
"""Top-5 rank-metric dropdown (Layer 2): within-group sort, store_idx mapping,
and the re-sort-safety of the graph/KPI callbacks."""
import main


def _rows():
    return [
        {"symbol": "SPY", "sharpe_ratio": 1.2, "total_return_pct": 10,
         "win_rate_pct": 55, "max_drawdown_pct": 8, "total_trades": 30,
         "param_label": "a", "ranked_by": "Best Sharpe"},
        {"symbol": "SPY", "sharpe_ratio": 0.5, "total_return_pct": 40,
         "win_rate_pct": 45, "max_drawdown_pct": 20, "total_trades": 12,
         "param_label": "b", "ranked_by": "Best Return"},
        {"symbol": "SPY", "sharpe_ratio": 2.0, "total_return_pct": 5,
         "win_rate_pct": 70, "max_drawdown_pct": 30, "total_trades": 60,
         "param_label": "c", "ranked_by": "Best Win Rate"},
    ]


class TestRankRows:
    def test_top_row_per_metric(self):
        r = _rows()
        assert main._rank_rows(r, "sharpe_ratio")[0]["param_label"] == "c"
        assert main._rank_rows(r, "total_return_pct")[0]["param_label"] == "b"
        assert main._rank_rows(r, "win_rate_pct")[0]["param_label"] == "c"
        assert main._rank_rows(r, "max_drawdown_pct")[0]["param_label"] == "a"  # lowest
        assert main._rank_rows(r, "total_trades")[0]["param_label"] == "c"

    def test_symbol_groups_stay_contiguous(self):
        rows = _rows() + [{"symbol": "QQQ", "sharpe_ratio": 9, "total_return_pct": 1,
                           "win_rate_pct": 1, "max_drawdown_pct": 1, "total_trades": 1,
                           "param_label": "q", "ranked_by": "x"}]
        out = main._rank_rows(rows, "total_return_pct")
        syms = [r["symbol"] for r in out]
        assert syms == ["SPY", "SPY", "SPY", "QQQ"]        # SPY block then QQQ

    def test_missing_metric_sorts_last(self):
        rows = [{"symbol": "SPY", "sharpe_ratio": 1.0, "win_rate_pct": None,
                 "total_return_pct": 5, "max_drawdown_pct": 5, "total_trades": 5,
                 "param_label": "has_none", "ranked_by": "x"},
                {"symbol": "SPY", "sharpe_ratio": 0.1, "win_rate_pct": 60,
                 "total_return_pct": 1, "max_drawdown_pct": 5, "total_trades": 5,
                 "param_label": "has_wr", "ranked_by": "y"}]
        assert main._rank_rows(rows, "win_rate_pct")[-1]["param_label"] == "has_none"

    def test_unknown_metric_falls_back_to_sharpe(self):
        assert main._rank_rows(_rows(), "bogus")[0]["param_label"] == "c"


class TestRankTableCallback:
    def test_empty_store(self):
        data, cols, sel, title = main.rank_table("sharpe_ratio", None)
        assert data == [] and sel == [0] and "Sharpe" in title

    def test_store_idx_points_at_original_position(self):
        data, cols, sel, title = main.rank_table("total_return_pct", _rows())
        # row 'b' (best return) is store index 1 and should be table row 0
        assert data[0]["store_idx"] == 1
        assert sel == [0]
        assert "Total Return" in title

    def test_title_tracks_metric(self):
        _, _, _, title = main.rank_table("win_rate_pct", _rows())
        assert "Win Rate" in title


class TestStoreIdxMapping:
    def test_kpis_read_the_selected_store_row(self):
        store = _rows()
        # table sorted by return → row 0 is store idx 1 ('b', 40% return)
        table, _, _, _ = main.rank_table("total_return_pct", store)
        out = main.update_kpis([0], store, table)
        # KPI caption embeds the selected row's param_label ('b')
        assert "b" in str(out)

    def test_no_table_data_is_safe(self):
        from dash import no_update
        assert main.update_kpis([0], _rows(), None) is no_update
