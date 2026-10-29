"""Retrieve, draft, preserve evidence and export an auditable investigation."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from importlib.metadata import version
import hashlib
import json
import platform
import time
from . import model

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SHA = hashlib.sha256("\n".join((ROOT / "backend" / name).read_text(encoding="utf-8") for name in ["contracts.py","retrieval.py","model.py","service.py"]).encode()).hexdigest()


def release():
    path = ROOT / "data/release.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"model":"qwen2.5:1.5b","prompt_version":"v2","selection":"Initial development configuration"}


def investigate(corpus, corpus_sha, retriever, request):
    started = time.perf_counter()
    case = next(c for c in corpus["cases"] if c["id"] == request.case_id)
    passages = retriever.search(request.case_id, request.question)
    generation = model.generate(request.question, passages, request.model, request.prompt_version) if request.mode == "local_ai" else {
        "state":"not_requested","attempted":False,"completed":False,"draft":None,"raw":None,"errors":[],
        "model":None,"prompt_version":None,"seconds":None}
    scope = [d for d in corpus["documents"] if d["case_id"] in (request.case_id,None)]
    return {"id":str(uuid4()),"created_at":datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "request":request.model_dump(),"case_snapshot":case,"sources":scope,"retrieved":passages,
            "generation":generation,"corpus_sha256":corpus_sha,"engine_sha256":ENGINE_SHA,"engine_version":"1.0.0",
            "settings":{"top_k":4,"minimum_tfidf":.06,"fusion":"reciprocal rank fusion, k=60","seed":42},
            "runtime":{"python":platform.python_version(),"scikit-learn":version("scikit-learn"),"fastapi":version("fastapi")},
            "seconds":round(time.perf_counter()-started,6),
            "boundary":"Quote verification checks source identity and verbatim text, not relevance or factual truth. All records are fictional; human review remains separate."}


def report(run, reviews):
    request, generation = run["request"], run["generation"]
    lines=["# Supply Chain Exception Investigation", "", "FICTIONAL DEMONSTRATION RECORDS AND PROCEDURES", "",
           f"Case: {request['case_id']} — {run['case_snapshot']['title']}",f"Question: {request['question']}",
           f"Investigation: {run['id']}",f"Created UTC: {run['created_at']}",f"Mode: {request['mode']}",
           f"Generation state: {generation['state']}","",run["boundary"],"","## Selected local-AI evidence"]
    draft=generation.get("draft")
    if draft:
        lines.append(f"Model stance: {draft['status']} (requires analyst review).")
        for citation in draft["evidence"]:
            lines.extend(["",f"### {citation['passage_id']}",f"> {citation['quote']}"])
        if not draft["evidence"]:
            lines.append("The model selected insufficient evidence. No unsupported answer was filled in.")
    else:
        lines.append("No accepted model draft. The passages below are search results, not a generated answer.")
    lines.extend(["","## Retrieved passages"])
    for passage in run["retrieved"]:
        lines.extend(["",f"### {passage['id']} — {passage['title']}",passage["text"]])
    lines.extend(["","## Analyst review history"])
    for row in reviews:
        lines.extend(["",f"{row['created_at']} — {row['disposition']}",row["note"]])
    if not reviews:
        lines.append("Unreviewed. No analyst note recorded.")
    lines.extend(["","## Reproducibility",f"Corpus SHA-256: {run['corpus_sha256']}",f"Engine SHA-256: {run['engine_sha256']}",
                  f"Model: {generation.get('model')}",f"Model digest: {generation.get('model_digest')}",
                  f"Prompt version: {generation.get('prompt_version')}",f"Prompt SHA-256: {generation.get('prompt_sha256')}",
                  "","No message, order, release, engineering approval or shipment update was sent by this app."])
    return "\n".join(lines)+"\n"
