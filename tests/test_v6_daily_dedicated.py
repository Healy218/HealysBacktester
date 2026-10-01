from scripts import v6_daily_dedicated_20260930 as daily


def test_matching_prior_workers_still_obeys_available_memory(monkeypatch):
    monkeypatch.setattr(daily,'resource_plan',lambda *a,**k:dict(workers=k['available_workers'],training_threads=16))
    assert daily.selected_resources({'workers':5},6)['workers']==5
    assert daily.selected_resources({'workers':5},3)['workers']==3
    assert daily.selected_resources({'workers':5},5)['training_threads']==16

