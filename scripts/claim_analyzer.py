# scripts/claim_analyzer.py
import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List
import xgboost as xgb
import numpy as np
import pickle


try:
    from scripts.universal_medical_validator import UniversalMedicalValidator
    from scripts.universal_fraud_detector import UniversalFraudDetector
    from scripts.disease_knowledge_base import DiseaseKnowledgeBase
except ImportError:
    # Fallback for initial implementation
    UniversalMedicalValidator = None
    UniversalFraudDetector = None
    DiseaseKnowledgeBase = None

class ClaimDecisionEngine:
    """Business decision engine for medical claim processing"""
    
    def calculate_final_decision(self, claim_record: dict, coverage_analysis: dict) -> dict:
        """Calculate final business decision with clear reasons"""
        
        # Extract key metrics
        fraud_score = claim_record.get('fraud_score', 0)
        medical_score = claim_record.get('medical_appropriateness_score', 1.0)
        policy_status = coverage_analysis.get('policy_validation', {}).get('status', 'VALID')
        # 🧠 DEBUG LINE — to see actual decision parameters
        print(f"[DEBUG] Fraud Score: {fraud_score}, Medical Score: {medical_score}, Policy: {policy_status}")

        denial_reasons = []
        approval_reasons = []
        review_reasons = []
        
        # AUTOMATIC DENIAL RULES
        if policy_status == 'EXPIRED':
            denial_reasons.append("Policy expired before treatment date")
        
        if coverage_analysis.get('exclusions_found'):
            denial_reasons.append(f"Excluded procedures: {', '.join(coverage_analysis['exclusions_found'])}")
        
        if fraud_score > 0.8:
            denial_reasons.append("High fraud risk detected")
        
        if medical_score < 0.3:
            denial_reasons.append("Medically inappropriate treatment")
        
        # AUTOMATIC APPROVAL RULES
        if (not denial_reasons and 
            fraud_score < 0.4 and 
            medical_score > 0.7 and
            not coverage_analysis.get('coverage_limits', {}).get('exceeded_limits') and
            policy_status == 'VALID'):
            approval_reasons.append("Low risk, medically appropriate, within coverage limits")
        
        # MANUAL REVIEW RULES
        if fraud_score > 0.4 and fraud_score <= 0.7:
            review_reasons.append("Moderate fraud risk requires manual review")
        
        if coverage_analysis.get('coverage_limits', {}).get('exceeded_limits'):
            review_reasons.append("Coverage limits exceeded - requires adjustment")
        
        if medical_score <= 0.7:
            review_reasons.append("Medical appropriateness concerns require review")
        
        if not claim_record.get('diagnosis'):
            review_reasons.append("Missing or unclear diagnosis")
        
        # FINAL DECISION LOGIC
        total_claimed = claim_record.get('total_claim_amount', 0)
        co_pay = coverage_analysis.get('co_pay_applicable', 0)
        
        if denial_reasons:
            status = "DENIED"
            approved_amount = 0
        elif not review_reasons and approval_reasons:
            status = "APPROVED"
            approved_amount = total_claimed * (1 - co_pay)
        else:
            status = "UNDER_REVIEW"
            approved_amount = 0
        
        print(f"[DEBUG] Decision: {status}, Reasons -> Denial: {denial_reasons}, Review: {review_reasons}, Approval: {approval_reasons}")

        return {
            "status": status,
            "approved_amount": round(approved_amount, 2),
            "denial_reasons": denial_reasons,
            "approval_reasons": approval_reasons,
            "review_reasons": review_reasons,
            "co_pay_amount": round(total_claimed * co_pay, 2),
            "patient_responsibility": round(total_claimed - approved_amount, 2),
            "decision_date": datetime.now().isoformat()
        }

class InsuranceCoverageValidator:
    """Validate insurance policy coverage and limits"""
    
    def validate_coverage(self, claim_data: dict) -> dict:
        """Validate insurance coverage against policy rules"""
        
        coverage_result = {
            "policy_validation": {
                "status": "VALID",
                "reasons": []
            },
            "coverage_limits": {
                "room_rent_limit": 5000,
                "icu_limit": 15000,
                "surgery_limit": 150000,
                "exceeded_limits": []
            },
            "co_pay_applicable": 0.10,
            "exclusions_found": [],
            "waiting_period_violations": []
        }
        
        # Policy Date Validation
        self._validate_policy_dates(claim_data, coverage_result)
        
        # Coverage Limits Validation
        self._validate_coverage_limits(claim_data, coverage_result)
        
        # Procedure Exclusions
        self._validate_procedure_exclusions(claim_data, coverage_result)
        
        return coverage_result
    
    def _validate_policy_dates(self, claim_data: dict, result: dict):
        """Validate policy dates"""
        policy_period = claim_data.get('policy_period', '')
        admission_date = claim_data.get('admission_date', '')
        
        if policy_period and admission_date:
            try:
                policy_end = self._extract_policy_end_date(policy_period)
                admission = datetime.strptime(admission_date, '%Y-%m-%d')
                
                if policy_end and admission > policy_end:
                    result["policy_validation"]["status"] = "EXPIRED"
                    result["policy_validation"]["reasons"].append(
                        f"Policy expired on {policy_end.strftime('%Y-%m-%d')}, admission on {admission_date}"
                    )
            except:
                pass
    
    def _validate_coverage_limits(self, claim_data: dict, result: dict):
        """Validate coverage limits - FIXED Room Rent Logic & Preserved Surgery Logic"""
        
        # Get all the values we need from the AI-extracted data
        total_room_rent = claim_data.get('room_rent') or 0
        
        # Default to 1 day to prevent DivisionByZeroError if duration is missing
        treatment_duration = claim_data.get('treatment_duration') or 1
        
        # Get the *actual* limit extracted from the policy, 
        # but fall back to the hard-coded one if not found.
        daily_limit = claim_data.get('room_rent_limit') or result["coverage_limits"].get("room_rent_limit") or 0

        # Only run the check if all numbers are valid
        if total_room_rent > 0 and daily_limit > 0:
            
            # This is the new calculation
            calculated_daily_rent = total_room_rent / treatment_duration
            
            # This is the new, correct comparison
            if calculated_daily_rent > daily_limit:
                result["coverage_limits"]["exceeded_limits"].append(
                    f"Daily room rent ₹{calculated_daily_rent:,.2f} (₹{total_room_rent:,} / {treatment_duration} days) exceeds limit ₹{daily_limit:,}"
                )

        # This part is copied exactly from your code, as requested.
        surgery_cost = claim_data.get('surgery_cost', 0) or 0  # Handle None
        if surgery_cost > result["coverage_limits"]["surgery_limit"]:
            result["coverage_limits"]["exceeded_limits"].append(
                f"Surgery cost ₹{surgery_cost:,} exceeds limit ₹{result['coverage_limits']['surgery_limit']:,}"
            )
    
    def _validate_procedure_exclusions(self, claim_data: dict, result: dict):
        """Check for excluded procedures"""
        procedures = claim_data.get('procedures', [])
        # diagnosis = claim_data.get('diagnosis', '').lower()
        raw_diagnosis = claim_data.get('diagnosis')
        if raw_diagnosis:
            diagnosis = str(raw_diagnosis).lower()
        else:
            diagnosis = ""  # Handle None/Null gracefully
        
        excluded_procedures = ['cosmetic_surgery', 'dental_implants']
        for proc in procedures:
            if proc: # Only check if proc is not None
                if any(excluded in proc.lower() for excluded in excluded_procedures):
                    result["exclusions_found"].append(proc)
        
        # Disease-specific exclusions
        if 'cosmetic' in diagnosis:
            result["exclusions_found"].append("Cosmetic procedures excluded")
    
    def _extract_policy_end_date(self, policy_period: str):
        """Extract end date from policy period string"""
        try:
            if policy_period and 'to' in policy_period:
                end_date_str = policy_period.split('to')[-1].strip()
                return datetime.strptime(end_date_str, '%Y-%m-%d')
        except:
            pass
        return None

class EnhancedClaimAnalyzer:
    def __init__(self, model_path: str = "models/xgb_fraud_production.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.label_encoders = None
        
        # Initialize enhanced validation systems
        self.medical_validator = None
        self.fraud_detector = None
        self.decision_engine = ClaimDecisionEngine()
        self.coverage_validator = InsuranceCoverageValidator()
        self._initialize_enhanced_systems()
        
        self._load_production_model()
    
    def _initialize_enhanced_systems(self):
        """Initialize the enhanced medical and fraud detection systems"""
        try:
            if UniversalMedicalValidator:
                self.medical_validator = UniversalMedicalValidator()
                self.fraud_detector = UniversalFraudDetector()
                print("✅ Enhanced medical validation systems initialized")
            else:
                print("⚠️ Enhanced systems not available - using basic validation")
        except Exception as e:
            print(f"⚠️ Enhanced systems initialization failed: {e}")
    
    def _load_production_model(self):
        """Load the production-trained model"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.model = model_data['model']
                self.scaler = model_data['scaler']
                self.label_encoders = model_data.get('label_encoders', {})
                print("✅ Production model loaded successfully")
            else:
                print("❌ Production model not found, using enhanced demo mode")
                self._create_enhanced_demo_model()
                
        except Exception as e:
            print(f"❌ Error loading production model: {e}")
            self._create_enhanced_demo_model()
    
    def _create_enhanced_demo_model(self):
        """Fallback to enhanced demo model with medical intelligence"""
        self.model = "enhanced_demo_model"
        print("✅ Enhanced demo model activated")
    
    def analyze_claim_comprehensive(self, extracted_data: Dict) -> Dict:
        """
        Enhanced claim analysis with medical validation, fraud detection, and business decisions
        """
        print("🔍 Starting comprehensive claim analysis...")
        
        # Step 1: Medical Validation
        medical_validation = self._perform_medical_validation(extracted_data)
        
        # Step 2: Rule-based validation
        rule_result = self._perform_rule_checks(extracted_data)
        
        # Step 3: ML-based scoring
        if self.model and self.model != "enhanced_demo_model":
            ml_result = self._production_ml_scoring(extracted_data)
        else:
            ml_result = self._enhanced_demo_scoring(extracted_data, medical_validation)
        
        # Step 4: Fraud Analysis
        fraud_analysis = self._perform_fraud_analysis(extracted_data)
        
        # Step 5: Insurance Coverage Validation
        coverage_analysis = self.coverage_validator.validate_coverage(extracted_data)
        
        # Step 6: Combine all results
        combined_result = self._combine_analysis_results(
            ml_result, rule_result, medical_validation, fraud_analysis
        )

        # Create a single, complete record for the decision engine.
        # Start with the original data...
        decision_input_record = extracted_data.copy()
        
        # ...and update it with the final analysis scores and results.
        decision_input_record.update(combined_result)
        
        # ...and add the medical score to the top level where the engine expects it.
        decision_input_record['medical_appropriateness_score'] = medical_validation.get('appropriateness_score', 1.0)
        # --- END FIX ---
        
        # Step 7: Business Decision
        business_decision = self.decision_engine.calculate_final_decision(
            decision_input_record, coverage_analysis
        )
        
        # Step 8: Comprehensive Report
        comprehensive_report = self._generate_comprehensive_report(
            # extracted_data, combined_result, coverage_analysis, business_decision
            decision_input_record,
            decision_input_record,
            coverage_analysis,
            business_decision
        )
        
        return comprehensive_report
    
    def _perform_medical_validation(self, data: Dict) -> Dict:
        """Perform medical treatment validation"""
        if not self.medical_validator:
            return {
                'is_medically_appropriate': True,
                'appropriateness_score': 1.0,
                'medical_warnings': ['Medical validation system not available'],
                'medical_errors': [],
                'recommendation': 'REVIEW'
            }
        
        try:
            return self.medical_validator.validate_medical_treatment(data)
        except Exception as e:
            print(f"❌ Medical validation failed: {e}")
            return {
                'is_medically_appropriate': True,
                'appropriateness_score': 0.5,
                'medical_warnings': [f'Medical validation error: {str(e)}'],
                'medical_errors': [],
                'recommendation': 'REVIEW'
            }
    
    def _perform_fraud_analysis(self, data: Dict) -> Dict:
        """Perform comprehensive fraud analysis"""
        if not self.fraud_detector:
            return {
                'overall_risk_score': 0.0,
                'risk_level': 'LOW',
                'detected_patterns': []
            }
        
        try:
            return self.fraud_detector.analyze_claim_fraud(data)
        except Exception as e:
            print(f"❌ Fraud analysis failed: {e}")
            return {
                'overall_risk_score': 0.0,
                'risk_level': 'LOW',
                'detected_patterns': []
            }
    
    def _generate_comprehensive_report(self, data: Dict, analysis: Dict, coverage: Dict, decision: Dict) -> Dict:
        """Generate comprehensive claim report"""
        medical_validation = analysis.get('medical_validation', {})
        
        return {
            # Claim Identification
            "claim_info": {
                "claim_id": data.get('claim_id', 'Unknown'),
                "patient_name": data.get('patient_name', 'Unknown'),
                "policy_number": data.get('policy_number', 'Unknown'),
                "date_of_service": data.get('admission_date', 'Unknown'),
                "hospital_name": data.get('hospital_name', 'Unknown'),
                "treating_doctor": data.get('treating_doctor', 'Unknown')
            },
            
            # Medical Information
            "medical_details": {
                "diagnosis": data.get('diagnosis', 'Unknown'),
                "treatment_duration": self._calculate_treatment_duration(data),
                "procedures": data.get('procedures', []),
                "medications": data.get('medications', []),
                "room_type": data.get('room_type', 'Unknown'),
                "disease_identified": medical_validation.get('disease_identified', 'Unknown'),
                "medical_appropriateness_score": medical_validation.get('appropriateness_score', 0)
            },
            
            # Financial Information
            "financial_breakdown": {
                "total_claimed": data.get('total_claim_amount', 0),
                "room_charges": data.get('room_rent', 0),
                "surgery_costs": data.get('surgery_costs', 0),
                "medicine_costs": data.get('medicine_costs', 0),
                "doctor_fees": data.get('doctor_fees', 0),
                "investigation_costs": data.get('investigation_costs', 0)
            },
            
            # Insurance Coverage Analysis
            "coverage_analysis": coverage,
            
            # Validation Results
            "validation_results": {
                "fraud_risk_score": analysis.get('fraud_score', 0),
                "medical_validation": medical_validation,
                "rule_based_validation": analysis.get('rule_based_result', {}),
                "fraud_analysis": analysis.get('fraud_analysis', {})
            },
            
            # Final Business Decision
            "final_decision": decision,
            
            # Documents Processed
            "documents_processed": self._get_processed_documents(data),
            
            # Timestamp
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def _calculate_treatment_duration(self, data: dict) -> int:
        """Calculate treatment duration from admission/discharge dates"""
        try:
            admission = data.get('admission_date')
            discharge = data.get('discharge_date')
            if admission and discharge:
                adm_dt = datetime.strptime(admission, '%Y-%m-%d')
                dis_dt = datetime.strptime(discharge, '%Y-%m-%d')
                return (dis_dt - adm_dt).days
        except:
            pass
        return data.get('treatment_duration', 0)
    
    def _get_processed_documents(self, data: Dict) -> List[str]:
        """Get list of processed documents"""
        documents = []
        doc_fields = ['claim_form', 'hospital_bill', 'medical_bill', 'discharge_summary', 'policy_copy', 'fir_copy']
        for field in doc_fields:
            if data.get(field):
                documents.append(field.replace('_', ' ').title())
        return documents

    # Keep existing methods for backward compatibility
    def analyze_claim(self, extracted_data: Dict) -> Dict:
        """Legacy method for backward compatibility"""
        return self.analyze_claim_comprehensive(extracted_data)
    
    def _production_ml_scoring(self, data: Dict) -> Dict:
        """Use production ML model for fraud scoring"""
        try:
            features = self._engineer_enhanced_features(data)
            features_scaled = self.scaler.transform([features])
            fraud_probability = self.model.predict_proba(features_scaled)[0, 1]
            
            return {
                'fraud_score': round(float(fraud_probability), 3),
                'analysis_reason': 'ML-based fraud detection',
                'ml_confidence': 0.9
            }
        except Exception as e:
            print(f"Production ML scoring failed: {e}")
            return self._enhanced_demo_scoring(data, {})
    
    def _enhanced_demo_scoring(self, data: Dict, medical_validation: Dict) -> Dict:
        """Enhanced demo scoring with medical intelligence"""
        base_score = 0.1
        med_score = medical_validation.get('appropriateness_score', 1.0) or 1.0
        base_score += (1 - med_score) * 0.3
        
        claim_amount = data.get('total_claim_amount', 0) or 0
        if claim_amount > 100000:
            base_score += 0.2
        
        fraud_score = round(base_score, 3)
        # fraud_score = min(max(base_score + np.random.normal(0, 0.05), 0), 1)
        
        return {
            'fraud_score': round(fraud_score, 3),
            'analysis_reason': f'Demo analysis - Medical appropriateness: {med_score:.1%}',
            'ml_confidence': 0.6
        }
    
    def _combine_analysis_results(self, ml_result: Dict, rule_result: Dict, medical_validation: Dict, fraud_analysis: Dict) -> Dict:
        """
        Combine all analysis results into a single, consistent dictionary.
        This function calculates the final fraud score and ensures the
        risk_level and detected_patterns match that final score.
        """
        
        # 1. Aggregate all scores
        fraud_scores = [
            ml_result.get('fraud_score', 0),
            rule_result.get('fraud_score', 0),
            fraud_analysis.get('overall_risk_score', 0),
            (1 - (medical_validation.get('appropriateness_score') or 1.0)) # Safer check for None
        ]
        final_fraud_score = max(fraud_scores)
        
        # 2. Aggregate all reasons/patterns from all modules
        all_patterns = []
        all_patterns.extend(fraud_analysis.get('detected_patterns', []))
        
        # Add rule-based reasons
        if rule_result.get('analysis_reason', "All basic checks passed") != "All basic checks passed":
            all_patterns.append(rule_result.get('analysis_reason'))
        
        # Add medical warnings
        if medical_validation.get('medical_warnings'):
            all_patterns.extend([f"Medical: {w}" for w in medical_validation['medical_warnings']])
        if medical_validation.get('medical_errors'):
             all_patterns.extend([f"Medical Error: {e}" for e in medical_validation['medical_errors']])

        # Remove empty or None patterns
        all_patterns = [str(p) for p in all_patterns if p]

        # 3. Determine new, consistent risk level based on the final score
        if final_fraud_score >= 0.8:
            final_risk_level = 'HIGH'
        elif final_fraud_score >= 0.5:
            final_risk_level = 'MEDIUM'
        else:
            final_risk_level = 'LOW'

        # 4. Creating an new, consistent fraud_analysis dictionary
        # This is the new, unified source of truth for fraud.
        consistent_fraud_analysis = {
            'overall_risk_score': round(final_fraud_score, 3),
            'risk_level': final_risk_level,
            'detected_patterns': all_patterns if all_patterns else ['No specific fraud patterns detected']
        }

        # 5. Return the combined results
        return {
            'fraud_score': round(final_fraud_score, 3), # Kept for backward compatibility
            'analysis_reason': 'Comprehensive analysis completed',
            'medical_validation': medical_validation,
            'rule_based_result': rule_result,
            'ml_result': ml_result,
            'fraud_analysis': consistent_fraud_analysis # <-- THE FIX
        }
    
    def _perform_rule_checks(self, data: Dict) -> Dict:
        """Perform critical rule-based validation checks"""
        fraud_score = 0.0
        reasons = []
        
        # Policy date validation
        if data.get('admission_date') and data.get('policy_period'):
            try:
                admission_date = datetime.strptime(data['admission_date'], '%Y-%m-%d')
                policy_end = self._extract_policy_end_date(data['policy_period'])
                
                if policy_end and admission_date > policy_end:
                    fraud_score = max(fraud_score, 0.9)
                    reasons.append("Claim Rejected: Hospitalization occurred after policy expired.")
            except:
                pass
        
        return {
            'fraud_score': fraud_score,
            'analysis_reason': ' | '.join(reasons) if reasons else "All basic checks passed"
        }
    
    def _extract_policy_end_date(self, policy_period: str):
        """Extract end date from policy period string"""
        try:
            if policy_period and 'to' in policy_period:
                end_date_str = policy_period.split('to')[-1].strip()
                return datetime.strptime(end_date_str, '%Y-%m-%d')
        except:
            pass
        return None
    
    def _engineer_enhanced_features(self, data: Dict) -> list:
        """Engineer enhanced features with medical intelligence"""
        features = []
        claim_amount = data.get('total_claim_amount', 0)
        features.append(np.log1p(claim_amount))
        
        # Add basic features
        features.extend([0, 45, 0, 0.5])  # Placeholder values
        
        return features

# Backward compatibility
ClaimAnalyzer = EnhancedClaimAnalyzer
