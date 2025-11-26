# scripts/report_generator.py - FINAL: Full 7-section PDF + Mistral LLM reasons
"""
Final full report generator. Produces:
 - Comprehensive JSON report (generate_comprehensive_claim_report)
 - 7-section PDF report with full content (generate_comprehensive_pdf_report)
 - Excel analytics (generate_analytics_report)

LLM integration:
 - Optional Mistral via Ollama (HTTP example)
 - Function generate_decision_reasons(rule_results) implements LLM call + fallback
"""

import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd
from fpdf import FPDF
import requests  # used for LLM HTTP call (Ollama example)
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# LLM configuration (edit to match environment)
# ------------------------------------------------------------------
class LLMConfig:
    ENABLE_LLM = True       # set to False to disable LLM calls and always use rule-based reasons
    OLLAMA_URL = "http://localhost:11434"  # example local Ollama HTTP base
    MODEL_ID = "mistral"       # change to your local model id
    TIMEOUT_SECONDS = 210      # request timeout if system is cpu will need more time if it is gpu timeout will be less
    MAX_OUTPUT_TOKENS = 700    # 512 increased to see reasoning (3 reasons it gives if context increased pdf structure can change )

# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------
def safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse JSON and return dict, else None."""
    try:
        return json.loads(text)
    except Exception:
        return None

# ------------------------------------------------------------------
# Report generator
# ------------------------------------------------------------------

class MedicalClaimReportGenerator:
    def __init__(self, db_handler):
        self.db_handler = db_handler
        self.COLORS = {
            'dark_blue': (0, 0, 128),
            'black': (0, 0, 0),
            'grey_text': (80, 80, 80),
            'grey_bg': (240, 240, 240),
            'green_bg': (220, 245, 220),
            'green_text': (0, 100, 0),
            'yellow_bg': (255, 245, 200),
            'yellow_text': (130, 100, 0),
            'red_bg': (245, 220, 220),
            'red_text': (150, 0, 0),
            'white': (255, 255, 255)
        }

    # ------------------------------
    # Text cleaning for PDF
    # ------------------------------
    def _clean_pdf_text(self, text: Any, max_len: int = 160) -> str:
        if isinstance(text, (int, float)):
            text = f"{text}"
        text = str(text or "")
        text = text.replace("\r", " ").replace("\n", " ").strip()
        text = re.sub(r"[^\x20-\x7E]", "", text) # Remove non-ASCII
        text = re.sub(r"\s{2,}", " ", text)
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text

    # ------------------------------
    # Deterministic / Rule-based helpers
    # ------------------------------
    def _get_ai_recommendation(self, claim: Dict) -> str:
        # FIX: Handle NoneType safely
        fraud_score = claim.get('fraud_score') or 0
        
        if fraud_score > 0.7:
            return "🚨 REJECT - High fraud probability"
        elif fraud_score > 0.4:
            return "⚠️ REVIEW REQUIRED - Medium risk"
        else:
            return "✅ APPROVE - Low risk"

    def _assess_data_quality(self, claim: Dict) -> str:
        missing_fields = []
        if not claim.get('diagnosis'):
            missing_fields.append('diagnosis')
        if not claim.get('hospital_name'):
            missing_fields.append('hospital_name')
        if not claim.get('admission_date'):
            missing_fields.append('admission_date')
        if not missing_fields:
            return "Good - All essential fields present"
        return f"Partial - Missing: {', '.join(missing_fields)}"

    def _assess_domain_cost_appropriateness(self, claim: Dict) -> str:
        """Domain-specific cost checks (keeps original heuristics)."""
        # FIX: Ensure numeric safety
        total_claimed = claim.get('total_claim_amount') or 0
        disease = (claim.get('diagnosis') or "").lower()
        
        cost_analysis_within_guidelines = claim.get('cost_analysis_within_guidelines', True)

        if cost_analysis_within_guidelines is False:
            return "HIGH - Costs exceed medical guidelines"
        if 'dengue' in disease and total_claimed > 80000:
            return "HIGH - Excessive for uncomplicated dengue"
        if 'fracture' in disease and total_claimed > 350000:
            return "HIGH - Excessive for fracture treatment"
        if total_claimed > 500000:
            return "MEDIUM - Very high amount, needs verification"
        if total_claimed < 10000:
            return "LOW - Potentially under-treated"
        return "APPROPRIATE - Within reasonable range"

    # ------------------------------
    # Domain data generation
    # ------------------------------
    def _generate_domain_executive_summary(self, claim: Dict) -> Dict:
        # FIX: Ensure numeric safety for calculations
        total_claimed = claim.get('total_claim_amount') or 0
        approved_amount = claim.get('approved_amount') or 0
        fraud_score = claim.get('fraud_score') or 0

        summary = {
            "patient_information": {
                "name": claim.get('patient_name', 'Unknown'),
                "policy_number": claim.get('policy_number', 'Unknown'),
                "hospital": claim.get('hospital_name', 'Unknown')
            },
            "medical_information": {
                "diagnosis": claim.get('diagnosis', 'Unknown'),
                "disease_identified": claim.get('disease_identified', 'Unknown'),
                "treatment_duration": claim.get('treatment_duration', 'Unknown'),
                "admission_date": claim.get('admission_date', 'Unknown')
            },
            "financial_overview": {
                "total_claimed": total_claimed,
                "approved_amount": approved_amount,
                "patient_responsibility": claim.get('patient_responsibility') or 0,
                "claim_utilization": f"{(approved_amount / total_claimed * 100) if total_claimed > 0 else 0:.1f}%"
            },
            "business_decision": {
                "status": claim.get('status', 'PENDING'),
                "decision_date": claim.get('updated_at', datetime.now().isoformat())
            },
            "key_risk_indicators": {
                "fraud_risk_score": fraud_score,
                "fraud_risk_level": "HIGH" if fraud_score > 0.8 else "MEDIUM" if fraud_score > 0.5 else "LOW",
                "medical_appropriateness_score": claim.get('medical_appropriateness_score') or 0,
                "policy_status": claim.get('policy_status', "VALID"),
                "coverage_breaches": claim.get('policy_limits_exceeded', [])
            }
        }
        return summary

    def _generate_business_decision_section(self, claim: Dict) -> Dict:
        reasons = {}
        try:
            reason_str = claim.get('analysis_reason', '')
            reasons = {
                "denial_reasons": [r.split("DENIED: ")[1] for r in reason_str.split(" | ") if r.startswith("DENIED:")],
                "review_reasons": [r.split("REVIEW: ")[1] for r in reason_str.split(" | ") if r.startswith("REVIEW:")],
                "approval_reasons": [r.split("APPROVED: ")[1] for r in reason_str.split(" | ") if r.startswith("APPROVED:")]
            }
        except Exception:
            pass 

        return {
            "final_decision": claim.get('status', 'PENDING'),
            "approved_amount": claim.get('approved_amount') or 0,
            "financial_impact": {
                "co_pay_amount": claim.get('co_pay_amount') or 0,
                "patient_responsibility": claim.get('patient_responsibility') or 0,
                "insurance_payment": claim.get('approved_amount') or 0
            },
            "decision_reasons": {
                "denial_reasons": reasons.get('denial_reasons', []),
                "approval_reasons": reasons.get('approval_reasons', []),
                "review_reasons": reasons.get('review_reasons', [])
            },
            "decision_timestamp": claim.get('updated_at', datetime.now().isoformat())
        }

    def _generate_domain_medical_validation(self, claim: Dict) -> Dict:
        return {
            "disease_analysis": {
                "diagnosis": claim.get('diagnosis', 'Unknown'),
                "disease_identified": claim.get('disease_identified', 'Unknown'),
                "medical_appropriateness": claim.get('is_medically_appropriate', True),
                "appropriateness_score": f"{(claim.get('medical_appropriateness_score') or 0):.1%}"
            },
            "treatment_analysis": {
                "procedures_performed": claim.get('procedures', []),
                "medications_prescribed": claim.get('medications', []),
                "room_type_used": claim.get('room_type', 'Unknown'),
                "treatment_duration": claim.get('treatment_duration', 0)
            },
            "cost_appropriateness": {
                "within_guidelines": claim.get('cost_analysis_within_guidelines', True),
                "typical_range": claim.get('cost_analysis_typical_range', 'N/A'),
                "details": claim.get('cost_analysis_details', 'N/A')
            },
            "treatment_guidelines_compliance": {
                "is_compliant": claim.get('treatment_is_compliant', True),
                "details": claim.get('treatment_compliance_details', 'N/A')
            },
            "medical_issues": {
                "critical_errors": claim.get('medical_errors', []),
                "warnings": claim.get('medical_warnings', []),
                "fraud_indicators": claim.get('fraud_indicators', [])
            }
        }

    def _generate_coverage_analysis(self, claim: Dict) -> Dict:
        policy_status = claim.get('policy_status', "VALID")
        exclusions = claim.get('policy_exclusions', [])
        limits = claim.get('policy_limits_exceeded', [])
        co_pay_percentage = claim.get('co_pay_percentage') or 0.1

        return {
            "policy_validation": {"status": policy_status, "policy_number": claim.get('policy_number', 'N/A')},
            "coverage_limits": {"exceeded_limits": limits},
            "financial_implications": {
                "co_pay_percentage": f"{co_pay_percentage * 100}%", 
                "co_pay_amount": claim.get('co_pay_amount') or 0
            },
            "coverage_violations": {
                "excluded_procedures": exclusions,
                "limit_exceeded": limits,
                "waiting_period_issues": claim.get('policy_waiting_period_issues', [])
            }
        }

    def _generate_domain_financial_analysis(self, claim: Dict) -> Dict:
        total_claimed = claim.get('total_claim_amount') or 0
        approved_amount = claim.get('approved_amount') or 0

        return {
            "claim_amount_breakdown": {
                "total_claimed": total_claimed,
                "room_charges": claim.get('room_rent') or 0,
                "surgery_costs": claim.get('surgery_costs') or 0,
                "medicine_costs": claim.get('medicine_costs') or 0,
                "doctor_fees": claim.get('doctor_fees') or 0,
                "investigation_costs": claim.get('investigation_costs') or 0
            },
            "approval_breakdown": {
                "approved_amount": approved_amount,
                "co_pay_amount": claim.get('co_pay_amount') or 0,
                "patient_responsibility": claim.get('patient_responsibility') or 0,
                "claim_utilization_rate": f"{(approved_amount / total_claimed * 100) if total_claimed > 0 else 0:.1f}%"
            },
            "cost_analysis": {
                "cost_appropriateness": self._assess_domain_cost_appropriateness(claim),
                "comparison_to_guidelines": self._compare_to_medical_guidelines(claim)
            }
        }

    def _compare_to_medical_guidelines(self, claim: Dict) -> Dict:
        within_guidelines = claim.get('cost_analysis_within_guidelines', True)
        
        return {
            "claimed_amount": claim.get('total_claim_amount') or 0,
            "typical_range": claim.get('cost_analysis_typical_range', 'N/A'),
            "max_reasonable": claim.get('cost_analysis_max_reasonable', 'N/A'),
            "within_guidelines": within_guidelines,
            "deviation_from_typical": "Within range" if within_guidelines else "Above guidelines"
        }

    def _generate_domain_fraud_analysis(self, claim: Dict) -> Dict:
        fraud_score = claim.get('fraud_score') or 0
        overall_risk = claim.get('overall_risk_score') or 0

        return {
            "risk_assessment": {
                "fraud_risk_score": f"{fraud_score:.1%}",
                "risk_level": "HIGH" if fraud_score > 0.8 else "MEDIUM" if fraud_score > 0.5 else "LOW",
                "overall_risk_score": f"{overall_risk:.1%}"
            },
            "fraud_patterns_detected": claim.get('fraud_indicators', []),
            "detailed_analysis": {}, 
            "domain_specific_red_flags": self._get_domain_red_flags(claim)
        }

    def _get_domain_red_flags(self, claim: Dict) -> List[str]:
        flags = []
        
        if claim.get('is_medically_appropriate', True) is False:
            flags.append("Medically inappropriate treatment")
        
        medical_errors = claim.get('medical_errors', [])
        if medical_errors:
            flags.append(f"{len(medical_errors)} medical appropriateness issues")
        
        # FIX: Ensuring room_rent is treated as number
        if (claim.get('room_rent') or 0) > 50000:
            flags.append("Excessive room charges")
            
        return flags

    def _generate_documents_section(self, claim: Dict) -> Dict:
        files = claim.get('associated_files', [])
            
        return {
            "submitted_documents": files,
            "extracted_data_quality": self._assess_data_quality(claim),
            "document_verification_status": "Verified" if len(files) >= 2 else "Needs Verification"
        }

    def _get_domain_immediate_actions(self, claim: Dict) -> List[str]:
        status = claim.get('status', 'PENDING')
        if status == "DENIED":
            return ["Notify patient of denial with specific reasons", "Document decision in claim system", "Flag similar future claims for review"]
        if status == "UNDER_REVIEW":
            return ["Request additional medical documentation", "Verify treatment details with hospital", "Review with medical director if needed"]
        if status == "APPROVED":
            return ["Process payment for approved amount", "Update patient records", "Monitor for similar claim patterns"]
        return ["Complete comprehensive analysis before decision"]

    def _get_business_recommendations(self, decision_status: str) -> List[str]:
        if decision_status == "DENIED":
            return ["Review denial reasons with provider network", "Consider policy guideline updates if needed", "Monitor for appeal requests"]
        if decision_status == "UNDER_REVIEW":
            return ["Establish clear documentation requirements", "Set review timeline expectations", "Consider provider education if pattern exists"]
        return []

    def _get_medical_review_suggestions(self, claim: Dict) -> List[str]:
        s = []
        if claim.get('medical_errors'):
            s.append("Review treatment with medical director")
        if claim.get('is_medically_appropriate', True) is False:
            s.append("Consider independent medical review")
        return s

    def _get_fraud_prevention_measures(self, claim: Dict) -> List[str]:
        # FIX: Ensuring fraud_score is treated as number
        if (claim.get('fraud_score') or 0) > 0.8:
            return ["Enhanced verification for future claims from this provider", "Review provider billing patterns", "Consider audit of similar treatments"]
        return []

    def _get_process_improvements(self, claim: Dict) -> List[str]:
        improvements = []
        if claim.get('medical_errors'):
            improvements.append("Improve medical guideline communication to providers")
        return improvements

    # ------------------------------------------------------------------
    # LLM integration: generate_decision_reasons
    # ------------------------------------------------------------------
    def deterministic_reasons_from_rules(self, claim: Dict) -> Dict[str, Any]:
        """Produce deterministic reasons from rules (fallback)."""
        reasons_from_db = {}
        try:
            reason_str = claim.get('analysis_reason', '')
            reasons_from_db = {
                "denial_reasons": [r.split("DENIED: ")[1] for r in reason_str.split(" | ") if r.startswith("DENIED:")],
                "review_reasons": [r.split("REVIEW: ")[1] for r in reason_str.split(" | ") if r.startswith("REVIEW:")],
                "approval_reasons": [r.split("APPROVED: ")[1] for r in reason_str.split(" | ") if r.startswith("APPROVED:")]
            }
        except Exception:
            pass

        reasons = {
            "status": claim.get('status', 'PENDING'),
            "short_reasons": [],
            "detailed_explanations": [],
            "provenance": {"rules": [], "model_version": None}
        }

        # FIX: Safety latch for fraud_score
        fraud_score = claim.get('fraud_score') or 0
        if fraud_score > 0.7:
            reasons["short_reasons"].append(f"High fraud score ({fraud_score:.2f})")
            reasons["detailed_explanations"].append(f"Fraud detection model returned a high score ({fraud_score:.2f}).")
            reasons["provenance"]["rules"].append("fraud_score>0.7")
        
        fd_reasons = reasons_from_db.get('denial_reasons') or reasons_from_db.get('review_reasons') or reasons_from_db.get('approval_reasons')
        if fd_reasons and not reasons["short_reasons"]:
            for r in fd_reasons:
                short = self._clean_pdf_text(r, max_len=140)
                reasons["short_reasons"].append(short)
                reasons["detailed_explanations"].append(short)
                reasons["provenance"]["rules"].append("final_decision:from_db")
        
        return reasons

    def _attempt_json_repair(self, text: str) -> Optional[dict]:
        """Try to fix common JSON formatting issues from LLM outputs."""
        if not text:
            return None
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            return None
        text = json_match.group(0)
        text = text.strip()
        if text.startswith("```json"):
            text = text.strip("`").replace("json", "", 1).strip()
        elif text.startswith("```"):
            text = text.strip("`").strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        # Try robust repair
        if "{" in text and "}" in text:
            try:
                repaired = text[text.index("{"): text.rindex("}") + 1]
                return json.loads(repaired)
            except Exception:
                pass
        try:
            text = text.replace("\n", " ").replace("\r", " ").strip()
            text = re.sub(r",\s*}", "}", text)
            text = re.sub(r",\s*]", "]", text)
            return json.loads(text)
        except Exception:
            return None

    def generate_reasons_with_model(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Call the LLM to generate a professional 'Decision Rationale'."""
        
        # 1. Check Config
        if not LLMConfig.ENABLE_LLM:
            logger.debug("LLM disabled in config, using deterministic reasons.")
            return self.deterministic_reasons_from_rules(claim)

        # 2. Prepare Context
        rich_context = {
            "patient_name": claim.get('patient_name'),
            "diagnosis": claim.get('diagnosis'),
            "procedures": claim.get('procedures', []),
            "final_decision": claim.get('status', 'PENDING'),
            "approved_amount": claim.get('approved_amount', 0),
            "patient_responsibility": claim.get('patient_responsibility', 0),
            "medical_issues": claim.get('medical_errors', []) + claim.get('medical_warnings', []),
            "policy_issues": claim.get('policy_limits_exceeded', []) + claim.get('policy_exclusions', [])
        }

        system_prompt = (
            "You are a Senior Claims Adjudicator. Write a formal Decision Rationale. "
            "TONE: Professional, Objective, Concise. "
            "FORMAT: JSON only."
        )

        user_prompt = (
            f"Write the rationale for {rich_context.get('patient_name')}.\n"
            "DATA:\n"
            f"{json.dumps(rich_context, indent=2)}\n\n"
            "**OUTPUT FORMAT:**\n"
            "{\n"
            '  "detailed_explanations": ["The single paragraph rationale text goes here."]\n'
            "}"
        )

        payload = {
            "model": LLMConfig.MODEL_ID,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {"num_predict": LLMConfig.MAX_OUTPUT_TOKENS, "temperature": 0.1},
            "stream": False,
            "format": "json"
        }

        try:
            url = f"{LLMConfig.OLLAMA_URL}/api/chat"
            logger.info("Calling LLM for Decision Rationale...")
            resp = requests.post(url, json=payload, timeout=LLMConfig.TIMEOUT_SECONDS)
            resp.raise_for_status()
            
            model_text = resp.json().get("message", {}).get("content", "")
            parsed = self._attempt_json_repair(model_text)
            
            if parsed and "detailed_explanations" in parsed:
                parsed.setdefault("provenance", {})["model_version"] = LLMConfig.MODEL_ID
                return parsed
            else:
                logger.warning(f"LLM output invalid: {model_text[:100]}...")
                return self.deterministic_reasons_from_rules(claim)
                
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return self.deterministic_reasons_from_rules(claim)

    # ------------------------------------------------------------------
    # --- PDF Rendering & Report Generation ---
    # ------------------------------------------------------------------
    
    # --- PDF Helper Functions ---
    def _set_color(self, pdf: FPDF, type: str):
        if type == 'green':
            pdf.set_fill_color(*self.COLORS['green_bg'])
            pdf.set_text_color(*self.COLORS['green_text'])
        elif type == 'yellow':
            pdf.set_fill_color(*self.COLORS['yellow_bg'])
            pdf.set_text_color(*self.COLORS['yellow_text'])
        elif type == 'red':
            pdf.set_fill_color(*self.COLORS['red_bg'])
            pdf.set_text_color(*self.COLORS['red_text'])
        elif type == 'grey':
            pdf.set_fill_color(*self.COLORS['grey_bg'])
            pdf.set_text_color(*self.COLORS['black'])
        elif type == 'dark_blue':
            pdf.set_fill_color(*self.COLORS['dark_blue'])
            pdf.set_text_color(*self.COLORS['white'])
        else: # Default/reset
            pdf.set_fill_color(*self.COLORS['white'])
            pdf.set_text_color(*self.COLORS['black'])

    def _add_status_box(self, pdf: FPDF, status: str, llm_reason: str = ""):
        status = status.upper()
        if status == 'APPROVED':
            color_type = 'green'
        elif status == 'UNDER_REVIEW':
            color_type = 'yellow'
        elif status == 'DENIED':
            color_type = 'red'
        else:
            color_type = 'grey'
        self._set_color(pdf, color_type)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.multi_cell(0, 12, f" Final Decision: {status}", border=1, align='L', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._set_color(pdf, 'default') # Reset
        if llm_reason:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(*self.COLORS['grey_text'])
            pdf.multi_cell(0, 5, f"> {self._clean_pdf_text(llm_reason, max_len=500)}", new_x='LMARGIN', new_y='NEXT')
            pdf.set_text_color(*self.COLORS['black'])
        pdf.ln(5)

    def _add_key_value_row(self, pdf: FPDF, key: str, value: str):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(45, 8, self._clean_pdf_text(key), border=0, new_x='RIGHT', new_y='TOP')
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 8, self._clean_pdf_text(str(value)), border=0, align='L', new_x='LMARGIN', new_y='NEXT')

    def _add_section_header(self, pdf: FPDF, title: str):
        pdf.set_font('Helvetica', 'B', 12)
        self._set_color(pdf, 'dark_blue')
        pdf.multi_cell(0, 8, f" {title}", fill=True, new_x='LMARGIN', new_y='NEXT')
        self._set_color(pdf, 'default')
        pdf.ln(4)
        
    # --- Main JSON Report Generation ---
    def generate_comprehensive_claim_report(self, claim_id: str) -> Dict:
        """Assemble full domain-specific report and attach decision reasons (LLM or deterministic)."""
        claim = self.db_handler.get_claim_by_id(claim_id)
        if not claim:
            return {"error": f"Claim {claim_id} not found"}
            
        report = {
            "claim_id": claim_id,
            "generated_at": datetime.now().isoformat(),
            "report_type": "comprehensive_domain_specific",
            "sections": {}
        }

        report["sections"]["executive_summary"] = self._generate_domain_executive_summary(claim)
        report["sections"]["business_decision"] = self._generate_business_decision_section(claim)
        report["sections"]["medical_validation"] = self._generate_domain_medical_validation(claim)
        report["sections"]["insurance_coverage"] = self._generate_coverage_analysis(claim)
        report["sections"]["financial_analysis"] = self._generate_domain_financial_analysis(claim)
        report["sections"]["fraud_analysis"] = self._generate_domain_fraud_analysis(claim)
        report["sections"]["documents"] = self._generate_documents_section(claim)
        report["sections"]["recommendations"] = self._generate_domain_recommendations(claim)

        reasons = self.generate_reasons_with_model(claim)
        
        report["sections"]["business_decision"]["model_reasons"] = reasons
        report["sections"]["business_decision"]["rule_reasons"] = self.deterministic_reasons_from_rules(claim)
        
        report["sections"]["business_decision"]["final_decision"] = {
            "status": claim.get('status'),
            "approved_amount": claim.get('approved_amount'),
            "denial_reasons": report["sections"]["business_decision"]["decision_reasons"].get('denial_reasons'),
            "approval_reasons": report["sections"]["business_decision"]["decision_reasons"].get('approval_reasons'),
            "review_reasons": report["sections"]["business_decision"]["decision_reasons"].get('review_reasons')
        }
        return report

    # --- Main PDF Generation ---
    def generate_comprehensive_pdf_report(self, claim_id: str, output_path: str) -> str:
        report = self.generate_comprehensive_claim_report(claim_id)
        if 'error' in report:
            logger.error(f"Failed to generate report data for {claim_id}: {report['error']}")
            return ""

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, margin=20)
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)

        # Header
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(*self.COLORS['dark_blue'])
        pdf.cell(0, 10, f'COMPREHENSIVE MEDICAL CLAIM REPORT', border=0, new_x='LMARGIN', new_y='NEXT', align='C')
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(*self.COLORS['grey_text'])
        pdf.cell(0, 8, f'Claim ID: {claim_id}', border=0, new_x='LMARGIN', new_y='NEXT', align='C')
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 8, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}', border=0, new_x='LMARGIN', new_y='NEXT', align='C')
        pdf.ln(10)

        # Sections
        self._add_executive_summary_to_pdf(pdf, report)
        self._add_business_decision_to_pdf(pdf, report)
        self._add_medical_validation_to_pdf(pdf, report)
        self._add_insurance_coverage_to_pdf(pdf, report)
        self._add_financial_analysis_to_pdf(pdf, report)
        self._add_fraud_analysis_to_pdf(pdf, report)
        self._add_recommendations_to_pdf(pdf, report)

        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        pdf.output(output_path)
        return output_path

    # ------------------------------
    # --- PDF SECTION RENDERERS ---
    # ------------------------------
    def _add_executive_summary_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(*self.COLORS['black'])
        pdf.cell(0, 10, '1. Executive Summary', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 5, "This page provides an at-a-glance overview of the claim, the decision, and the key risk factors.")
        pdf.ln(5)
        summary = report['sections']['executive_summary']
        dec = summary['business_decision']
        model_reasons = report.get('sections', {}).get('business_decision', {}).get('model_reasons', {})
        llm_reason_text = ""
        if model_reasons and model_reasons.get('detailed_explanations'):
            llm_reason_text = model_reasons['detailed_explanations'][0]
        self._add_status_box(pdf, dec['status'], llm_reason_text)
        self._add_section_header(pdf, "Financial Overview")
        fi = summary['financial_overview']
        pdf.set_font('Helvetica', 'B', 11)
        self._set_color(pdf, 'grey')
        pdf.cell(60, 8, "Description", border=1, new_x='RIGHT', new_y='TOP', align='L', fill=True)
        pdf.cell(0, 8, "Amount", border=1, new_x='LMARGIN', new_y='NEXT', align='R', fill=True)
        self._set_color(pdf, 'default')
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(60, 8, "Total Amount Claimed", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('total_claimed', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(60, 8, "Total Amount Approved", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('approved_amount', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(60, 8, "Patient Responsibility", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('patient_responsibility', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.ln(5)
        self._add_section_header(pdf, "Key Risk Dashboard")
        kri = summary['key_risk_indicators']
        pdf.set_font('Helvetica', 'B', 11)
        self._set_color(pdf, 'grey')
        pdf.cell(60, 8, "Metric", border=1, new_x='RIGHT', new_y='TOP', align='L', fill=True)
        pdf.cell(50, 8, "Score / Status", border=1, new_x='RIGHT', new_y='TOP', align='L', fill=True)
        pdf.cell(0, 8, "Risk Level", border=1, new_x='LMARGIN', new_y='NEXT', align='L', fill=True)
        self._set_color(pdf, 'default')
        pdf.set_font('Helvetica', '', 10)
        
        # FIX: Ensure numeric fraud score
        fs = kri.get('fraud_risk_score') or 0
        pdf.cell(60, 8, "Fraud & Risk Analysis", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(50, 8, f"{fs:.1%}", border=1, new_x='RIGHT', new_y='TOP', align='L')
        
        fraud_level = kri.get('fraud_risk_level', 'LOW')
        pdf.cell(0, 8, f"{fraud_level}", border=1, new_x='LMARGIN', new_y='NEXT', align='L')
        
        med_score = kri.get('medical_appropriateness_score') or 0
        med_level = "HIGH" if med_score >= 0.7 else "REVIEW" if med_score >= 0.4 else "LOW"
        pdf.cell(60, 8, "Medical Appropriateness", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(50, 8, f"{med_score:.1%}", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"{med_level}", border=1, new_x='LMARGIN', new_y='NEXT', align='L')
        
        policy_status = kri.get('policy_status', 'VALID')
        pdf.cell(60, 8, "Policy Coverage", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(50, 8, f"Policy: {policy_status}", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"{policy_status}", border=1, new_x='LMARGIN', new_y='NEXT', align='L')
        pdf.ln(5)
        self._add_section_header(pdf, "Claim & Patient Details")
        pi = summary['patient_information']
        mi = summary['medical_information']
        self._add_key_value_row(pdf, "Patient Name", pi.get('name', 'Unknown'))
        self._add_key_value_row(pdf, "Policy Number", pi.get('policy_number', 'Unknown'))
        self._add_key_value_row(pdf, "Hospital", pi.get('hospital', 'Unknown'))
        self._add_key_value_row(pdf, "Diagnosis", mi.get('diagnosis', 'Unknown'))
        self._add_key_value_row(pdf, "Admission Date", mi.get('admission_date', 'Unknown'))
        pdf.ln(6)

    def _add_business_decision_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(*self.COLORS['black'])
        pdf.cell(0, 10, '2. Business Decision Analysis', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        bd = report['sections']['business_decision']
        model_reasons = bd.get('model_reasons', {})
        llm_reason_text = ""
        if model_reasons and model_reasons.get('detailed_explanations'):
            llm_reason_text = model_reasons['detailed_explanations'][0]
        self._add_status_box(pdf, bd.get('final_decision', {}).get('status', 'PENDING'), llm_reason_text)
        self._add_section_header(pdf, "Financial Impact")
        fi = bd.get('financial_impact', {})
        pdf.set_font('Helvetica', 'B', 11)
        self._set_color(pdf, 'grey')
        pdf.cell(60, 8, "Description", border=1, new_x='RIGHT', new_y='TOP', align='L', fill=True)
        pdf.cell(0, 8, "Amount", border=1, new_x='LMARGIN', new_y='NEXT', align='R', fill=True)
        self._set_color(pdf, 'default')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(60, 8, "Approved Amount", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('insurance_payment', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.cell(60, 8, "Co-pay Amount", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('co_pay_amount', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(60, 8, "Patient Responsibility", border=1, new_x='RIGHT', new_y='TOP', align='L')
        pdf.cell(0, 8, f"Rs. {fi.get('patient_responsibility', 0):,.2f}", border=1, new_x='LMARGIN', new_y='NEXT', align='R')
        pdf.ln(5)
        self._add_section_header(pdf, "Decision Reasons (from rules)")
        reasons = bd.get('decision_reasons', {})
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin) 
        pdf.multi_cell(0, 7, "Denial Reasons:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        denial = reasons.get('denial_reasons', [])
        if not denial: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for r in denial: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(r)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin) 
        pdf.multi_cell(0, 7, "Review Reasons:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        review = reasons.get('review_reasons', [])
        if not review: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for r in review: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(r)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin) 
        pdf.multi_cell(0, 7, "Approval Reasons:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        approval = reasons.get('approval_reasons', [])
        if not approval: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for r in approval: 
            pdf.set_x(pdf.l_margin) 
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(r)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(6)

    def _add_medical_validation_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '3. MEDICAL VALIDATION', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        mv = report['sections']['medical_validation']
        da = mv.get('disease_analysis', {})
        ta = mv.get('treatment_analysis', {})
        issues = mv.get('medical_issues', {})
        self._add_section_header(pdf, "Disease Analysis")
        self._add_key_value_row(pdf, "Diagnosis:", da.get('diagnosis'))
        self._add_key_value_row(pdf, "Disease Identified:", da.get('disease_identified'))
        self._add_key_value_row(pdf, "Medical Appropriateness:", str(da.get('medical_appropriateness')))
        self._add_key_value_row(pdf, "Appropriateness Score:", da.get('appropriateness_score'))
        pdf.ln(5)
        self._add_section_header(pdf, "Treatment Analysis")
        self._add_key_value_row(pdf, "Room Type:", ta.get('room_type_used'))
        self._add_key_value_row(pdf, "Treatment Duration:", f"{ta.get('treatment_duration')} days")
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Procedures Performed:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        procedures = ta.get('procedures_performed', [])
        if not procedures:
             pdf.set_x(pdf.l_margin + 5)
             pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for proc in procedures:
            pdf.set_x(pdf.l_margin + 5) # Indent
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(proc)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Medications Prescribed:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        medications = ta.get('medications_prescribed', [])
        if not medications:
             pdf.set_x(pdf.l_margin + 5)
             pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for med in medications:
            pdf.set_x(pdf.l_margin + 5) # Indent
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(med)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        self._add_section_header(pdf, "Medical Issues & Warnings")
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Critical Errors:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        errors = issues.get('critical_errors', [])
        if not errors: 
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for e in errors:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(e)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Warnings:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        warnings = issues.get('warnings', [])
        if not warnings: 
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for w in warnings:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(w)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(6)

    def _add_insurance_coverage_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '4. INSURANCE COVERAGE', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        cov = report['sections']['insurance_coverage']
        pv = cov.get('policy_validation', {})
        fin = cov.get('financial_implications', {})
        ex = cov.get('coverage_violations', {})
        self._add_section_header(pdf, "Policy Details")
        self._add_key_value_row(pdf, "Policy Status:", pv.get('status', 'Unknown'))
        self._add_key_value_row(pdf, "Policy Number:", pv.get('policy_number', 'N/A'))
        self._add_key_value_row(pdf, "Co-pay Applicable:", fin.get('co_pay_percentage', 'N/A'))
        self._add_key_value_row(pdf, "Co-pay Amount:", f"Rs. {fin.get('co_pay_amount', 0):,.2f}")
        pdf.ln(5)
        self._add_section_header(pdf, "Coverage Violations")
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Limits Exceeded:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        limits = ex.get('limit_exceeded', [])
        if not limits: 
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for le in limits:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(le)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, "Excluded Procedures:", new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        excluded = ex.get('excluded_procedures', [])
        if not excluded: 
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for exproc in excluded:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(exproc)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(6)

    def _add_financial_analysis_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '5. FINANCIAL ANALYSIS', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        fa = report['sections']['financial_analysis']
        cb = fa.get('claim_amount_breakdown', {})
        ab = fa.get('approval_breakdown', {})
        ca = fa.get('cost_analysis', {})
        comp = ca.get('comparison_to_guidelines', {})
        self._add_section_header(pdf, "Claim Amount Breakdown")
        self._add_key_value_row(pdf, "Total Claimed:", f"Rs. {cb.get('total_claimed', 0):,.2f}")
        self._add_key_value_row(pdf, "Room Charges:", f"Rs. {cb.get('room_charges', 0):,.2f}")
        self._add_key_value_row(pdf, "Doctor Fees:", f"Rs. {cb.get('doctor_fees', 0):,.2f}")
        self._add_key_value_row(pdf, "Medicine Costs:", f"Rs. {cb.get('medicine_costs', 0):,.2f}")
        self._add_key_value_row(pdf, "Investigation Costs:", f"Rs. {cb.get('investigation_costs', 0):,.2f}")
        self._add_key_value_row(pdf, "Surgery Costs:", f"Rs. {cb.get('surgery_costs', 0):,.2f}")
        pdf.ln(5)
        self._add_section_header(pdf, "Approval Breakdown")
        self._add_key_value_row(pdf, "Approved Amount:", f"Rs. {ab.get('approved_amount', 0):,.2f}")
        self._add_key_value_row(pdf, "Co-pay Amount:", f"Rs. {ab.get('co_pay_amount', 0):,.2f}")
        self._add_key_value_row(pdf, "Patient Responsibility:", f"Rs. {ab.get('patient_responsibility', 0):,.2f}")
        self._add_key_value_row(pdf, "Claim Utilization:", ab.get('claim_utilization_rate', 'N/A'))
        pdf.ln(5)
        self._add_section_header(pdf, "Cost Appropriateness Analysis")
        self._add_key_value_row(pdf, "Cost Appropriateness:", ca.get('cost_appropriateness'))
        self._add_key_value_row(pdf, "Within Guidelines:", str(comp.get('within_guidelines')))
        self._add_key_value_row(pdf, "Typical Range:", comp.get('typical_range'))
        pdf.ln(6)

    def _add_fraud_analysis_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '6. FRAUD & RISK ANALYSIS', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        fa = report['sections']['fraud_analysis']
        ra = fa.get('risk_assessment', {})
        patterns = fa.get('fraud_patterns_detected', [])
        rf = fa.get('domain_specific_red_flags', [])
        self._add_section_header(pdf, "Risk Assessment")
        self._add_key_value_row(pdf, "Fraud Risk Score:", ra.get('fraud_risk_score'))
        self._add_key_value_row(pdf, "Risk Level:", ra.get('risk_level'))
        pdf.ln(5)
        self._add_section_header(pdf, "Detected Fraud Patterns")
        pdf.set_font('Helvetica', '', 11)
        pdf.set_x(pdf.l_margin)
        if not patterns: 
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for p in patterns:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(p)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        self._add_section_header(pdf, "Domain-Specific Red Flags")
        pdf.set_font('Helvetica', '', 11)
        pdf.set_x(pdf.l_margin)
        if not rf: 
            pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
        for r in rf:
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(r)}", new_x='LMARGIN', new_y='NEXT')
        pdf.ln(6)

    def _add_recommendations_to_pdf(self, pdf: FPDF, report: Dict):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '7. RECOMMENDATIONS', border=0, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(5)
        rec = report['sections']['recommendations']
        def put_rec_list(title: str, items: list):
            self._add_section_header(pdf, title)
            pdf.set_font('Helvetica', '', 11) # Reset to normal
            pdf.set_x(pdf.l_margin)
            if not items: 
                pdf.multi_cell(0, 7, "- None -", new_x='LMARGIN', new_y='NEXT')
            for item in items:
                pdf.set_x(pdf.l_margin + 5)
                pdf.multi_cell(0, 7, f"- {self._clean_pdf_text(item)}", new_x='LMARGIN', new_y='NEXT')
            pdf.ln(3)
        put_rec_list("Immediate Actions", rec.get('immediate_actions', []))
        put_rec_list("Business Recommendations", rec.get('business_recommendations', []))
        put_rec_list("Medical Review Suggestions", rec.get('medical_review_suggestions', []))
        put_rec_list("Fraud Prevention Measures", rec.get('fraud_prevention_measures', []))
        put_rec_list("Process Improvements", rec.get('process_improvements', []))
        pdf.ln(6)
        
    def _generate_domain_recommendations(self, claim: dict) -> dict:
        """
        Generates domain-specific recommendations for claim reviewers or auditors.
        This is Section 7 of the report.
        """
        decision = claim.get('status', 'PENDING').upper()
        recommendations = {
            "immediate_actions": self._get_domain_immediate_actions(claim), 
            "business_recommendations": self._get_business_recommendations(decision),
            "medical_review_suggestions": self._get_medical_review_suggestions(claim), 
            "fraud_prevention_measures": self._get_fraud_prevention_measures(claim), 
            "process_improvements": self._get_process_improvements(claim)
        }
        if not any(recommendations.values()):
            recommendations["immediate_actions"] = ["No specific domain recommendations available."]
        return recommendations

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    def generate_analytics_report(self, output_path: str):
        claims = self.db_handler.get_all_claims()
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        if not claims:
            return {"error": "No claims data available"}

        df_data = []
        for claim in claims:
            df_data.append({
                'Claim ID': claim.get('claim_id'),
                'Patient': claim.get('patient_name', 'Unknown'),
                'Diagnosis': claim.get('diagnosis', 'Unknown'),
                'Total Claimed': claim.get('total_claim_amount', 0),
                'Approved Amount': claim.get('approved_amount', 0), 
                'Fraud Score': claim.get('fraud_score') or 0,
                'Medical Score': claim.get('medical_appropriateness_score') or 0,
                'Business Decision': claim.get('status', 'PENDING'),
                'Created Date': claim.get('created_at', '')[:10] if claim.get('created_at') else 'Unknown'
            })

        df = pd.DataFrame(df_data)
        
        # Calculate derived fields for analytics
        approved_claims = df[df['Business Decision'].str.upper() == 'APPROVED']
        
        analytics = {
            "total_claims": len(df),
            "total_claimed_amount": f"Rs.{df['Total Claimed'].sum():,}",
            "total_approved_amount": f"Rs.{approved_claims['Approved Amount'].sum():,}",
            "average_fraud_score": f"{df['Fraud Score'].mean():.1%}" if len(df) > 0 else "0.0%",
            "average_medical_score": f"{df['Medical Score'].mean():.1%}" if len(df) > 0 else "0.0%",
            "approval_rate": f"{(len(approved_claims) / len(df) * 100) if len(df) > 0 else 0:.1f}%",
            "business_decision_distribution": df['Business Decision'].value_counts().to_dict(),
            "high_risk_claims": len(df[df['Fraud Score'] > 0.6]),
            "medical_issues": len(df[df['Medical Score'] < 0.7]) if 'Medical Score' in df else 0,
            "cost_savings": f"Rs.{(df['Total Claimed'].sum() - df['Approved Amount'].sum()):,}"
        }

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Claims Data', index=False)
            pd.DataFrame([analytics], index=[0]).to_excel(writer, sheet_name='Summary Analytics', index=False)
            
            if 'Business Decision' in df.columns:
                decision_analysis = df.groupby('Business Decision').agg({
                    'Total Claimed': ['count', 'sum', 'mean'],
                    'Approved Amount': 'sum',
                    'Fraud Score': 'mean',
                    'Medical Score': 'mean'
                }).round(3)
                decision_analysis.to_excel(writer, sheet_name='Decision Analysis')
            else:
                logger.warning("Analytics: 'Business Decision' column not found for groupby.")

        return analytics


# Test harness
def test_enhanced_report_generation():
    """
    Run a standalone test of the report generator using the latest claim in the DB.
    """
    print("\n🚀 Starting Report Generator Test...\n")
    
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.db_handler import DatabaseHandler
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return
        
    print("🔄 Connecting to Database...")
    db_handler = DatabaseHandler()
    gen = MedicalClaimReportGenerator(db_handler)

    claims = db_handler.get_all_claims()
    if not claims:
        print("❌ No claims found in database.")
        return

    test_claim = claims[0]
    claim_id = test_claim['claim_id']
    print(f"🧪 Selected Claim ID: {claim_id}")

    print("\n1️⃣  Generating JSON Report (calling LLM)...")
    report = gen.generate_comprehensive_claim_report(claim_id)
    
    if 'error' in report:
        print(f"   ❌ Failed: {report['error']}")
    else:
        print("   ✅ JSON Report generated.")

    print("\n2️⃣  Generating PDF Report...")
    os.makedirs("reports", exist_ok=True)
    pdf_path = f"reports/TEST_{claim_id}_report.pdf"
    out_path = gen.generate_comprehensive_pdf_report(claim_id, pdf_path)
    
    if out_path:
        print(f"   ✅ PDF saved to: {out_path}")
    else:
        print("   ❌ PDF generation failed.")

    print("\n✨ Test Complete.\n")

if __name__ == "__main__":
    test_enhanced_report_generation()
    
