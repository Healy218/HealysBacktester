"""Ensure the SPX0 evaluation entry point records its actual mark input."""
import sys
from types import SimpleNamespace

import pandas as pd


def test_spx0_cli_hashes_the_marks_used_for_evaluation(tmp_path, monkeypatch):
    from nn_meta.spx0 import evaluate as E
    from nn_meta.feature_contract import CONTRACT_VERSION, baseline_spec_fingerprint
    dataset=tmp_path/'dataset.parquet'
    marks=tmp_path/'marks.parquet'
    marks.touch()
    spec={'symbols':{},'train_window':['2024-01-01','2024-12-31']}
    rows=pd.DataFrame({'entry_ts':pd.to_datetime(['2025-06-01'])})
    rows.attrs.update(feature_contract_version=CONTRACT_VERSION,
                      baseline_spec_sha256=baseline_spec_fingerprint(spec))
    rows.to_parquet(dataset)
    monkeypatch.setattr(E,'synthetic_spec',lambda _:spec)
    monkeypatch.setattr(E,'option_b_blockers',lambda *a,**kw:[])
    monkeypatch.setattr(E,'load_mark_stream',lambda _:pd.DataFrame())
    monkeypatch.setattr(E,'expanding_folds',lambda *a,**kw:[SimpleNamespace(val_start=pd.Timestamp('2025-01-02'))])
    monkeypatch.setattr(E,'evaluate_window',lambda *a,**kw:{})
    monkeypatch.setattr(E,'_write_report',lambda *a:None)
    captured={}
    monkeypatch.setattr(E,'create_manifest',lambda **kw:captured.update(kw) or {})
    monkeypatch.setattr(E,'write_manifest',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['spx0-evaluate','--dataset',str(dataset),'--marks',str(marks),'--output',str(tmp_path/'report.md')])
    E.main()
    assert captured['mark_stream_path']==marks
    assert captured['evaluation_config']['cost_model']=='index_dollar'
