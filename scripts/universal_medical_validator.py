# scripts/universal_medical_validator.py
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .disease_knowledge_base import DiseaseKnowledgeBase

class UniversalMedicalValidator:
    def __init__(self):
        self.knowledge_base = DiseaseKnowledgeBase()

    def _safe_num(self, value, default=0.0):
        """Ensure numeric safety for math operations"""
        try:
            return float(value) if value not in [None, ''] else default
        except (ValueError, TypeError):
            return default

    def validate_medical_treatment(self, claim_data: Dict) -> Dict:
        """
        Universal validation for any medical claim
        """
        diagnosis = claim_data.get('diagnosis', '')
        disease_info = self.knowledge_base.get_disease_info(diagnosis)
        
        if not disease_info:
            return self._unknown_diagnosis_validation(claim_data)
        
        validation_result = {
            'disease_identified': disease_info['name'],
            'is_medically_appropriate': True,
            'appropriateness_score': 1.0,
            'medical_warnings': [],
            'medical_errors': [],
            'fraud_indicators': [],
            'recommendation': 'APPROVE',
            'cost_analysis': {},
            'treatment_analysis': {}
        }
        
        # Validation steps
        self._validate_treatment_duration(claim_data, disease_info, validation_result)
        self._validate_treatment_costs(claim_data, disease_info, validation_result)
        self._validate_treatment_appropriateness(claim_data, disease_info, validation_result)
        self._validate_room_type(claim_data, disease_info, validation_result)
        self._detect_fraud_patterns(claim_data, disease_info, validation_result)
        self._calculate_final_recommendation(validation_result)
        
        return validation_result
    
    def _validate_treatment_duration(self, claim_data: Dict, disease_info: Dict, result: Dict):
        """Validate treatment duration against guidelines"""
        treatment_days = self._safe_num(claim_data.get('treatment_duration'))
        typical_duration = disease_info.get('typical_duration', (0, 0))
        min_days = self._safe_num(typical_duration[0] if len(typical_duration) > 0 else 0)
        max_days = self._safe_num(typical_duration[1] if len(typical_duration) > 1 else 0)

        if min_days > 0 and treatment_days < min_days:
            result['medical_warnings'].append(
                f"Short stay ({treatment_days} days) for {disease_info['name']} (typical: {min_days}-{max_days} days)"
            )
            result['appropriateness_score'] -= 0.1
        
        if max_days > 0 and treatment_days > max_days * 1.3:
            result['medical_errors'].append(
                f"Extended stay ({treatment_days} days) for {disease_info['name']} (typical: {min_days}-{max_days} days)"
            )
            result['appropriateness_score'] -= 0.3
    
    def _validate_treatment_costs(self, claim_data: Dict, disease_info: Dict, result: Dict):
        """Validate treatment costs against guidelines"""
        claim_amount = self._safe_num(claim_data.get('total_claim_amount'))
        min_cost, max_cost = disease_info.get('cost_range', (0, 0))
        max_reasonable = self._safe_num(disease_info.get('max_reasonable', 0))
        
        result['cost_analysis'] = {
            'claimed_amount': claim_amount,
            'typical_range': f"₹{min_cost:,} - ₹{max_cost:,}",
            'max_reasonable': f"₹{max_reasonable:,}",
            'within_guidelines': min_cost <= claim_amount <= max_reasonable
        }
        
        if claim_amount < min_cost:
            result['medical_warnings'].append(
                f"Low claim amount (₹{claim_amount:,}) for {disease_info['name']}"
            )
        
        if claim_amount > max_reasonable > 0:
            result['medical_errors'].append(
                f"Excessive claim amount (₹{claim_amount:,}) for {disease_info['name']}"
            )
            result['appropriateness_score'] -= 0.4
    
    def _validate_treatment_appropriateness(self, claim_data: Dict, disease_info: Dict, result: Dict):
        """
        Validate if treatments match disease guidelines using Smart Keyword Matching
        (Fixes OCR variation issues)
        """
        treatments = claim_data.get('procedures', [])
        medications = claim_data.get('medications', [])
        
        # Helper for fuzzy matching (e.g., finding 'Chloroquine' inside 'Antimalarial Drugs (Chloroquine)')
        def is_present(required_item, billed_items_list):
            required_clean = required_item.lower().replace('_', ' ').strip()
            for billed_item in billed_items_list:
                billed_clean = billed_item.lower().replace('_', ' ').strip()
                # Check for partial match in either direction
                if required_clean in billed_clean or billed_clean in required_clean:
                    return True
            return False

        # 1. Check for Unnecessary Treatments
        for treatment in disease_info.get('unnecessary_treatments', []):
            if is_present(treatment, treatments):
                result['medical_errors'].append(
                    f"Unnecessary treatment: {treatment} for {disease_info['name']}"
                )
                result['appropriateness_score'] -= 0.2

        # 2. Check for Missing Required Treatments
        required_list = disease_info.get('required_treatments', [])
        # We only need to find ONE of the required variations if synonyms exist
        # But strict logic implies ALL in the list are required. 
        
        for required in required_list:
            if not is_present(required, treatments):
                # Special check: sometimes meds are listed in procedures or vice versa by OCR
                if not is_present(required, medications):
                    result['medical_warnings'].append(
                        f"Missing required treatment: {required} for {disease_info['name']}"
                    )
                    result['appropriateness_score'] -= 0.1

        # 3. Validate Medications (Allow for brand names/combinations)
        common_meds = disease_info.get('common_medications', [])
        
        for med in medications:
            # If the medication list is empty, skip check
            if not common_meds: 
                break
                
            # If the billed med is NOT found in common list
            if not is_present(med, common_meds):
                # Check if it's a generic "Drug" or "Pharmacy" line item which is neutral
                if any(x in med.lower() for x in ['pharmacy', 'consumables', 'medical']):
                    continue
                    
                result['medical_warnings'].append(
                    f"Uncommon medication: {med} for {disease_info['name']}"
                )
                result['appropriateness_score'] -= 0.05

        result['treatment_analysis'] = {
            'treatments_found': treatments,
            'required_treatments': required_list,
            'unnecessary_treatments': disease_info.get('unnecessary_treatments', []),
            'medications_found': medications,
            'common_medications': common_meds
        }
    
    def _validate_room_type(self, claim_data: Dict, disease_info: Dict, result: Dict):
        """Validate room type appropriateness"""
        room_type = str(claim_data.get('room_type', '')).lower()
        required_room = disease_info.get('room_type', 'general')
        
        if disease_info.get('icu_required') and 'icu' not in room_type:
            result['medical_errors'].append(
                f"ICU admission required for {disease_info['name']} but {room_type} room used"
            )
            result['appropriateness_score'] -= 0.3
        
        if required_room == 'general' and room_type in ['deluxe', 'executive', 'suite']:
            result['medical_warnings'].append(
                f"Luxury room ({room_type}) used for routine {disease_info['name']} treatment"
            )
            result['appropriateness_score'] -= 0.1
    
    def _detect_fraud_patterns(self, claim_data: Dict, disease_info: Dict, result: Dict):
        """Detect common fraud patterns"""
        red_flags = disease_info.get('red_flags', [])
        room_rent = self._safe_num(claim_data.get('room_rent'))
        room_limit = self._safe_num(claim_data.get('room_rent_limit'), 5000)
        
        if room_limit > 0 and room_rent > room_limit * 1.5:
            result['fraud_indicators'].append({
                'pattern': 'room_rent_abuse',
                'severity': 'high',
                'description': f'Room rent ₹{room_rent:,} exceeds policy limit ₹{room_limit:,}',
                'evidence': 'Possible billing manipulation'
            })
        
        treatments = claim_data.get('procedures', [])
        for treatment in treatments:
            if treatment.lower() in [t.lower() for t in disease_info['unnecessary_treatments']]:
                result['fraud_indicators'].append({
                    'pattern': 'unnecessary_procedures',
                    'severity': 'high',
                    'description': f'Unnecessary {treatment} for {disease_info["name"]}',
                    'evidence': 'Medically inappropriate billing'
                })
        
        treatment_days = self._safe_num(claim_data.get('treatment_duration'))
        typical_duration = disease_info.get('typical_duration', (0, 0))
        max_typical = self._safe_num(typical_duration[1] if len(typical_duration) > 1 else 0)
        
        if max_typical > 0 and treatment_days > max_typical * 1.5:
            result['fraud_indicators'].append({
                'pattern': 'extended_stay',
                'severity': 'medium',
                'description': f'Extended stay ({treatment_days} days) for {disease_info["name"]}',
                'evidence': f'Typical stay: {max_typical} days'
            })
    
    def _calculate_final_recommendation(self, result: Dict):
        """Calculate final recommendation based on scores"""
        score = max(0.0, result.get('appropriateness_score', 0))
        result['appropriateness_score'] = score
        
        if score >= 0.8:
            result['recommendation'] = 'APPROVE'
        elif score >= 0.6:
            result['recommendation'] = 'REVIEW'
        else:
            result['recommendation'] = 'REJECT'
        
        result['is_medically_appropriate'] = score >= 0.7
    
    def _unknown_diagnosis_validation(self, claim_data: Dict) -> Dict:
        """Validation for unknown diagnoses"""
        return {
            'disease_identified': 'Unknown',
            'is_medically_appropriate': True,
            'appropriateness_score': 0.5,
            'medical_warnings': ['Unknown diagnosis - limited validation possible'],
            'medical_errors': [],
            'fraud_indicators': [],
            'recommendation': 'REVIEW',
            'cost_analysis': {},
            'treatment_analysis': {}
        }
    
    def validate_multiple_claims(self, claims_data: List[Dict]) -> List[Dict]:
        """Validate multiple claims at once"""
        return [self.validate_medical_treatment(claim) for claim in claims_data]

