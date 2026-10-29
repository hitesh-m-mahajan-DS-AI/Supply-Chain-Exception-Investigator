"""Mechanical correctness checks; model quality is measured separately in evaluate.py."""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
from fastapi.testclient import TestClient
from backend.contracts import InvestigationRequest
from backend.retrieval import load_corpus, Retriever
from backend.model import validate_quotes, generate
from backend.service import investigate
from backend import store
from backend.api import app


class InvestigatorChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus,cls.sha=load_corpus()
        cls.retriever=Retriever(cls.corpus)

    def test_scoped_retrieval_never_exposes_other_cases(self):
        found=self.retriever.search("EX-1042","What does the temperature logger file show for SH-1045?")
        self.assertTrue(all(p["case_id"] in (None,"EX-1042") for p in found))

    def test_known_development_fact_and_policy_are_retrieved(self):
        fact=self.retriever.search("EX-1042","What reason did the supplier report for the delay?")
        self.assertIn("EX-1042-NOTICE:p1",[p["id"] for p in fact])
        policy=self.retriever.search("EX-1043","What does the procedure require for damaged goods before release?")
        self.assertIn("SOP-DAMAGE:p1",[p["id"] for p in policy])

    def test_empty_and_fts_operator_queries_are_safe(self):
        self.assertEqual(self.retriever.search("EX-1042","the and of"),[])
        self.retriever.search("EX-1042",'" OR * NEAR() ; DROP TABLE passages; --')
        self.assertTrue(self.retriever.search("EX-1042","vehicle breakdown"))

    def test_valid_verbatim_selection(self):
        passages=[{"id":"P01","text":"The supplier reported a vehicle breakdown."}]
        raw=json.dumps({"status":"supported","evidence":[{"passage_id":"P01","quote":"The supplier reported a vehicle breakdown."}]})
        draft,errors=validate_quotes(raw,passages)
        self.assertEqual(errors,[])
        self.assertEqual(draft["status"],"supported")

    def test_invented_quote_and_unknown_citation_are_withheld(self):
        passages=[{"id":"P01","text":"The supplier reported a vehicle breakdown."}]
        for evidence in [{"passage_id":"P01","quote":"The supplier confirmed arrival at 19:00."},
                         {"passage_id":"ANOTHER-CASE","quote":"The supplier reported a vehicle breakdown."}]:
            draft,errors=validate_quotes(json.dumps({"status":"supported","evidence":[evidence]}),passages)
            self.assertIsNone(draft)
            self.assertTrue(errors)

    def test_invalid_schema_duplicate_and_false_conflict_rejected(self):
        evidence={"passage_id":"P01","quote":"The supplier reported a vehicle breakdown."}
        passages=[{"id":"P01","text":evidence["quote"]}]
        for raw in ["not json",json.dumps({"status":"conflict","evidence":[evidence]}),
                    json.dumps({"status":"supported","evidence":[evidence,evidence]}),
                    json.dumps({"status":"insufficient","evidence":[evidence]}),
                    json.dumps({"status":"supported","evidence":[evidence],"extra":"invented"})]:
            self.assertIsNone(validate_quotes(raw,passages)[0])

    def test_empty_evidence_refusal_remains_an_explicit_model_stance(self):
        draft,errors=validate_quotes('{"status":"insufficient","evidence":[]}',[])
        self.assertEqual(errors,[])
        self.assertEqual(draft["status"],"insufficient")

    def test_unavailable_model_is_not_a_generated_answer(self):
        with patch("backend.model.status",return_value={"models":[],"version":None}):
            result=generate("What happened?",[],"qwen2.5:1.5b","v2")
        self.assertEqual(result["state"],"unavailable")
        self.assertFalse(result["attempted"])
        self.assertIsNone(result["draft"])

    def test_search_only_never_calls_model_or_reads_evaluation_labels(self):
        request=InvestigationRequest(case_id="EX-1042",question="What reason was reported for the delay?",mode="search_only")
        with patch("backend.model.generate",side_effect=AssertionError("Unexpected model call")):
            result=investigate(self.corpus,self.sha,self.retriever,request)
        self.assertEqual(result["generation"]["state"],"not_requested")
        self.assertNotIn("expected_status",json.dumps(result))
        self.assertNotIn("expected_passage_ids",json.dumps(result))
        self.assertTrue(result["retrieved"])

    def test_model_receives_only_question_and_scoped_passages(self):
        passage={"id":"P01","kind":"supplier_notice","text":"The supplier reported a vehicle breakdown."}
        reply={"message":{"content":json.dumps({"status":"supported","evidence":[{"passage_id":"P01","quote":passage['text']} ]})},"done_reason":"stop"}
        captured=[]
        def mocked_urlopen(request,timeout):
            captured.append(json.loads(request.data))
            return BytesIO(json.dumps(reply).encode())
        with patch("backend.model.status",return_value={"version":"test","models":[{"name":"qwen2.5:1.5b","digest":"test-digest"}]}),patch("backend.model.urlopen",side_effect=mocked_urlopen):
            result=generate("What delay reason was reported?",[passage],"qwen2.5:1.5b","v2")
        self.assertEqual(result["state"],"checked")
        context=json.loads(captured[0]["messages"][1]["content"])
        self.assertEqual(set(context),{"question","passages"})
        self.assertEqual(context["passages"][0]["passage_id"],"P01")
        self.assertEqual(captured[0]["options"]["num_gpu"],0)

    def test_api_persistence_review_history_and_exports(self):
        with TemporaryDirectory() as folder,patch.object(store,"ROOT",Path(folder)),TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code,200)
            request={"case_id":"EX-1042","question":"What delay reason was reported?","mode":"search_only"}
            for invalid in [{**request,"extra":1},{**request,"case_id":"bad"},{**request,"question":"     "},{**request,"model":"cloud-model"}]:
                self.assertEqual(client.post("/api/investigations",json=invalid).status_code,422)
            created=client.post("/api/investigations",json=request)
            self.assertEqual(created.status_code,201)
            run=created.json()["investigation"]
            self.assertEqual(client.get(f"/api/investigations/{run['id']}").json()["investigation"],run)
            self.assertEqual(len(client.get("/api/investigations").json()),1)
            for disposition in ["needs_follow_up","reviewed"]:
                review=client.post(f"/api/investigations/{run['id']}/reviews",json={"disposition":disposition,"note":"Analyst reviewed the fictional evidence."})
                self.assertEqual(review.status_code,201)
            self.assertEqual(len(review.json()),2)
            self.assertEqual(client.get(f"/api/investigations/{run['id']}/export/json").json()["investigation"],run)
            self.assertIn("Analyst reviewed",client.get(f"/api/investigations/{run['id']}/export/md").text)
            self.assertIn("selected_by_model",client.get(f"/api/investigations/{run['id']}/export/csv").text)
            self.assertEqual(client.get("/api/investigations/00000000-0000-0000-0000-000000000000").status_code,404)
            self.assertEqual(client.get("/api/investigations/not-a-uuid").status_code,422)


if __name__=="__main__":
    unittest.main(verbosity=2)
