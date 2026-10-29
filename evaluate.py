"""Separate dev selection from a frozen held-out case evaluation; actual CPU calls."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import statistics
from backend.contracts import InvestigationRequest
from backend.retrieval import load_corpus, Retriever
from backend.service import investigate, ENGINE_SHA
from backend.model import status, normalized

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"outputs"
CONFIGS=[{"model":m,"prompt_version":p} for m in ["qwen2.5:0.5b","qwen2.5:1.5b"] for p in ["v1","v2"]]


def write(name,value):
    OUT.mkdir(exist_ok=True)
    target=OUT/name
    temporary=target.with_suffix(target.suffix+".tmp")
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(target)


def score(question,run):
    retrieved={p["id"] for p in run["retrieved"]}
    expected=set(question["expected_passage_ids"])
    draft=run["generation"].get("draft")
    selected={p["passage_id"] for p in draft["evidence"]} if draft else set()
    quotes=normalized(" ".join(p["quote"] for p in draft["evidence"])).lower() if draft else ""
    field_ok=bool(draft) and all(normalized(p).lower() in quotes for p in question["expected_phrases"])
    stance_ok=bool(draft) and draft["status"]==question["expected_status"]
    task_ok=bool(stance_ok and selected==expected and field_ok)
    return {"id":question["id"],"case_id":question["case_id"],"question":question["question"],
            "field":question["field"],"expected_status":question["expected_status"],
            "retrieval_all_hit":expected.issubset(retrieved) if expected else None,
            "task_pass":task_ok,"field_pass":field_ok if expected else None,
            "refusal_pass":stance_ok if not expected else None,
            "displayed_answer_on_unanswerable":bool(not expected and draft and draft["status"]!="insufficient"),
            "state":run["generation"]["state"],"predicted_status":draft["status"] if draft else None,
            "model_completed":run["generation"]["completed"],"seconds":run["seconds"],
            "expected_passage_ids":sorted(expected),"selected_passage_ids":sorted(selected)}


def summarize(records):
    answerable=[r for r in records if r["retrieval_all_hit"] is not None]
    unknown=[r for r in records if r["refusal_pass"] is not None]
    passed=sum(r["task_pass"] for r in records)
    return {"questions":len(records),"task_pass":passed,"task_pass_pct":100*passed/len(records) if records else None,
            "answerable":len(answerable),"retrieval_all_hit":sum(r["retrieval_all_hit"] for r in answerable),
            "field_pass":sum(r["field_pass"] for r in answerable),
            "unanswerable":len(unknown),"refusal_pass":sum(r["refusal_pass"] for r in unknown),
            "displayed_answer_on_unanswerable":sum(r["displayed_answer_on_unanswerable"] for r in records),
            "checked":sum(r["state"]=="checked" for r in records),"withheld":sum(r["state"]=="withheld" for r in records),
            "unavailable":sum(r["state"]=="unavailable" for r in records),
            "completed_calls":sum(r["model_completed"] for r in records),
            "mean_seconds":statistics.mean(r["seconds"] for r in records) if records else None,
            "median_seconds":statistics.median(r["seconds"] for r in records) if records else None}


def run_questions(corpus,sha,retriever,questions,config):
    rows=[]
    for q in questions:
        request=InvestigationRequest(case_id=q["case_id"],question=q["question"],mode="local_ai",**config)
        run=investigate(corpus,sha,retriever,request)
        scored=score(q,run)
        rows.append({"score":scored,"investigation":run})
        print(f"{q['id']} {config['model']} {config['prompt_version']}: {scored['state']}, task={scored['task_pass']}, {run['seconds']:.3f}s",flush=True)
    return rows


def development(corpus,sha,retriever,questions):
    results,groups=[],[]
    for config in CONFIGS:
        rows=run_questions(corpus,sha,retriever,[q for q in questions if q["split"]=="development"],config)
        results.extend(rows)
        groups.append({**config,**summarize([r["score"] for r in rows])})
    # Predeclared selection: exact task checks, field checks, output checks; ties prefer 1.5B/v2.
    winner=max(groups,key=lambda r:(r["task_pass"],r["field_pass"],r["checked"],r["model"]=="qwen2.5:1.5b",r["prompt_version"]=="v2"))
    prompt=(ROOT/f"data/prompts/{winner['prompt_version']}.txt").read_text(encoding="utf-8")
    release={"model":winner["model"],"prompt_version":winner["prompt_version"],"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
             "selection":"Highest exact development task checks, then field and output checks; ties prefer 1.5B and v2.",
             "development_questions":6,"engine_sha256":ENGINE_SHA,"corpus_sha256":sha,
             "frozen_at":datetime.now(timezone.utc).isoformat(),
             "evaluation_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT/"data/release.json").write_text(json.dumps(release,indent=2)+"\n",encoding="utf-8")
    write("development_results.json",results)
    write("development_summary.json",groups)
    write("evaluation_protocol.json",{**release,"top_k":4,"minimum_tfidf":.06,"split":"2 dev cases / 6 held-out cases; fixed authored corpus", "task_check":"Exact stance + exact gold passage set + required value fragments. A strict fixture check, not a general semantic correctness metric."})
    print("FROZEN",json.dumps(release),flush=True)


def heldout(corpus,sha,retriever,questions):
    release=json.loads((ROOT/"data/release.json").read_text(encoding="utf-8"))
    if release["engine_sha256"]!=ENGINE_SHA or release["corpus_sha256"]!=sha or release["evaluation_script_sha256"]!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise SystemExit("Pipeline/corpus/evaluation code changed after selection. Rerun development and label any reused held-out questions honestly.")
    prompt=(ROOT/f"data/prompts/{release['prompt_version']}.txt").read_text(encoding="utf-8")
    if hashlib.sha256(prompt.encode()).hexdigest()!=release["prompt_sha256"]:
        raise SystemExit("Selected prompt changed after freeze.")
    config={k:release[k] for k in ["model","prompt_version"]}
    rows=run_questions(corpus,sha,retriever,[q for q in questions if q["split"]=="heldout"],config)
    summary={"ready":True,"evaluated_at":datetime.now(timezone.utc).isoformat(),"release":release,
             "development":json.loads((OUT/"development_summary.json").read_text(encoding="utf-8")),
             "heldout":summarize([r["score"] for r in rows]),"questions":[r["score"] for r in rows],
             "limitations":"Small authored fictional corpus. Held-out questions are on six separate cases within the indexed corpus. Exact source/value checks can reject other reasonable excerpts; quote validation does not establish relevance or truth. Not a real operational accuracy benchmark."}
    write("heldout_results.json",rows)
    write("evaluation_summary.json",summary)
    render(summary)
    print("HELDOUT SUMMARY",json.dumps(summary["heldout"]),flush=True)


def render(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    development=summary["development"]
    fig,axes=plt.subplots(1,2,figsize=(14,4.6),layout="constrained")
    names=[r["model"].replace('qwen2.5:','')+' / '+r["prompt_version"] for r in development]
    axes[0].bar(names,[r["task_pass"] for r in development],color="#6465ad")
    axes[0].set(title="Development: exact fixture task checks",ylabel="Passed questions / 6",ylim=(0,6.5))
    h=summary["heldout"]
    values=[h["retrieval_all_hit"],h["field_pass"],h["refusal_pass"],h["task_pass"]]
    denominators=[h["answerable"],h["answerable"],h["unanswerable"],h["questions"]]
    axes[1].bar(["Required sources\nin top 4","Accepted value\nfragments","Correct model\nabstentions","Exact task\nchecks"],[100*v/d for v,d in zip(values,denominators)],color=["#6978a2","#6465ad","#b48750","#39477f"])
    axes[1].set(title="Held-out questions: distinct checks",ylabel="Percentage of the stated denominator",ylim=(0,115))
    for i,(v,d) in enumerate(zip(values,denominators)):
        axes[1].text(i,100*v/d+2,f"{v}/{d}",ha="center",fontsize=10)
    fig.suptitle("F2 Exception Investigator · Actual local CPU calls on fictional fixtures",fontsize=13)
    fig.savefig(OUT/"evaluation.png",dpi=150)
    plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["development","heldout"],required=True)
    args=parser.parse_args()
    corpus,sha=load_corpus()
    retriever=Retriever(corpus)
    questions=json.loads((ROOT/"data/evaluation_questions.json").read_text(encoding="utf-8"))
    available={m["name"] for m in status()["models"]}
    if args.stage=="development" and not {c["model"] for c in CONFIGS}.issubset(available):
        raise SystemExit("Both named local models are required for this optional comparison; the app still supports search-only mode.")
    if args.stage=="development":development(corpus,sha,retriever,questions)
    else:heldout(corpus,sha,retriever,questions)
