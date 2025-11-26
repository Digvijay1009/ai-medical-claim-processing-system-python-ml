# scripts/main_processing_pipeline.py
import sys
import os
import logging
from datetime import datetime
import traceback
import json


# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the scripts directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.file_handler import FileHandler
from scripts.text_extractor import TextExtractor
from scripts.ai_validator import AIValidator
from scripts.claim_analyzer import EnhancedClaimAnalyzer
from scripts.db_handler import DatabaseHandler

# Import our new enhanced systems
try:
    from scripts.universal_medical_validator import UniversalMedicalValidator
    from scripts.universal_fraud_detector import UniversalFraudDetector
    from scripts.disease_knowledge_base import DiseaseKnowledgeBase
    ENHANCED_SYSTEMS_AVAILABLE = True
    print("✅ Enhanced medical validation systems imported successfully")
except ImportError as e:
    ENHANCED_SYSTEMS_AVAILABLE = False
    print(f"⚠️ Enhanced systems not available: {e}")
    print("🔄 Using basic validation systems")


class DomainSpecificClaimProcessingPipeline:
    def __init__(self):
        """Initializes all the handler components for domain-specific pipeline."""
        self.file_handler = FileHandler()
        self.text_extractor = TextExtractor()
        self.ai_validator = AIValidator()
        self.claim_analyzer = EnhancedClaimAnalyzer()
        self.db_handler = DatabaseHandler()
        
        # Initialize enhanced systems
        self.medical_validator = None
        self.fraud_detector = None
        self.disease_knowledge_base = None
        self._initialize_enhanced_systems()

    def _initialize_enhanced_systems(self):
        """Initialize the enhanced medical and fraud detection systems"""
        if ENHANCED_SYSTEMS_AVAILABLE:
            try:
                self.medical_validator = UniversalMedicalValidator()
                self.fraud_detector = UniversalFraudDetector()
                self.disease_knowledge_base = DiseaseKnowledgeBase()
                logging.info("✅ Enhanced medical validation systems initialized")
            except Exception as e:
                logging.error(f"❌ Enhanced systems initialization failed: {e}")
                self.medical_validator = None
                self.fraud_detector = None
        else:
            logging.info("🔄 Using basic validation systems (enhanced systems not available)")

    def process_claim_comprehensive(self, uploaded_files: list) -> dict:
        """
        Complete domain-specific claim processing with comprehensive reporting
        """
        logging.info("🏥 Starting domain-specific claim processing...")

        try:
            # Step 1: Save uploaded files
            claim_id, file_paths = self.file_handler.save_uploaded_files(uploaded_files)
            logging.info(f"📁 Step 1: Files saved. Claim ID: {claim_id}")

            # Step 2: Extract and consolidate text
            consolidated_text = self.text_extractor.extract_and_consolidate_text(file_paths)
            logging.info(f"📄 Step 2: Text extracted. Length: {len(consolidated_text)}")

            # Step 3: Enhanced AI validation and data extraction
            extracted_data = self.ai_validator.validate_and_extract_with_llm(consolidated_text)
            extracted_data['full_text_dump'] = consolidated_text
            extracted_data['associated_files'] = [f.name for f in uploaded_files]
            extracted_data = self._normalize_extracted_fields(extracted_data)
            # 🧠 Normalize keys before passing to analyzer
            extracted_data = self._normalize_extracted_fields(extracted_data)
            logging.info(f"🤖 Step 3: Enhanced AI data extraction complete. Fields extracted: {len(extracted_data)}")

            # Step 4: Comprehensive Claim Analysis with Business Decisions
            comprehensive_report = self.claim_analyzer.analyze_claim_comprehensive(extracted_data)
            comprehensive_report['claim_info']['claim_id'] = claim_id
            logging.info(f"🎯 Step 4: Comprehensive analysis complete. Decision: {comprehensive_report['final_decision']['status']}")

            # Step 4.5: Optional - Enhance report with LLM (Mistral) reasoning
            try:
                from scripts.llm_extr import MistralReasoningEngine

                llm_engine = MistralReasoningEngine()
                comprehensive_report = llm_engine.enhance_report_with_llm(comprehensive_report)

                logging.info("🤖 Step 4.5: LLM explanations successfully added to report")

            except Exception as e:
                logging.warning(f"⚠️ LLM enhancement skipped: {e}")

            # Step 5: Save to database
            self._save_comprehensive_claim(
                claim_id=claim_id,
                consolidated_text=consolidated_text,
                extracted_data=extracted_data,
                report=comprehensive_report,
                file_paths=file_paths
            )
            logging.info(f"💾 Step 5: Comprehensive claim {claim_id} saved to database.")

            # Step 6: Save individual documents
            self._save_claim_documents(claim_id, uploaded_files, file_paths)
            logging.info(f"📋 Step 6: Claim documents saved for {claim_id}")

            # Step 7: Automatically generate comprehensive PDF report
            try:
                from scripts.report_generator import MedicalClaimReportGenerator

                report_generator = MedicalClaimReportGenerator(self.db_handler)
                pdf_path = report_generator.generate_comprehensive_pdf_report(
                    claim_id, f"reports/{claim_id}_comprehensive_report.pdf"
                )

                logging.info(f"📄 Step 7: Comprehensive PDF report generated successfully: {pdf_path}")
            except Exception as e:
                logging.error(f"❌ Failed to generate PDF report automatically: {e}")

            # Return full report (so Streamlit or UI can render it)
            return comprehensive_report

        except Exception as e:
            logging.error(f"❌ Error in domain-specific claim processing pipeline: {str(e)}")
            logging.error(f"🔍 Full traceback: {traceback.format_exc()}")
            raise e

    def _save_comprehensive_claim(self, claim_id: str, consolidated_text: str,
                                      extracted_data: dict, report: dict, file_paths: list):
        """
        Save comprehensive claim to database by 'flattening' the report
        to match the new data contract for the report generator.
        """
        claim_record = {}
        try:
            # --- 1. Start with the flat extracted data ---
            claim_record = extracted_data.copy()

            # --- 2. Add/Overwrite with key pipeline metadata ---
            claim_record.update({
                'claim_id': claim_id,
                'consolidated_text': consolidated_text,
                'associated_files': [os.path.basename(fp) for fp in file_paths],
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            })

            # --- 3. Flatten the 'report' object (analysis results) ---
            
            # From 'claim_info'
            claim_info = report.get('claim_info', {})
            claim_record.update({
                'policy_number': claim_info.get('policy_number', claim_record.get('policy_number')),
                'patient_name': claim_info.get('patient_name', claim_record.get('patient_name')),
                'admission_date': claim_info.get('date_of_service', claim_record.get('admission_date')),
                'hospital_name': claim_info.get('hospital_name', claim_record.get('hospital_name')),
                'treating_doctor': claim_info.get('treating_doctor', claim_record.get('treating_doctor')),
            })

            # From 'medical_details'
            medical_details = report.get('medical_details', {})
            claim_record.update({
                'diagnosis': medical_details.get('diagnosis', claim_record.get('diagnosis')), 
                'medical_appropriateness_score': medical_details.get('medical_appropriateness_score'),
            })

            # From 'financial_breakdown'
            financial_breakdown = report.get('financial_breakdown', {})
            claim_record.update({
                'total_claim_amount': financial_breakdown.get('total_claimed', claim_record.get('total_claim_amount')),
            })

            # --- 4. Flatten 'validation_results' ---
            validation_results = report.get('validation_results', {})
            
            # Flatten 'medical_validation'
            medical_validation = validation_results.get('medical_validation', {})
            claim_record.update({
                'is_medically_appropriate': medical_validation.get('is_medically_appropriate', True),
                'disease_identified': medical_validation.get('disease_identified'),
                'medical_errors': medical_validation.get('medical_errors', []),
                'medical_warnings': medical_validation.get('medical_warnings', []),
                'cost_analysis_within_guidelines': medical_validation.get('cost_analysis', {}).get('within_guidelines', True),
                'cost_analysis_typical_range': medical_validation.get('cost_analysis', {}).get('typical_range', 'N/A'),
                'cost_analysis_max_reasonable': medical_validation.get('cost_analysis', {}).get('max_reasonable', 'N/A'),
            })
            
            # Flatten 'fraud_analysis'
            fraud_analysis = validation_results.get('fraud_analysis', {})
            claim_record.update({
                'fraud_score': validation_results.get('fraud_risk_score'),
                'overall_risk_score': validation_results.get('fraud_risk_score'),
                'fraud_indicators': fraud_analysis.get('detected_patterns', []),
            })
            
            # Flatten 'rule_based_validation'
            rule_validation = validation_results.get('rule_based_validation', {})
            claim_record.update({
                'validation_errors': rule_validation.get('reasons', []),
                'policy_status': rule_validation.get('policy_status', 'VALID'), 
                'policy_exclusions': rule_validation.get('policy_exclusions', []), 
                'policy_limits_exceeded': rule_validation.get('policy_limits_exceeded', []), 
                'policy_waiting_period_issues': rule_validation.get('waiting_period_issues', []), 
            })

            # --- 5. Flatten 'final_decision' (THIS IS THE FIX) ---
            final_decision = report.get('final_decision', {})
            claim_record.update({
                'status': final_decision.get('status', 'Pending').title(),
                'reviewer_name': final_decision.get('reviewer_name'),
                'review_comments': final_decision.get('review_comments'),
                'analysis_reason': self._format_decision_reasons(final_decision),
                
                # --- CORRECTED KEYS ---
                'approved_amount': final_decision.get('approved_amount', 0),
                'co_pay_amount': final_decision.get('co_pay_amount', 0), # Was 'co_pay'
                'patient_responsibility': final_decision.get('patient_responsibility', 0),
            })

            # --- 6. REMOVE the old nested fields ---
            if 'medical_validation_result' in claim_record:
                del claim_record['medical_validation_result']
            if 'extracted_json' in claim_record:
                del claim_record['extracted_json']

            # This call will now insert the fully flattened, consistent record
            self.db_handler.insert_claim(claim_record)

        except Exception as e:
            logging.error(f"❌ Failed to save comprehensive claim: {e}")
            logging.error(f"🔍 Full traceback: {traceback.format_exc()}")
            logging.error(f"🚨 Failing claim record data (first 500 chars): {str(claim_record)[:500]}")
            raise e

    def _format_decision_reasons(self, decision: dict) -> str:
        """Format decision reasons for database storage"""
        reasons = []
        if decision.get('denial_reasons'):
            reasons.extend([f"DENIED: {reason}" for reason in decision['denial_reasons']])
        if decision.get('review_reasons'):
            reasons.extend([f"REVIEW: {reason}" for reason in decision['review_reasons']])
        if decision.get('approval_reasons'):
            reasons.extend([f"APPROVED: {reason}" for reason in decision['approval_reasons']])

        return " | ".join(reasons) if reasons else "No specific reasons provided"

    def _save_claim_documents(self, claim_id: str, uploaded_files: list, file_paths: list):
        """Save individual document records for the claim"""
        try:
            document_types = self._classify_document_types(uploaded_files)

            for i, (file, file_path) in enumerate(zip(uploaded_files, file_paths)):
                doc_type = 'other'
                if file.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.tif')):
                    doc_type = document_types[i] if i < len(document_types) else 'other'

                allowed_types = [
                    'policy', 'hospital_bill', 'medical_bill', 'discharge_summary',
                    'claim_form', 'fir', 'pre_authorization', 'investigation_report', 'other'
                ]
                if doc_type not in allowed_types:
                    doc_type = 'other'

                self.db_handler.add_claim_document(
                    claim_id=claim_id,
                    document_type=doc_type,
                    file_name=file.name,
                    file_path=file_path,
                    extracted_data={}
                )

        except Exception as e:
            logging.warning(f"⚠️ Document saving failed: {e}. Claim processing continues.")
            logging.warning(f"🔍 Traceback: {traceback.format_exc()}")

    def _classify_document_types(self, uploaded_files: list) -> list:
        """Classify document types based on file names"""
        document_types = []

        for file in uploaded_files:
            file_name_lower = file.name.lower()

            if 'policy' in file_name_lower:
                doc_type = 'policy'
            elif 'bill' in file_name_lower:
                if 'medical' in file_name_lower or 'pharmacy' in file_name_lower:
                    doc_type = 'medical_bill'
                else:
                    doc_type = 'hospital_bill'
            elif 'discharge' in file_name_lower:
                doc_type = 'discharge_summary'
            elif 'claim' in file_name_lower:
                doc_type = 'claim_form'
            elif 'fir' in file_name_lower:
                doc_type = 'fir'
            elif 'pre-auth' in file_name_lower:
                doc_type = 'pre_authorization'
            else:
                doc_type = 'other'

            document_types.append(doc_type)

        return document_types
    
    def _normalize_extracted_fields(self, data: dict) -> dict:
        """
        Normalize inconsistent field names from AI extraction into
        a standard schema expected by the analyzer and report generator.
        """

        # 1️ Define all known aliases from LLM or PDF extraction
        field_aliases = {
            "claim_amount": "total_claim_amount",
            "claimed_amount": "total_claim_amount",
            "gross_total": "total_claim_amount",
            "bill_amount": "total_claim_amount",
            "disease": "diagnosis",
            "medical_condition": "diagnosis",
            "hospital": "hospital_name",
            "hospital_details": "hospital_name",
            "doctor": "treating_doctor",
            "physician": "treating_doctor",
            "admit_date": "admission_date",
            "date_of_admission": "admission_date",
            "discharge": "discharge_date",
            "date_of_discharge": "discharge_date",
            "policy_no": "policy_number",
            "policyid": "policy_number",
            "sum_insured_amount": "sum_insured"
        }

        normalized = data.copy()

        # 2️ Apply alias mapping (copy missing standard fields)
        for old_key, new_key in field_aliases.items():
            if old_key in data and new_key not in data:
                normalized[new_key] = data[old_key]

        # 3️ Auto-clean numeric fields (ensure integers, not strings)
        numeric_fields = [
            "total_claim_amount", "room_rent", "doctor_fees",
            "medicine_costs", "investigation_costs", "surgery_costs", "sum_insured"
        ]
        for key in numeric_fields:
            try:
                if key in normalized and isinstance(normalized[key], str):
                    normalized[key] = int(normalized[key].replace(",", "").replace("₹", "").strip())
            except:
                pass

        # 4️ Guarantee required defaults so report never breaks
        normalized.setdefault("diagnosis", "Unknown")
        normalized.setdefault("total_claim_amount", 0)
        normalized.setdefault("hospital_name", "Unknown")
        normalized.setdefault("admission_date", None)
        normalized.setdefault("discharge_date", None)

        print(f"🧩 Normalized extracted fields: {len(normalized)} keys (ready for analyzer)")
        print(json.dumps(normalized, indent=2))
        return normalized

    # Legacy method for backward compatibility
    def process_claim_batch(self, uploaded_files: list) -> dict:
        """Legacy method for backward compatibility"""
        return self.process_claim_comprehensive(uploaded_files)


# Backward compatibility aliases
EnhancedClaimProcessingPipeline = DomainSpecificClaimProcessingPipeline
ClaimProcessingPipeline = DomainSpecificClaimProcessingPipeline
