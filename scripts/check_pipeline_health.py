#!/usr/bin/env python3
"""
scripts/check_pipeline_health.py

Usage:
    python scripts/check_pipeline_health.py --claim-id <CLAIM_ID>
    python scripts/check_pipeline_health.py --text-file <path_to_text_file>
"""

import argparse
import json
import sys
from typing import Optional

# Import your project modules (adjust relative import if needed)
try:
    from scripts.ai_validator import AIValidator
    from scripts.universal_medical_validator import UniversalMedicalValidator
    from scripts.universal_fraud_detector import UniversalFraudDetector
    from scripts.disease_knowledge_base import DiseaseKnowledgeBase
    from scripts.report_generator import MedicalClaimReportGenerator
    from scripts.db_handler import DatabaseHandler
except Exception as e:
    # Try top-level imports if running from project root
    try:
        from ai_validator import AIValidator
        from universal_medical_validator import UniversalMedicalValidator
        from universal_fraud_detector import UniversalFraudDetector
        from disease_knowledge_base import DiseaseKnowledgeBase
        from report_generator import MedicalClaimReportGenerator
        from db_handler import DatabaseHandler
    except Exception as e2:
        print("ERROR importing project modules:", e)
        print("Try running this from the project root or adjust PYTHONPATH.")
        raise

def load_claim_by_id(claim_id: str, db: DatabaseHandler) -> Optional[dict]:
    claim = db.get_claim_by_id(claim_id)
    if not claim:
        print(f"⚠️  Claim with id '{claim_id}' not found in DB.")
    return claim

def load_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"❌ Failed to read text file {path}: {e}")
        return ""

def pretty_flag(ok: bool) -> str:
    return "✅" if ok else "❌"

def warn_flag(cond: bool) -> str:
    return "✅" if cond else "⚠️"

def summarize_and_print_diagnostics(claim: dict,
                                    extracted: dict,
                                    disease_info: Optional[dict],
                                    med_result: dict,
                                    fraud_result: dict):
    claim_id = claim.get("claim_id", "<unknown>")
    print("\n" + "="*40)
    print(f"CLAIM PIPELINE DIAGNOSTIC — {claim_id}")
    print("="*40)

    # 1) Extraction health
    essential = ["diagnosis", "hospital_name", "admission_date", "discharge_date", "total_claim_amount"]
    missing = [f for f in essential if not extracted.get(f) and extracted.get(f) != 0]
    print("\n[1] PDF / Text Extraction")
    if extracted:
        print(f"  Fields extracted: {len(extracted.keys())}")
    if missing:
        print(f"  {warn_flag(False)} Missing essential fields: {', '.join(missing)}")
    else:
        print(f"  {pretty_flag(True)} All essential fields present")

    # show key extracted values
    print("  Key extracted values:")
    for k in ["diagnosis","hospital_name","admission_date","discharge_date","treatment_duration","total_claim_amount"]:
        print(f"    - {k}: {extracted.get(k)}")

    # 2) Disease mapping
    print("\n[2] Disease Mapping (Knowledge Base)")
    if disease_info:
        print(f"  {pretty_flag(True)} Mapped to disease key: {disease_info.get('name')} (category: {disease_info.get('category')})")
    else:
        print(f"  {warn_flag(False)} Diagnosis unresolved by knowledge base: '{extracted.get('diagnosis')}'")
        print("    → Suggestion: check DiseaseKnowledgeBase.aliases/_normalize_diagnosis()/auto-alias generator")

    # 3) Medical validation
    print("\n[3] Medical Validation")
    if med_result:
        appr = med_result.get("appropriateness_score", med_result.get("score", None))
        print(f"  Appropriateness score: {appr}")
        rec = med_result.get("recommendation") or med_result.get("is_valid")
        print(f"  Recommendation (validator): {rec}")
        warnings = med_result.get("medical_warnings", []) or med_result.get("warnings", [])
        errors = med_result.get("medical_errors", []) or med_result.get("errors", [])
        fraud_inds = med_result.get("fraud_indicators", [])
        print(f"  Warnings: {len(warnings)}; Errors: {len(errors)}; Fraud indicators: {len(fraud_inds)}")
        if warnings:
            print("   - Warnings (sample):")
            for w in warnings[:5]:
                print(f"     • {w}")
        if errors:
            print("   - Errors (sample):")
            for e in errors[:5]:
                print(f"     • {e}")
    else:
        print("  ❌ No medical validation result produced (check validator invocation).")

    # 4) Financial checks
    print("\n[4] Financial Checks")
    total_claimed = extracted.get("total_claim_amount") or extracted.get("total_claimed") or 0
    print(f"  Total claimed read: Rs.{total_claimed:,}")
    cost_analysis = med_result.get("cost_analysis", {})
    within = cost_analysis.get("within_guidelines", None)
    if within is False:
        print("  ❌ Cost analysis indicates claim exceeds guidelines")
    elif within is True:
        print("  ✅ Claim within guidelines per disease rules")
    else:
        print("  ⚠️ Cost guidance not available in medical validation output")

    # 5) Fraud detection
    print("\n[5] Fraud Detection")
    if fraud_result:
        overall_risk = fraud_result.get("overall_risk_score", fraud_result.get("fraud_probability", None))
        risk_level = fraud_result.get("risk_level", "UNKNOWN")
        print(f"  Fraud risk score: {overall_risk}   Risk level: {risk_level}")
        patterns = []
        # gather detected patterns from a few possible locations
        for key in ["detected_patterns", "medical_fraud_analysis", "insurance_fraud_analysis", "fraud_patterns"]:
            if isinstance(fraud_result.get(key), list):
                patterns.extend(fraud_result.get(key, []))
            elif isinstance(fraud_result.get(key), dict):
                # normalized nested patterns
                nested = fraud_result.get(key, {})
                if nested.get("medical_fraud_patterns"):
                    patterns.extend(nested.get("medical_fraud_patterns", []))
                if nested.get("insurance_fraud_patterns"):
                    patterns.extend(nested.get("insurance_fraud_patterns", []))
        print(f"  Detected fraud patterns: {len(patterns)}")
        if patterns:
            print("   - Patterns (sample):")
            for p in patterns[:5]:
                # pattern may be dict or string
                if isinstance(p, dict):
                    print(f"     • {p.get('pattern','?')} ({p.get('severity','?')}) - {p.get('description','')}")
                else:
                    print(f"     • {p}")
    else:
        print("  ❌ No fraud analysis produced")

    # 6) Decision consistency
    print("\n[6] Decision Consistency Checks")
    validator_reco = med_result.get("recommendation") if med_result else None
    fraud_reco = fraud_result.get("recommendation") if fraud_result else None
    final_status = ( (claim.get("status") or claim.get("final_status")) or
                     ( (fraud_result.get("recommendation") if fraud_result else None) ) ) or "UNKNOWN"
    print(f"  Validator recommendation: {validator_reco}")
    print(f"  Fraud engine recommendation: {fraud_reco}")
    print(f"  Claim record final status: {claim.get('status', claim.get('final_status', 'UNKNOWN'))}")

    if validator_reco and fraud_reco:
        if str(validator_reco).upper().startswith("APPROV") and str(fraud_reco).upper().startswith("APPROV"):
            print("  ✅ Validator & Fraud agree on APPROVE")
        elif str(validator_reco).upper().startswith("REJ") or str(fraud_reco).upper().startswith("REJ"):
            print("  ❌ One or both modules recommend REJECT — investigate errors")
        else:
            print("  ⚠️ Modules disagree or suggest REVIEW — manual review suggested")
    else:
        print("  ⚠️ Could not determine consistency (missing module outputs)")

    # 7) Data integrity
    print("\n[7] Final Output Integrity")
    critical_report_fields = ["diagnosis", "disease_identified", "treatment_duration", "total_claim_amount", "approved_amount"]
    missing_report_fields = [f for f in critical_report_fields if not (claim.get(f) or extracted.get(f) or med_result.get(f) or (claim.get('comprehensive_report', {}) and claim['comprehensive_report'].get(f)))]
    if missing_report_fields:
        print(f"  ⚠️ Missing critical final fields: {missing_report_fields}")
    else:
        print("  ✅ All critical report fields present")

    # Summarize
    print("\nSUMMARY / SUGGESTED ACTIONS:")
    if missing:
        print(" - Fix extraction: ensure key fields present (diagnosis, dates, amount).")
    if not disease_info:
        print(" - Ensure DiseaseKnowledgeBase aliases and normalization are active.")
    if med_result and med_result.get("appropriateness_score", 0) < 0.7:
        print(" - Medical appropriateness score low: review medical warnings/errors.")
    if fraud_result and fraud_result.get("overall_risk_score", 0) >= 0.45:
        print(" - Fraud risk medium/high: escalate for manual review or audit.")
    if not missing and disease_info and med_result and fraud_result and (med_result.get("recommendation") and fraud_result.get("recommendation")):
        print(" - Pipeline looks healthy for this claim. Safe to generate final PDF/Payment.")
    print("\n" + "="*40 + "\n")

def run_check_for_claim_id(claim_id: str):
    db = DatabaseHandler()
    claim = load_claim_by_id(claim_id, db)
    if not claim:
        return

    # Instantiate processors
    ai = AIValidator()
    kb = DiseaseKnowledgeBase()
    med = UniversalMedicalValidator()
    fraud = UniversalFraudDetector()

    # If claim already has 'extracted_text' we prefer it, else try using claim fields to build text
    consolidated_text = claim.get("consolidated_text") or claim.get("extracted_text") or ""
    if not consolidated_text:
        # fallback: attempt to serialize claim fields
        consolidated_text = json.dumps(claim)

    # Step A: extraction (LLM first, fallback rules)
    try:
        extracted = ai.validate_and_extract_with_llm(consolidated_text) or {}
    except Exception as e:
        print("❌ AI extraction failed:", e)
        extracted = {}

    # Merge extracted into claim copy (not writing DB)
    merged_claim = dict(claim)
    merged_claim.update(extracted)

    # Step B: disease mapping
    disease_info = kb.get_disease_info(extracted.get("diagnosis", claim.get("diagnosis", "")) or "")

    # Step C: medical validation
    med_result = med.validate_medical_treatment(merged_claim)

    # Step D: fraud detection
    fraud_result = fraud.analyze_claim_fraud(merged_claim)

    # Print diagnostics
    summarize_and_print_diagnostics(merged_claim, extracted, disease_info, med_result, fraud_result)

def run_check_from_text_file(path: str, synthetic_claim_id: str = "TEXTFILE_CHECK"):
    # instantiate tools
    ai = AIValidator()
    kb = DiseaseKnowledgeBase()
    med = UniversalMedicalValidator()
    fraud = UniversalFraudDetector()

    text = load_text_file(path)
    if not text:
        print("No text to analyze. Exiting.")
        return

    try:
        extracted = ai.validate_and_extract_with_llm(text) or {}
    except Exception as e:
        print("❌ AI extraction failed:", e)
        extracted = {}

    # build minimal claim dict
    claim = {
        "claim_id": synthetic_claim_id,
        "consolidated_text": text,
        **extracted
    }

    disease_info = kb.get_disease_info(extracted.get("diagnosis", "") or "")
    med_result = med.validate_medical_treatment(claim)
    fraud_result = fraud.analyze_claim_fraud(claim)

    summarize_and_print_diagnostics(claim, extracted, disease_info, med_result, fraud_result)

def main():
    parser = argparse.ArgumentParser(description="Claim pipeline diagnostic checker")
    parser.add_argument("--claim-id", type=str, help="Claim ID to check (loads from DB)")
    parser.add_argument("--text-file", type=str, help="Path to text file containing consolidated extracted text")
    args = parser.parse_args()

    if not args.claim_id and not args.text_file:
        parser.print_help()
        sys.exit(1)

    if args.claim_id:
        run_check_for_claim_id(args.claim_id)
    elif args.text_file:
        run_check_from_text_file(args.text_file)

if __name__ == "__main__":
    main()
