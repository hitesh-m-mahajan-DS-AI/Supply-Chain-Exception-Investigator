"""Local CPU inference and mechanical quote checks; no claim of semantic verification."""
from pathlib import Path
import hashlib
import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
from pydantic import ValidationError
from .contracts import Draft

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:11434"
MODELS = ["qwen2.5:1.5b", "qwen2.5:0.5b"]
OPTIONS = {"temperature": 0, "seed": 42, "num_predict": 260, "num_ctx": 4096, "num_thread": 4, "num_gpu": 0}


def normalized(text):
    return " ".join(text.split())


def status():
    try:
        with urlopen(BASE + "/api/tags", timeout=2) as response:
            tags = json.load(response).get("models", [])
        with urlopen(BASE + "/api/version", timeout=2) as response:
            version = json.load(response).get("version")
        models = [{"name": row["name"], "digest": row.get("digest"), "bytes": row.get("size")} for row in tags if row["name"] in MODELS]
        return {"available": True, "version": version, "models": models, "notice": "Local CPU model; no downloads are performed by this app."}
    except (URLError, TimeoutError, ValueError, OSError):
        return {"available": False, "version": None, "models": [], "notice": "Ollama is unavailable. Case browsing and evidence search still work."}


def validate_quotes(raw, passages):
    errors = []
    try:
        draft = Draft.model_validate_json(raw)
    except (ValidationError, ValueError):
        return None, ["The model output did not satisfy the evidence schema."]
    lookup = {p["id"]: p for p in passages}
    seen = set()
    for evidence in draft.evidence:
        if evidence.passage_id not in lookup:
            errors.append("A citation is outside the retrieved case context.")
        elif normalized(evidence.quote) not in normalized(lookup[evidence.passage_id]["text"]):
            errors.append("A quoted excerpt does not occur verbatim in its cited passage.")
        if evidence.passage_id in seen:
            errors.append("Duplicate citations are not accepted.")
        seen.add(evidence.passage_id)
    return (draft.model_dump() if not errors else None), errors


def generate(question, passages, model_name, prompt_version):
    prompt = (ROOT / f"data/prompts/{prompt_version}.txt").read_text(encoding="utf-8")
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    local = status()
    selected = next((m for m in local["models"] if m["name"] == model_name), None)
    context = [{"passage_id": p["id"], "kind": p["kind"], "text": p["text"]} for p in passages]
    result = {"state": "unavailable", "attempted": False, "completed": False, "draft": None,
              "raw": None, "errors": [], "seconds": None, "model": model_name,
              "model_digest": selected["digest"] if selected else None, "ollama_version": local["version"],
              "prompt_version": prompt_version, "prompt_sha256": prompt_sha, "options": OPTIONS,
              "input_context": context, "schema_sha256": hashlib.sha256(json.dumps(Draft.model_json_schema(),sort_keys=True).encode()).hexdigest()}
    if not selected:
        result["errors"] = ["The requested local model is not available. Search results are still shown."]
        return result
    payload = {"model": model_name, "messages": [{"role": "system", "content": prompt},
               {"role": "user", "content": json.dumps({"question": question, "passages": context}, ensure_ascii=False)}],
               "format": Draft.model_json_schema(), "stream": False, "options": OPTIONS, "keep_alive": "5m"}
    started = time.perf_counter()
    result["attempted"] = True
    try:
        request = Request(BASE + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
        with urlopen(request, timeout=40) as response:
            answer = json.load(response)
        result["completed"] = True
        result["raw"] = answer["message"]["content"]
        result["done_reason"] = answer.get("done_reason")
        result["token_counts"] = {"prompt": answer.get("prompt_eval_count"), "generated": answer.get("eval_count")}
        draft, errors = validate_quotes(result["raw"], passages)
        result.update({"state": "checked" if draft else "withheld", "draft": draft, "errors": errors})
    except (URLError, TimeoutError, ValueError, KeyError, OSError):
        result["errors"] = ["Local generation did not complete successfully. Use the retrieved evidence directly or retry."]
    result["seconds"] = round(time.perf_counter() - started, 6)
    return result
