import pandas as pd
import pytest
from incubator.daily_v6.snapshot import append_frozen


def test_provider_correction_does_not_rewrite_frozen_history():
    index=pd.date_range('2026-09-28',periods=3,freq='D')
    old=pd.DataFrame({'Close':[10.0],'Volume':[100.0]},index=index[:1])
    fresh=pd.DataFrame({'Close':[10.0,11.0,12.0],'Volume':[99.0,200.0,300.0]},index=index)
    result,audit=append_frozen(old,fresh)
    assert result.loc[index[0],'Volume']==100
    assert result.loc[index[1]:].equals(fresh.loc[index[1]:])
    assert audit['changed_columns']=={'Volume':1}
    assert audit['appended_rows']==2


def test_no_duplicate_day_when_extending_next_session():
    index=pd.date_range('2026-09-28',periods=3,freq='D')
    first=pd.DataFrame({'Close':[10.,11.]},index=index[:2])
    fresh=pd.DataFrame({'Close':[9.,12.,13.]},index=index)
    result,_=append_frozen(first,fresh)
    assert result.Close.tolist()==[10.,11.,13.]


def test_invalid_history_rejected():
    data=pd.DataFrame({'Close':[1,2]},index=[1,1])
    with pytest.raises(ValueError):append_frozen(data,data)
