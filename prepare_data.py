"""Author reproducible fictional cases and separate development/evaluation questions."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import random

ROOT = Path(__file__).resolve().parent


def build():
    rng = random.Random(42)
    cases, documents, questions = [], [], []
    damaged_total = rng.choice([180, 240, 300])
    damaged = rng.randint(12, 24)
    dispatch = rng.choice([100, 120, 140])
    received = dispatch - 20

    def doc(doc_id, case_id, title, kind, text, minute=0):
        stamp = datetime(2026, 3, 13, 14, tzinfo=timezone.utc) + timedelta(minutes=minute)
        documents.append({"id": doc_id, "case_id": case_id, "title": title, "kind": kind,
                          "recorded_at": stamp.isoformat(), "text": text, "synthetic": True})
        return doc_id + ":p1"

    policies = [
        ("SOP-DELAY", "Delayed delivery review", "For a delayed shipment, record the reported reason and revised estimated arrival. Request a current carrier status before escalating to the planning owner. An estimate is not a delivery confirmation."),
        ("SOP-DAMAGE", "Damaged receipt handling", "For damaged cartons, keep affected goods in quarantine. Record counts, photographs and lot identifiers. A quality reviewer must authorize release or replacement; a supplier request is not authorization."),
        ("SOP-QUANTITY", "Disputed quantity reconciliation", "When dispatch and receiving quantities disagree, preserve both records and request a joint recount. Keep the final accepted quantity unresolved until the designated receiving owner signs the reconciliation."),
        ("SOP-TEMP", "Missing temperature records", "If a required temperature logger file is missing, quarantine the affected goods and request the logger file. The quality owner must review the data before release. Do not infer measured temperatures from shipping setpoints."),
        ("SOP-POD", "Unsigned proof-of-delivery review", "For an unsigned proof-of-delivery record, request a signed document and verify receipt with the destination team. Preserve the carrier status as a report. Do not mark receipt as confirmed using the portal status alone."),
        ("SOP-SUB", "Substitute material approval", "Before accepting a substitute material, obtain written engineering change approval and confirm the required specification. A supplier proposal is not approval. Keep the alternative on hold until the authorized reviewer responds."),
        ("SOP-CUSTOMS", "Fictional border-document checklist", "For missing border paperwork in this demonstration, collect the certificate of origin and supporting invoice, then ask the document owner to review completeness. Do not invent a clearance time. This fictional checklist is not customs or legal advice."),
    ]
    for key, title, text in policies:
        doc(key, None, title, "procedure", text)

    def case(case_id, title, category, severity, supplier, summary, flag, source_ids, suggestion):
        cases.append({"id": case_id, "title": title, "category": category, "severity": severity,
                      "supplier": supplier, "hub": "North hub" if case_id == "EX-1045" or len(cases) % 2 == 0 else "Central hub",
                      "summary": summary, "authored_flag": flag, "synthetic": True,
                      "suggested_question": suggestion,
                      "timeline": [{"timestamp": next(d["recorded_at"] for d in documents if d["id"] == key),
                                    "label": next(d["title"] for d in documents if d["id"] == key), "source_id": key} for key in source_ids]})

    def question(key, case_id, question_text, status, expected_ids, phrases, field):
        questions.append({"id": key, "case_id": case_id, "question": question_text, "expected_status": status,
                          "expected_passage_ids": expected_ids, "expected_phrases": phrases, "field": field,
                          "split": "development" if case_id in ("EX-1042", "EX-1043") else "heldout"})

    key = "EX-1042"
    n1 = doc(key+"-NOTICE", key, "Supplier delay notice", "supplier_notice", "For shipment SH-1042, Harbor Materials reported a vehicle breakdown. Its revised estimated arrival is 14 March 2026 at 18:00. This is an unverified supplier estimate; no delivery confirmation is attached.")
    doc(key+"-SCAN", key, "Carrier departure scan", "carrier_record", "Carrier scan for shipment SH-1042 records departure from West depot at 11:20 on 13 March 2026. The departure scan does not confirm arrival.", 20)
    doc(key+"-NOTE", key, "Planning follow-up", "internal_note", "The planning owner requested a fresh carrier status. The root cause and actual delivery time have not been independently verified.", 40)
    case(key, "Inbound delivery delayed", "Delay", "High", "Harbor Materials", "A reported breakdown moved the estimated arrival. Actual receipt is not confirmed.", "Reported reason; unverified arrival", [key+"-NOTICE",key+"-SCAN",key+"-NOTE"], "What delay reason did the supplier report?")
    question("DEV-01",key,"What reason did Harbor Materials report for the delay?","supported",[n1],["vehicle breakdown"],"reported_reason")
    question("DEV-02",key,"Which estimated arrival did the supplier give for SH-1042?","supported",[n1],["14 March 2026 at 18:00"],"reported_eta")
    question("DEV-03",key,"What actual delivery time has been independently confirmed?","insufficient",[],[],"confirmed_delivery")

    key = "EX-1043"
    n1 = doc(key+"-INSPECT",key,"Damaged carton inspection","receiving_record",f"Receiving inspection counted {damaged} damaged cartons out of {damaged_total} received cartons. The goods remain in quarantine, pending quality review.")
    doc(key+"-NOTICE",key,"Supplier evidence request","supplier_notice","The supplier requested photographs and lot identifiers before considering replacement. No replacement approval has been issued.",20)
    doc(key+"-NOTE",key,"Quality review queue","internal_note","The quality review is still pending. The disposal cost and replacement completion date are not recorded.",40)
    case(key,"Damaged packaging on receipt","Damage","Medium","Cedar Packaging","Damaged cartons were counted and held for quality review.","Quarantine; replacement not approved",[key+"-INSPECT",key+"-NOTICE",key+"-NOTE"],"How many damaged cartons were recorded?")
    question("DEV-04",key,"How many damaged cartons did the receiving inspection count?","supported",[n1],[str(damaged)+" damaged cartons"],"damaged_count")
    question("DEV-05",key,"What does the procedure require for damaged goods before release?","supported",["SOP-DAMAGE:p1"],["quarantine"],"handling_procedure")
    question("DEV-06",key,"What confirmed disposal cost was recorded for the damaged cartons?","insufficient",[],[],"disposal_cost")

    key = "EX-1044"
    n1=doc(key+"-DISPATCH",key,"Dispatch packing list","supplier_notice",f"The dispatch packing list states {dispatch} units for delivery RC-1044.")
    n2=doc(key+"-RECOUNT",key,"Signed receiving recount","receiving_record",f"The receiving recount records {received} units for delivery RC-1044. This count was signed by the receiving clerk.",0)
    doc(key+"-NOTE",key,"Open discrepancy review","internal_note","A discrepancy review is open. The records have not been reconciled and no final accepted quantity has been approved.",40)
    case(key,"Dispatch and receipt quantities disagree","Quantity","High","Harbor Materials","Two records give different counts for the same delivery.","Conflicting counts; no reconciliation",[key+"-DISPATCH",key+"-RECOUNT",key+"-NOTE"],"Do the dispatch and receiving records agree on quantity?")
    question("TEST-01",key,"Do the dispatch packing list and receiving recount agree on the number of units?","conflict",[n1,n2],[f"{dispatch} units",f"{received} units"],"quantity_conflict")
    question("TEST-02",key,"What quantity is specifically recorded by the receiving recount?","supported",[n2],[f"{received} units"],"receiving_count")
    question("TEST-03",key,"What final accepted quantity has been approved after reconciliation?","insufficient",[],[],"accepted_quantity")

    key="EX-1045"
    n1=doc(key+"-RECEIPT",key,"Missing logger attachment","receiving_record","Shipment SH-1045 arrived at North hub. The required temperature logger file was not provided with the shipment.")
    doc(key+"-QUALITY",key,"Pending quality release","internal_note","Quality release is pending. The maximum recorded temperature and exposure duration are unknown because the logger file is missing.",20)
    doc(key+"-REQUEST",key,"Logger file requested","internal_note","The document owner requested the logger file from the carrier. No logger attachment has been received in this case file.",40)
    case(key,"Temperature evidence missing","Missing records","High","Meridian Freight","The shipment arrived without its required temperature record.","Missing measurement data",[key+"-RECEIPT",key+"-QUALITY",key+"-REQUEST"],"Which measurement document is missing?")
    question("TEST-04",key,"Which required file was not provided with SH-1045?","supported",[n1],["temperature logger file"],"missing_document")
    question("TEST-05",key,"What should the missing-temperature-record procedure require before release?","supported",["SOP-TEMP:p1"],["quarantine","logger file"],"temperature_procedure")
    question("TEST-06",key,"What was the maximum measured temperature during transport?","insufficient",[],[],"maximum_temperature")

    key="EX-1046"
    n1=doc(key+"-PORTAL",key,"Carrier portal status","carrier_record","The carrier portal marks shipment SH-1046 as delivered at 12:40 on 13 March 2026. This is a portal status report.")
    doc(key+"-POD",key,"Unsigned delivery document","carrier_record","The proof-of-delivery document has no recipient signature. The destination team's receipt confirmation is not available.",20)
    doc(key+"-NOTE",key,"Destination follow-up","internal_note","The planner has asked the destination team to confirm receipt. No response has been added to the case file.",40)
    case(key,"Proof of delivery is unsigned","Delivery proof","Medium","Meridian Freight","The portal reports delivery but signed receipt evidence is absent.","Reported delivery; receipt unconfirmed",[key+"-PORTAL",key+"-POD",key+"-NOTE"],"What does the carrier portal report?")
    question("TEST-07",key,"What delivery status and time does the carrier portal report?","supported",[n1],["delivered at 12:40"],"reported_delivery")
    question("TEST-08",key,"Which procedure applies to an unsigned proof of delivery?","supported",["SOP-POD:p1"],["signed document","destination team"],"pod_procedure")
    question("TEST-09",key,"Which recipient has confirmed actual receipt of SH-1046?","insufficient",[],[],"confirmed_recipient")

    key="EX-1047"
    n1=doc(key+"-SUPPLIER",key,"Supplier arrival estimate","supplier_notice","The supplier email sent at 09:00 states an expected arrival of 16 March 2026 at 10:00 for SH-1047.")
    n2=doc(key+"-CARRIER",key,"Carrier arrival estimate","carrier_record","The carrier notice sent at 09:00 states an expected arrival of 18 March 2026 at 10:00 for SH-1047.",0)
    doc(key+"-NOTE",key,"ETA clarification requested","internal_note","Neither arrival estimate is confirmed. The planning owner requested clarification; no agreed arrival time is recorded.",40)
    case(key,"Arrival estimates conflict","Conflicting ETA","High","Harbor Materials","Supplier and carrier records disagree on the expected arrival.","Two estimates; no agreed ETA",[key+"-SUPPLIER",key+"-CARRIER",key+"-NOTE"],"Do the supplier and carrier arrival estimates agree?")
    question("TEST-10",key,"Do the supplier email and carrier notice give the same arrival estimate?","conflict",[n1,n2],["16 March 2026","18 March 2026"],"eta_conflict")
    question("TEST-11",key,"Which expected arrival does the carrier notice specifically state?","supported",[n2],["18 March 2026 at 10:00"],"carrier_eta")
    question("TEST-12",key,"What arrival time has been agreed and confirmed?","insufficient",[],[],"confirmed_eta")

    key="EX-1048"
    n1=doc(key+"-OFFER",key,"Alternative material offered","supplier_notice","The supplier proposed grade B material instead of the required grade A material. This is a proposal only; no equivalence test result is attached.")
    doc(key+"-ENGINEER",key,"Engineering change pending","internal_note","The engineering change board has not approved the substitution. The alternative material remains on hold.",20)
    doc(key+"-NOTE",key,"Test evidence unavailable","internal_note","No measured performance improvement or approved substitution certificate is recorded in this case.",40)
    case(key,"Substitute material awaits approval","Substitution","Medium","Cedar Packaging","An alternative material was proposed without engineering approval.","Proposal only; no equivalence evidence",[key+"-OFFER",key+"-ENGINEER",key+"-NOTE"],"Which substitute material was proposed?")
    question("TEST-13",key,"What material grade did the supplier propose as the alternative?","supported",[n1],["grade B material"],"proposed_grade")
    question("TEST-14",key,"What approval does the substitute-material procedure require before acceptance?","supported",["SOP-SUB:p1"],["written engineering change approval"],"substitution_procedure")
    question("TEST-15",key,"What measured performance improvement did the alternative achieve?","insufficient",[],[],"measured_improvement")

    key="EX-1049"
    n1=doc(key+"-CHECK",key,"Border paperwork check","internal_note","The commercial invoice was provided for shipment SH-1049. The certificate of origin is missing.")
    doc(key+"-HOLD",key,"Document review hold","carrier_record","The shipment is awaiting document review at the border. No clearance authorization or revised release time is recorded.",20)
    doc(key+"-REQUEST",key,"Document owner contacted","internal_note","The planner asked the document owner for the missing certificate. No reply is attached to this case file.",40)
    case(key,"Border document is missing","Missing paperwork","Medium","Meridian Freight","A required case-document attachment is absent and review is pending.","Missing certificate; no clearance time",[key+"-CHECK",key+"-HOLD",key+"-REQUEST"],"Which border-document attachment is missing?")
    question("TEST-16",key,"Which document is missing from the border paperwork check?","supported",[n1],["certificate of origin"],"missing_certificate")
    question("TEST-17",key,"What does the fictional border-document checklist say to collect?","supported",["SOP-CUSTOMS:p1"],["certificate of origin","supporting invoice"],"document_procedure")
    question("TEST-18",key,"What revised clearance release time has been authorized?","insufficient",[],[],"clearance_time")

    corpus={"version":"f2.1","seed":42,"synthetic":True,"cases":cases,"documents":documents,
            "scope":"Authored fictional demonstration records and procedures. No real company policies, shipments, legal guidance or operational outcomes."}
    folder=ROOT/"data"
    folder.mkdir(exist_ok=True)
    encoded=(json.dumps(corpus,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    (folder/"corpus.json").write_bytes(encoded)
    rng.shuffle(questions)
    (folder/"evaluation_questions.json").write_text(json.dumps(questions,indent=2)+"\n",encoding="utf-8")
    manifest={"corpus_sha256":hashlib.sha256(encoded).hexdigest(),"cases":len(cases),"documents":len(documents),
              "development_cases":["EX-1042","EX-1043"],"heldout_cases":[c["id"] for c in cases[2:]],
              "development_questions":6,"heldout_questions":18,"seed":42}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2))
    return corpus


if __name__ == "__main__":
    build()
