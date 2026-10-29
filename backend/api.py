"""Single-origin local investigator API and compiled React interface."""
from pathlib import Path
from threading import Lock
from uuid import UUID
import csv
import io
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from .contracts import InvestigationRequest, ReviewRequest
from .retrieval import load_corpus, Retriever
from .service import investigate, release, report
from . import model, store

ROOT=Path(__file__).resolve().parents[1]
CORPUS,CORPUS_SHA=load_corpus()
RETRIEVER=Retriever(CORPUS)
RUN_LOCK=Lock()
app=FastAPI(title="Supply Chain Exception Investigator",version="1.0.0")


@app.get("/api/health")
def health():
    return {"status":"ok","version":"1.0.0","scope":"fictional local casework"}


@app.get("/api/catalog")
def catalog():
    return {"corpus":CORPUS,"corpus_sha256":CORPUS_SHA,"release":release(),"model_status":model.status(),
            "prompts":{key:(ROOT/f"data/prompts/{key}.txt").read_text(encoding="utf-8") for key in ["v1","v2"]}}


@app.get("/api/model-status")
def model_status():
    return model.status()


@app.post("/api/investigations",status_code=201)
def create(request:InvestigationRequest):
    if not request.question.strip():
        raise HTTPException(422,"Enter a nonblank question.")
    if request.case_id not in {c["id"] for c in CORPUS["cases"]}:
        raise HTTPException(404,"Case not found.")
    with RUN_LOCK:
        result=investigate(CORPUS,CORPUS_SHA,RETRIEVER,request)
        store.save(result)
    return {"investigation":result,"reviews":[]}


@app.get("/api/investigations")
def history():
    return store.history()


def find(run_id:UUID):
    result=store.get(str(run_id))
    if result is None:
        raise HTTPException(404,"Investigation not found.")
    return result


@app.get("/api/investigations/{run_id}")
def detail(run_id:UUID):
    result=find(run_id)
    return {"investigation":result,"reviews":store.reviews(str(run_id))}


@app.post("/api/investigations/{run_id}/reviews",status_code=201)
def add_review(run_id:UUID,request:ReviewRequest):
    find(run_id)
    if not request.note.strip():
        raise HTTPException(422,"Add a nonblank analyst note.")
    store.review(str(run_id),request)
    return store.reviews(str(run_id))


@app.get("/api/investigations/{run_id}/export/{kind}")
def export(run_id:UUID,kind:str):
    result=find(run_id)
    reviews=store.reviews(str(run_id))
    headers={"Content-Disposition":f'attachment; filename="investigation-{run_id}.{kind}"'}
    if kind=="json":
        return JSONResponse({"investigation":result,"reviews":reviews},headers=headers)
    if kind=="md":
        return Response(report(result,reviews),media_type="text/markdown",headers=headers)
    if kind=="csv":
        buffer=io.StringIO(newline="")
        writer=csv.DictWriter(buffer,fieldnames=["passage_id","title","kind","text","selected_by_model"],lineterminator="\n")
        writer.writeheader()
        selected={e["passage_id"] for e in (result["generation"].get("draft") or {}).get("evidence",[])}
        for p in result["retrieved"]:
            writer.writerow({"passage_id":p["id"],"title":p["title"],"kind":p["kind"],"text":p["text"],"selected_by_model":p["id"] in selected})
        return Response(buffer.getvalue(),media_type="text/csv",headers=headers)
    raise HTTPException(404,"Choose json, md or csv export.")


@app.get("/api/evaluation")
def evaluation():
    target=ROOT/"outputs/evaluation_summary.json"
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"ready":False}


dist=ROOT/"frontend/dist"
if dist.is_dir():
    app.mount("/",StaticFiles(directory=dist,html=True),name="frontend")
else:
    @app.get("/")
    def missing_build():
        return {"message":"Run python setup_project.py, then python launch.py."}
