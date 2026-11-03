from server.smc_structure import analyze_smc_structure


def _gap_candles(invalidate=False):
    rows=[]
    for i in range(20):
        if i<10:
            row={"open":100.0,"high":101.0,"low":99.0,"close":100.2}
        elif i==10:
            row={"open":103.2,"high":104.5,"low":103.0,"close":104.0}
        else:
            row={"open":104.0,"high":105.0,"low":103.5,"close":104.5}
        row["time"]=1_800_000_000+i*3600
        rows.append(row)
    if invalidate:
        rows[-1]={"time":rows[-1]["time"],"open":102.0,"high":102.5,"low":100.0,"close":100.5}
    return rows


def test_fvg_zone_has_epoch_start_time_and_active_lifecycle():
    result=analyze_smc_structure(_gap_candles())
    zones=[z for z in result["zones"] if z["zone_type"]=="fvg"]
    assert zones
    assert zones[0]["status"]=="active"
    assert zones[0]["start_time"]==1_800_000_000+10*3600
    assert zones[0]["high"]>zones[0]["low"]


def test_fvg_zone_is_invalidated_by_close_through_far_boundary():
    result=analyze_smc_structure(_gap_candles(invalidate=True))
    zones=[z for z in result["zones"] if z["zone_type"]=="fvg"]
    assert zones
    assert zones[0]["status"]=="invalidated"


def test_timestamp_can_be_iso8601():
    rows=_gap_candles()
    rows[10]["time"]="2027-01-15T10:00:00Z"
    result=analyze_smc_structure(rows)
    zones=[z for z in result["zones"] if z["zone_type"]=="fvg"]
    assert zones
    assert zones[0]["start_time"]==int(__import__("datetime").datetime(2027,1,15,10,tzinfo=__import__("datetime").timezone.utc).timestamp())
