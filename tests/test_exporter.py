from datetime import date
import json
import threading
import pytest
from fixtures import archive,fit_bytes
from garmin_database.importer import Importer
from garmin_database.storage import Database
from garmin_database.query import Queries, bounds
from garmin_database.exporter import Exporter
from garmin_database.util import Cancelled

pytestmark=pytest.mark.integration


def setup(root,summary=False):
    db=Database(root); db.initialize()
    payload=fit_bytes(211,[(253,4,134),(0,1,2)],[(1100000000,50)]) if summary else fit_bytes()
    Importer(db).archive(archive(root,"2024-06-19",payload))
    return db


def test_streamed_export_and_replacement(tmp_path):
    db=setup(tmp_path/"data"); q=Queries(db); params=q.parameters()
    # timestamps in synthetic FIT fall on 2024-11-08
    start=date(2024,1,1); end=date(2025,1,1)
    out=tmp_path/"exports"; out.mkdir(); (out/"user.txt").write_text("keep")
    sizes=Exporter(db).generate(out,params,start,end,recent_days=400,full_samples=True)
    heart=next(p for p in params if p["key"].endswith("heart_rate"))
    contents=json.loads((out/(heart["key"]+".json")).read_text())
    assert [r[1] for r in contents["data"]]==[62,64]
    Exporter(db).generate(out,[heart],start,end,400)
    assert not (out/(heart["key"]+".json")).exists()  # sample history omitted by default
    assert (out/"user.txt").read_text()=="keep"
    assert json.loads((out/"recent.json").read_text())["series"][0]["data"]


def test_long_chart_has_no_aggregates(tmp_path):
    db=setup(tmp_path); q=Queries(db)
    p=next(p for p in q.parameters() if p["key"].endswith("heart_rate"))
    points,message=q.chart(p,date(2024,1,1),date(2025,1,1))
    assert points==[] and "podsumowań" in message


def test_summary_export(tmp_path):
    db=setup(tmp_path/"data",True); params=Queries(db).parameters()
    Exporter(db).generate(tmp_path/"out",params,date(2024,1,1),date(2025,1,1),400)
    assert all((tmp_path/"out"/(p["key"]+".json")).exists() for p in params)


def test_export_cancellation_keeps_old_file(tmp_path):
    db=setup(tmp_path/"data"); e=Exporter(db); out=tmp_path/"out"
    e.generate(out,[],date(2024,1,1),date(2025,1,1))
    original=(out/"recent.json").read_bytes()
    stop=threading.Event(); stop.set()
    with pytest.raises(Cancelled): e.generate(out,[],date(2024,1,1),date(2025,1,1),stop=stop)
    assert (out/"recent.json").read_bytes()==original


def test_foreign_export_filename_is_protected(tmp_path):
    db=setup(tmp_path/"data"); out=tmp_path/"out"; out.mkdir()
    (out/"recent.json").write_text("unrelated")
    with pytest.raises(FileExistsError): Exporter(db).generate(out,[],date(2024,1,1),date(2025,1,1))
    assert (out/"recent.json").read_text()=="unrelated"


@pytest.mark.unit
def test_dst_day_bounds():
    a,b=bounds(date(2026,3,29),date(2026,3,29))
    assert b-a==23*3600*1000
    a,b=bounds(date(2026,10,25),date(2026,10,25))
    assert b-a==25*3600*1000
