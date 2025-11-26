import re
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .disease_knowledge_base import DiseaseKnowledgeBase
from .universal_medical_validator import UniversalMedicalValidator


class UniversalFraudDetector:
    def __init__(self):
        self.knowledge_base = DiseaseKnowledgeBase()
        self.medical_validator = UniversalMedicalValidator()
        self.medical_fraud_patterns = self._initialize_medical_fraud_patterns()
        self.insurance_fraud_rules = self._initialize_insurance_fraud_rules()

    def _get_disease_rules(self, diagnosis: str):
        """Fuzzy match diagnosis to known diseases"""
        diag_clean = re.sub(r'[^a-z]', '', diagnosis.lower())
        for disease, info in self.knowledge_base.knowledge_base.items():
            if disease in diag_clean:
                return info
        if "malaria" in diag_clean:
            return self.knowledge_base.get_disease_info("malaria")
        return None

    def _safe_num(self, value, default=0.0):
        """Safely convert to float, avoiding NoneType math errors"""
        try:
            return float(value) if value not in [None, ""] else default
        except (ValueError, TypeError):
            return default

    def _initialize_medical_fraud_patterns(self) -> Dict:
        """Domain-specific medical claim fraud patterns"""
        return {
            "policy_manipulation": {
                "treatment_after_policy_expiry": {
                    "severity": "high",
                    "description": "Treatment dates after policy expiration",
                    "detection": "admission_date > policy_end_date",
                }
            },
            "medical_treatment_fraud": {
                "unnecessary_procedures": {
                    "severity": "high",
                    "description": "Medically unnecessary procedures billed",
                    "detection": "procedure not in disease_guidelines",
                },
                "extended_stay_fraud": {
                    "severity": "medium",
                    "description": "Hospital stay longer than medically necessary",
                    "detection": "stay_days > max_typical_days * 1.5",
                },
                "luxury_room_abuse": {
                    "severity": "medium",
                    "description": "Luxury rooms for routine treatments",
                    "detection": "executive_room for general_condition",
                },
                "unnecessary_icu": {
                    "severity": "high",
                    "description": "ICU admission for non-critical conditions",
                    "detection": "icu_billed but icu_not_required",
                },
            },
            "billing_fraud": {
                "cost_inflation": {
                    "severity": "high",
                    "description": "Costs exceed reasonable limits for condition",
                    "detection": "cost > max_reasonable_amount",
                }
            },
        }

    def _initialize_insurance_fraud_rules(self) -> Dict:
        """Insurance policy specific fraud rules"""
        return {
            "coverage_violations": [
                "room_rent_exceeds_policy_limit",
                "procedure_not_covered",
                "pre_existing_condition_during_waiting_period",
            ]
        }

    def analyze_claim_fraud(self, claim_data: Dict) -> Dict:
        """Comprehensive fraud analysis for any medical claim"""
        fraud_analysis = {
            "overall_risk_score": 0.0,
            "fraud_probability": 0.0,
            "risk_level": "LOW",
            "detected_patterns": [],
            "recommendation": "APPROVE",
            "detailed_analysis": {},
        }

        # Medical validation
        try:
            medical_validation = self.medical_validator.validate_medical_treatment(
                claim_data
            )
        except Exception as e:
            print(f"❌ Medical validation step failed: {e}")
            medical_validation = {
                "appropriateness_score": 0.0,
                "medical_errors": [f"Validation failed: {e}"],
            }
        fraud_analysis["medical_validation"] = medical_validation

        # Domain analyses
        fraud_analysis["document_analysis"] = self._analyze_document_consistency(claim_data)
        fraud_analysis["behavioral_analysis"] = self._analyze_behavioral_patterns(claim_data)
        fraud_analysis["financial_analysis"] = self._analyze_financial_patterns(claim_data)
        fraud_analysis["medical_fraud_analysis"] = self._analyze_medical_fraud_patterns(claim_data)
        fraud_analysis["insurance_fraud_analysis"] = self._analyze_insurance_fraud(claim_data)

        # Calculate overall risk
        fraud_analysis = self._calculate_domain_specific_risk(fraud_analysis)
        return fraud_analysis

    def _analyze_medical_fraud_patterns(self, claim_data: Dict) -> Dict:
        """Analyze medical treatment specific fraud patterns"""
        patterns = []
        diagnosis = claim_data.get("diagnosis", "")
        # Updated to use fuzzy lookup ---
        disease_info = self._get_disease_rules(diagnosis)
        # Updated to use fuzzy lookup ---

        if disease_info:
            procedures = claim_data.get("procedures", [])
            for procedure in procedures:
                if procedure.lower() in [
                    p.lower() for p in disease_info["unnecessary_treatments"]
                ]:
                    patterns.append({
                        "pattern": "unnecessary_procedure",
                        "severity": "high",
                        "description": f"Unnecessary {procedure} for {disease_info['name']}",
                        "evidence": f"{disease_info['name']} guidelines prohibit this procedure",
                    })

            treatment_days = self._safe_num(claim_data.get("treatment_duration"))
            typical_range = disease_info.get("typical_duration", (0, 0))
            max_typical = self._safe_num(
                typical_range[1] if len(typical_range) > 1 else 0
            )

            if max_typical > 0 and treatment_days > max_typical * 1.5:
                patterns.append({
                    "pattern": "extended_stay_fraud",
                    "severity": "medium",
                    "description": f"Extended stay ({treatment_days} days) for {disease_info['name']}",
                    "evidence": f"Typical stay: {max_typical} days",
                })

            room_type = str(claim_data.get("room_type", "")).lower()
            required_room = disease_info.get("room_type", "general")

            if required_room == "general" and room_type in ["deluxe", "executive", "suite"]:
                patterns.append({
                    "pattern": "luxury_room_abuse",
                    "severity": "medium",
                    "description": f"Luxury room ({room_type}) for routine {disease_info['name']}",
                    "evidence": f"{disease_info['name']} typically requires {required_room} room",
                })

            if not disease_info.get("icu_required") and "icu" in room_type:
                patterns.append({
                    "pattern": "unnecessary_icu",
                    "severity": "high",
                    "description": f"ICU admission for {disease_info['name']}",
                    "evidence": f"{disease_info['name']} does not typically require ICU",
                })

        return {
            "medical_fraud_patterns": patterns,
            "risk_indicators": len(patterns),
            "medical_fraud_score": min(1.0, len(patterns) * 0.3),
        }
        
    def _analyze_insurance_fraud(self, claim_data: Dict) -> Dict:
        """Analyze insurance policy specific fraud"""
        patterns = []

        policy_period = claim_data.get("policy_period", "")
        admission_date = claim_data.get("admission_date", "")
        
        # 1. Policy Expiry Check
        if policy_period and admission_date:
            policy_end = self._extract_policy_end_date(policy_period)
            admission = self._parse_date(admission_date)
            if policy_end and admission and admission > policy_end:
                patterns.append({
                    "pattern": "policy_expiry_fraud",
                    "severity": "high",
                    "description": "Treatment after policy expiration",
                    "evidence": f"Policy ended {policy_end.strftime('%Y-%m-%d')}, admission {admission_date}",
                })

        # 2. Room Rent Abuse Check
        room_rent = self._safe_num(claim_data.get("room_rent"))
        
        # FIX: Try to get limit from claim_data first, default to 5000 only if missing
        room_rent_limit = self._safe_num(claim_data.get("room_rent_limit"), 5000)
        
        if room_rent > room_rent_limit * 1.5:
            patterns.append({
                "pattern": "room_rent_abuse",
                "severity": "medium",
                "description": "Room rent significantly exceeds policy limit",
                "evidence": f"Room rent ₹{room_rent:,} vs limit ₹{room_rent_limit:,}",
            })

        # 3. Policy Exclusion Check (Substance Abuse) -- NEW SECTION ADDED HERE
        # We combine all text values in the claim data to search for keywords anywhere
        all_text = " ".join(str(v) for v in claim_data.values()).lower()
        
        exclusion_keywords = [
            "under influence of alcohol", 
            "alcohol detected", 
            "breathalyzer: positive", 
            "intoxicated", 
            "smell of alcohol"
            # NEW: Cosmetic Checks
            "cosmetic surgery",
            "aesthetic purpose",
            "beautification",
            "rhinoplasty",
            "plastic surgery",
            "improvement of appearance"
        ]
        
        for keyword in exclusion_keywords:
            if keyword in all_text:
                patterns.append({
                    "pattern": "policy_exclusion_substance_abuse",
                    "severity": "high",
                    "description": "Evidence of substance/alcohol use detected",
                    "evidence": f"Found keyword: '{keyword}' in documents",
                })
                break # Found one keyword then no need to keep checking

        return {
            "insurance_fraud_patterns": patterns,
            "risk_indicators": len(patterns),
            "insurance_fraud_score": min(1.0, len(patterns) * 0.4),
        }

    def _analyze_document_consistency(self, claim_data: Dict) -> Dict:
        """Analyze consistency across claim documents"""
        inconsistencies = []
        
        # 1. Check Amounts
        # Use total_claim_amount for both variables if final_bill_amount is missing/same
        bill_amount = self._safe_num(claim_data.get("total_claim_amount")) 
        claim_amount = self._safe_num(claim_data.get("total_claim_amount"))

        if bill_amount > 0 and claim_amount > 0 and abs(bill_amount - claim_amount) > 1000:
            inconsistencies.append({
                "type": "amount_inconsistency",
                "severity": "high",
                "description": f"Bill amount (₹{bill_amount:,}) differs from claimed amount (₹{claim_amount:,})",
            })

        # 2. Check Dates
        admission_dates = self._extract_all_dates(claim_data, "admission_date")
        if len(set(admission_dates)) > 1:
            inconsistencies.append({
                "type": "date_inconsistency",
                "severity": "high",
                "description": "Multiple admission dates found across documents",
            })

        # 3. NEW: Check for Missing MLC/FIR in Accident Cases (THIS IS THE CRITICAL PART)
        diagnosis = claim_data.get('diagnosis', '').lower()
        # Get file list string for searching (passed from pipeline)
        file_list_str = str(claim_data.get('associated_files', [])).lower()
        
        # If it is an accident case...
        if any(x in diagnosis for x in ['accident', 'fracture', 'rta', 'tibia', 'injury']):
            # ...and no Police/MLC/FIR file is found
            if not any(doc in file_list_str for doc in ['fir', 'mlc', 'police', 'report']):
                inconsistencies.append({
                    "type": "missing_document",
                    "severity": "high",
                    "description": "Accident claim missing mandatory MLC/FIR document",
                })

        return {
            "inconsistencies": inconsistencies,
            "is_consistent": len(inconsistencies) == 0,
            "consistency_score": max(0.0, 1.0 - len(inconsistencies) * 0.3),
        }

    def _analyze_behavioral_patterns(self, claim_data: Dict) -> Dict:
        """Analyze behavioral patterns for fraud detection"""
        patterns = []
        admission_date = self._parse_date(claim_data.get("admission_date"))
        if admission_date and admission_date.weekday() >= 5:
            patterns.append({
                "pattern": "weekend_admission",
                "severity": "low",
                "description": "Admission on weekend - possible elective procedure",
                "evidence": f"Admitted on {admission_date.strftime('%A')}",
            })
        return {"behavioral_patterns": patterns, "risk_indicators": len(patterns)}

    def _analyze_financial_patterns(self, claim_data: Dict) -> Dict:
        """Analyze financial patterns for fraud detection"""
        patterns = []
        claim_amount = self._safe_num(claim_data.get("total_claim_amount"))
        room_rent = self._safe_num(claim_data.get("room_rent"))

        if claim_amount > 50000 and claim_amount % 10000 == 0:
            patterns.append({
                "pattern": "round_number_amount",
                "severity": "low",
                "description": f"Round number claim amount: ₹{claim_amount:,}",
                "evidence": "Suspicious round number billing",
            })

        if room_rent > 50000:
            patterns.append({
                "pattern": "excessive_room_rent",
                "severity": "medium",
                "description": f"Excessive room rent: ₹{room_rent:,}",
                "evidence": "Possible room rent inflation",
            })
        return {"financial_patterns": patterns, "risk_indicators": len(patterns)}

    def _calculate_domain_specific_risk(self, fraud_analysis: Dict) -> Dict:
        """Calculate enhanced risk score with domain-specific factors"""
        base_risk = self._calculate_base_risk(fraud_analysis)
        medical_fraud_score = self._safe_num(
            fraud_analysis.get("medical_fraud_analysis", {}).get("medical_fraud_score")
        )
        insurance_fraud_score = self._safe_num(
            fraud_analysis.get("insurance_fraud_analysis", {}).get("insurance_fraud_score")
        )

        enhanced_risk = base_risk * 0.6 + medical_fraud_score * 0.3 + insurance_fraud_score * 0.1
        fraud_analysis["overall_risk_score"] = enhanced_risk
        fraud_analysis["fraud_probability"] = enhanced_risk

        # Updated decision logic ---
        # Add tolerance for minor warnings
        if enhanced_risk >= 0.7:
            fraud_analysis["risk_level"], fraud_analysis["recommendation"] = "HIGH", "REJECT"
        elif enhanced_risk >= 0.45:
            fraud_analysis["risk_level"], fraud_analysis["recommendation"] = "MEDIUM", "REVIEW"
        else:
            fraud_analysis["risk_level"], fraud_analysis["recommendation"] = "LOW", "APPROVE"

        # Auto-approve if all medical warnings are minor
        med_val = fraud_analysis.get("medical_validation", {})
        if fraud_analysis["risk_level"] == "MEDIUM" and len(med_val.get("medical_warnings", [])) <= 2:
            fraud_analysis["risk_level"], fraud_analysis["recommendation"] = "LOW", "APPROVE"
        # Updated decision logic ---

        fraud_analysis["detailed_analysis"] = {
            "primary_reason": self._get_domain_specific_risk_reason(fraud_analysis),
            "risk_factors": self._get_enhanced_risk_factors(fraud_analysis),
            "suggested_actions": self._get_enhanced_suggested_actions(fraud_analysis),
        }
        return fraud_analysis

    def _calculate_base_risk(self, fraud_analysis: Dict) -> float:
        """Calculate base risk score from standard analysis"""
        risk_factors = 0.0
        medical_score = self._safe_num(fraud_analysis["medical_validation"].get("appropriateness_score"))
        consistency_score = self._safe_num(fraud_analysis["document_analysis"].get("consistency_score"))
        behavioral_risk = min(1.0, self._safe_num(fraud_analysis["behavioral_analysis"].get("risk_indicators")) * 0.3)
        financial_risk = min(1.0, self._safe_num(fraud_analysis["financial_analysis"].get("risk_indicators")) * 0.3)

        risk_factors += (1 - medical_score) * 0.3
        risk_factors += (1 - consistency_score) * 0.25
        risk_factors += behavioral_risk * 0.2
        risk_factors += financial_risk * 0.25
        return risk_factors

    def _get_domain_specific_risk_reason(self, fraud_analysis: Dict) -> str:
        risk_score = fraud_analysis["overall_risk_score"]
        if risk_score >= 0.7:
            return "HIGH RISK: Multiple medical and insurance fraud patterns detected"
        elif risk_score >= 0.45: # Adjusted to match new threshold
            return "MEDIUM RISK: Suspicious medical treatment patterns requiring review"
        else:
            return "LOW RISK: Minimal fraud indicators detected"

    def _get_enhanced_risk_factors(self, fraud_analysis: Dict) -> List[str]:
        factors = []
        med_patterns = fraud_analysis.get("medical_fraud_analysis", {}).get("medical_fraud_patterns", [])
        ins_patterns = fraud_analysis.get("insurance_fraud_analysis", {}).get("insurance_fraud_patterns", [])
        if med_patterns:
            factors.append(f"Medical fraud patterns: {len(med_patterns)} detected")
        if ins_patterns:
            factors.append(f"Insurance violations: {len(ins_patterns)} detected")

        med_score = self._safe_num(fraud_analysis["medical_validation"].get("appropriateness_score", 1.0))
        if med_score < 0.7:
            factors.append(f"Medical appropriateness: {med_score:.1%}")
        cons_score = self._safe_num(fraud_analysis["document_analysis"].get("consistency_score", 1.0))
        if cons_score < 0.8:
            factors.append(f"Document consistency: {cons_score:.1%}")
        return factors

    def _get_enhanced_suggested_actions(self, fraud_analysis: Dict) -> List[str]:
        actions = []
        level = fraud_analysis["risk_level"]
        if level == "HIGH":
            actions.extend([
                "🚨 IMMEDIATE INVESTIGATION REQUIRED",
                "Verify all medical treatment appropriateness",
                "Check policy compliance and coverage limits",
                "Contact hospital for treatment justification",
            ])
        elif level == "MEDIUM":
            actions.extend([
                "🔍 Detailed medical review required",
                "Verify treatment duration and room type appropriateness",
                "Check for procedure unbundling or upcoding",
                "Validate policy coverage and exclusions",
            ])
        else:
            actions.extend([
                "✅ Standard processing recommended",
                "Verify key documents authenticity",
            ])
        return actions

    def _extract_all_dates(self, claim_data: Dict, date_field: str) -> List[str]:
        dates = []
        if claim_data.get(date_field):
            dates.append(claim_data[date_field])
        return list(set(d for d in dates if d))

    def _extract_policy_end_date(self, policy_period: str):
        try:
            if policy_period and "to" in policy_period:
                end_date_str = policy_period.split("to")[-1].strip()
                return self._parse_date(end_date_str)
        except:
            pass
        return None

    def _parse_date(self, date_str: str):
        if not date_str:
            return None
        for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def batch_analyze_claims(self, claims_data: List[Dict]) -> List[Dict]:
        return [self.analyze_claim_fraud(claim) for claim in claims_data]
