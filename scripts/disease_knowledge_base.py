# scripts/disease_knowledge_base.py
import json
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

class DiseaseKnowledgeBase:
    def __init__(self):
        self.diseases = self._initialize_disease_database()
        self.treatment_guidelines = self._initialize_treatment_guidelines()
        self.fraud_patterns = self._initialize_fraud_patterns()
        self.insurance_coverage_rules = self._initialize_coverage_rules()

        # Manual alias map for common alternate disease names
        self.aliases = {
            "p vivax malaria": "malaria",
            "falciparum malaria": "malaria",
            "plasmodium malaria": "malaria",
            "typhoid fever": "typhoid",
            "enteric fever": "typhoid",
            "urti": "pneumonia",
            "covid": "pneumonia",
            "corona": "pneumonia",
            "bronchitis": "asthma",
            "renal stone": "kidney_stones",
            "ureteric calculus": "kidney_stones"
        }

        # Merge auto-generated aliases with manual ones
        self.aliases.update(self._auto_generate_aliases())
        
        # Optional Debug Line (Recommended for Testing)
        print(f"[INFO] Auto-generated {len(self.aliases)} disease aliases successfully.")
        
        # Backward compatibility for older modules expecting `.knowledge_base`
        self.knowledge_base = {
            "diseases": self.diseases,
            "treatment_guidelines": self.treatment_guidelines,
            "fraud_patterns": self.fraud_patterns,
            "insurance_coverage_rules": self.insurance_coverage_rules,
            "aliases": self.aliases
        }
    
    def _initialize_disease_database(self) -> Dict:
        """Comprehensive database of 20 diseases across major categories"""
        return {
            # 🦠 Infectious Diseases
            'dengue_fever': {
                'name': 'Dengue Fever',
                'category': 'infectious',
                'typical_duration': (3, 7),
                'cost_range': (15000, 50000),
                'max_reasonable': 80000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['iv_fluids', 'blood_tests', 'platelet_monitoring'],
                'unnecessary_treatments': ['antibiotics', 'mri', 'ct_scan'],
                'common_medications': ['paracetamol', 'iv_fluids', 'antipyretics', 'acetaminophen'],# 'common_medications': ['paracetamol', 'iv_fluids'],
                'red_flags': ['antibiotics_prescribed', 'extended_stay', 'icu_admission']
            },
            'malaria': {
                'name': 'Malaria',
                'category': 'infectious',
                'typical_duration': (3, 7),
                'cost_range': (12000, 40000),
                'max_reasonable': 60000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['antimalarial_drugs', 'blood_tests'], # , 'peripheral_smear', 'smear', 'diagnostic_tests'
                'unnecessary_treatments': ['surgery', 'mri', 'ct_scan'],
                'common_medications': [
                    'chloroquine', 'artemisinin', 'primaquine', 'hydroxychloroquine', 
                    'antimalarial_drugs', 'antipyretics', 'paracetamol', 'dolo'],
                'red_flags': ['surgery_billed', 'extended_stay']
            },
            'typhoid': {
                'name': 'Typhoid Fever',
                'category': 'infectious',
                'typical_duration': (5, 10),
                'cost_range': (20000, 60000),
                'max_reasonable': 90000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['antibiotics', 'blood_culture'],
                'unnecessary_treatments': ['surgery', 'ct_scan'],
                'common_medications': ['ciprofloxacin', 'ceftriaxone', 'antibiotics'],
                'red_flags': ['surgery_billed', 'no_antibiotics']
            },

            # ❤️ Cardiac Diseases
            'heart_attack': {
                'name': 'Heart Attack (Myocardial Infarction)',
                'category': 'cardiac',
                'typical_duration': (5, 14),
                'cost_range': (150000, 500000),
                'max_reasonable': 600000,
                'room_type': 'icu',
                'icu_required': True,
                'surgery_required': True,
                'required_treatments': ['ecg', 'angiography', 'troponin_test'],
                'unnecessary_treatments': [],
                'common_medications': ['aspirin', 'clopidogrel', 'statins', 'painkillers', 'morphine', 'analgesics','iv_fluids'],
                'red_flags': ['no_angiography', 'short_stay', 'low_cost']
            },
            'angina': {
                'name': 'Angina Pectoris',
                'category': 'cardiac',
                'typical_duration': (3, 7),
                'cost_range': (60000, 200000),
                'max_reasonable': 300000,
                'room_type': 'icu',
                'icu_required': True,
                'surgery_required': False,
                'required_treatments': ['ecg', 'stress_test', 'medication'],
                'unnecessary_treatments': ['bypass_surgery'],
                'common_medications': ['nitrates', 'beta_blockers', 'aspirin'],
                'red_flags': ['surgery_billed', 'no_ecg']
            },

            # 🦴 Orthopedic
            'fracture_tibia': {
                'name': 'Tibia Fracture',
                'category': 'orthopedic',
                'typical_duration': (3, 10),
                'cost_range': (80000, 250000),
                'max_reasonable': 350000,
                'room_type': 'private',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['x-ray', 'surgeon'],# 'implants', 'orif', 'nail', 'internal fixation' ,'surgery'],
                'unnecessary_treatments': ['mri', 'extended_physio', 'angiography'],
                'common_medications': ['painkillers', 'antibiotics', 'tramadol', 'cefuroxime','paracetamol', 'diclofenac', 'analgesics', 'iv fluids'],
                'red_flags': ['no_surgery', 'extended_stay'] #  'no_implants',
            },
            'fracture_radius': {
                'name': 'Radius Fracture',
                'category': 'orthopedic',
                'typical_duration': (3, 7),
                'cost_range': (40000, 150000),
                'max_reasonable': 250000,
                'room_type': 'private',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['xray', 'surgery', 'cast'],
                'unnecessary_treatments': ['ct_scan'],
                'common_medications': ['painkillers', 'antibiotics'],
                'red_flags': ['no_xray', 'no_surgery']
            },

            # 🍽️ Gastrointestinal
            'appendicitis': {
                'name': 'Appendicitis',
                'category': 'gastrointestinal',
                'typical_duration': (3, 7),
                'cost_range': (50000, 120000),
                'max_reasonable': 180000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['appendectomy', 'blood_tests', 'ultrasound'],
                'unnecessary_treatments': ['mri'],
                'common_medications': ['antibiotics', 'painkillers'],
                'red_flags': ['no_surgery', 'extended_stay']
            },
            'gallstones': {
                'name': 'Gallstones (Cholelithiasis)',
                'category': 'gastrointestinal',
                'typical_duration': (3, 10),
                'cost_range': (70000, 200000),
                'max_reasonable': 300000,
                'room_type': 'private',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['ultrasound', 'laparoscopic_cholecystectomy'],
                'unnecessary_treatments': ['ct_scan', 'open_surgery'],
                'common_medications': ['painkillers', 'antibiotics'],
                'red_flags': ['no_ultrasound', 'no_surgery']
            },

            # 🌬️ Respiratory
            'pneumonia': {
                'name': 'Pneumonia',
                'category': 'respiratory',
                'typical_duration': (5, 10),
                'cost_range': (25000, 70000),
                'max_reasonable': 100000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['chest_xray', 'antibiotics', 'iv_fluids'],
                'unnecessary_treatments': ['bronchoscopy', 'ct_scan'],
                'common_medications': ['antibiotics', 'bronchodilators'],
                'red_flags': ['no_antibiotics', 'surgery_billed']
            },
            'asthma': {
                'name': 'Asthma',
                'category': 'respiratory',
                'typical_duration': (3, 7),
                'cost_range': (20000, 60000),
                'max_reasonable': 80000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['inhalers', 'nebulization', 'oxygen_support'],
                'unnecessary_treatments': ['mri', 'surgery'],
                'common_medications': ['salbutamol', 'steroids'],
                'red_flags': ['surgery_billed', 'icu_stay']
            },

            # 🧠 Neurological
            'stroke': {
                'name': 'Stroke (Cerebrovascular Accident)',
                'category': 'neurological',
                'typical_duration': (7, 20),
                'cost_range': (100000, 400000),
                'max_reasonable': 600000,
                'room_type': 'icu',
                'icu_required': True,
                'surgery_required': False,
                'required_treatments': ['ct_scan', 'mri', 'physiotherapy'],
                'unnecessary_treatments': ['surgery'],
                'common_medications': ['blood_thinners', 'statins'],
                'red_flags': ['no_brain_scan', 'short_stay']
            },
            'migraine': {
                'name': 'Migraine',
                'category': 'neurological',
                'typical_duration': (1, 3),
                'cost_range': (5000, 20000),
                'max_reasonable': 30000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['pain_management', 'neurology_consult'],
                'unnecessary_treatments': ['ct_scan', 'mri'],
                'common_medications': ['triptans', 'painkillers'],
                'red_flags': ['mri_billed', 'extended_stay']
            },

            # 🩸 Endocrine
            'diabetes': {
                'name': 'Diabetes Mellitus',
                'category': 'endocrine',
                'typical_duration': (3, 7),
                'cost_range': (15000, 50000),
                'max_reasonable': 70000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['blood_sugar_monitoring', 'insulin_therapy'],
                'unnecessary_treatments': ['surgery', 'ct_scan'],
                'common_medications': ['insulin', 'metformin'],
                'red_flags': ['no_glucose_test', 'icu_stay']
            },
            'thyroid_disorder': {
                'name': 'Thyroid Disorder',
                'category': 'endocrine',
                'typical_duration': (3, 5),
                'cost_range': (10000, 40000),
                'max_reasonable': 60000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['thyroid_function_test'],
                'unnecessary_treatments': ['surgery'],
                'common_medications': ['thyroxine', 'carbimazole'],
                'red_flags': ['unnecessary_scan']
            },

            # 🚽 Urological
            'pyelonephritis': {
                'name': 'Acute Pyelonephritis',
                'category': 'urological',
                'typical_duration': (5, 10),
                'cost_range': (30000, 80000),
                'max_reasonable': 120000,
                'room_type': 'general',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['antibiotics', 'urine_culture', 'iv_fluids', 'blood_tests'],
                'unnecessary_treatments': ['surgery', 'lithotripsy', 'dialysis'],
                'common_medications': ['antibiotics', 'ceftriaxone', 'levofloxacin', 'ciprofloxacin','painkillers', 'antipyretics', 'iv_fluids'],
                'red_flags': ['icu_admission', 'extended_stay', 'surgery_billed']
            },
            'kidney_stones': {
                'name': 'Kidney Stones (Urolithiasis)',
                'category': 'urological',
                'typical_duration': (3, 7),
                'cost_range': (50000, 150000),
                'max_reasonable': 200000,
                'room_type': 'private',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['ultrasound', 'lithotripsy'],
                'unnecessary_treatments': ['ct_scan', 'open_surgery'],
                'common_medications': ['painkillers', 'antibiotics'],
                'red_flags': ['no_ultrasound', 'no_surgery']
            },

            # 👁️ Ophthalmology
            'cataract': {
                'name': 'Cataract',
                'category': 'ophthalmology',
                'typical_duration': (1, 3),
                'cost_range': (20000, 60000),
                'max_reasonable': 80000,
                'room_type': 'day_care',
                'icu_required': False,
                'surgery_required': True,
                'required_treatments': ['phacoemulsification', 'lens_implant'],
                'unnecessary_treatments': ['ct_scan', 'blood_tests'],
                'common_medications': ['eye_drops', 'antibiotics'],
                'red_flags': ['extended_stay', 'no_surgery']
            },
            'glaucoma': {
                'name': 'Glaucoma',
                'category': 'ophthalmology',
                'typical_duration': (3, 7),
                'cost_range': (25000, 70000),
                'max_reasonable': 100000,
                'room_type': 'day_care',
                'icu_required': False,
                'surgery_required': False,
                'required_treatments': ['tonometry', 'eye_drops'],
                'unnecessary_treatments': ['surgery'],
                'common_medications': ['timolol', 'latanoprost'],
                'red_flags': ['surgery_billed']
            }
        }

    def _auto_generate_aliases(self) -> Dict:
        """
        Automatically create basic aliases from disease names and keys.
        For example: 'typhoid fever' -> 'typhoid', 'heart_attack' -> 'heart attack'
        """
        auto_aliases = {}
        for key, info in self.diseases.items():
            name = info.get('name', '').lower()
            key_clean = key.replace('_', ' ')
            
            # Generate name-based alias
            if 'fever' in name:
                auto_aliases[name.replace('fever', '').strip()] = key
            if '(' in name:
                alias = name.split('(')[0].strip()
                auto_aliases[alias] = key
            
            # Generate key-based alias
            if ' ' in key_clean:
                auto_aliases[key_clean] = key
            
            # Generate simpler forms
            if key_clean.endswith(' fracture'):
                auto_aliases[key_clean.replace(' fracture', '')] = key
            
            # Common patterns (fever, infection, stones)
            for suffix in [' infection', ' fever', ' stones']:
                if suffix in name:
                    auto_aliases[name.replace(suffix, '').strip()] = key
        return auto_aliases

    def _initialize_coverage_rules(self) -> Dict:
        """Insurance coverage rules for different health plans"""
        return {
            "basic_health_plan": {
                "room_rent_limit": 5000,
                "icu_limit": 15000,
                "surgery_limit": 150000,
                "co_pay": 0.10,
                "day_care_procedures": ["dialysis", "chemotherapy", "endoscopy", "cataract_surgery"],
                "exclusions": ["cosmetic_surgery", "dental_care", "vision_care"],

                # Disease-specific limits
                "disease_specific_limits": {
                    # 🦠 Infectious
                    "dengue_fever": {"max_amount": 80000},
                    "malaria": {"max_amount": 60000},
                    "typhoid": {"max_amount": 90000},

                    # ❤️ Cardiac
                    "heart_attack": {"max_amount": 600000},
                    "angina": {"max_amount": 300000},

                    # 🦴 Orthopedic
                    "fracture_tibia": {"max_amount": 350000},
                    "fracture_radius": {"max_amount": 250000},

                    # 🍽️ Gastrointestinal
                    "appendicitis": {"max_amount": 180000},
                    "gallstones": {"max_amount": 300000},

                    # 🌬️ Respiratory
                    "pneumonia": {"max_amount": 100000},
                    "asthma": {"max_amount": 80000},

                    # 🧠 Neurological
                    "stroke": {"max_amount": 600000},
                    "migraine": {"max_amount": 30000},

                    # 🩸 Endocrine
                    "diabetes": {"max_amount": 70000},
                    "thyroid_disorder": {"max_amount": 60000},

                    # 🚽 Urological
                    "pyelonephritis": {"max_amount": 120000},
                    "kidney_stones": {"max_amount": 200000},

                    # 👁️ Ophthalmology
                    "cataract": {"max_amount": 80000},
                    "glaucoma": {"max_amount": 100000}
                }
            },

            # 🩺 Optional: higher-tier plan (if needed)
            "premium_health_plan": {
                "room_rent_limit": 10000,
                "icu_limit": 25000,
                "surgery_limit": 300000,
                "co_pay": 0.05,
                "day_care_procedures": ["dialysis", "chemotherapy", "endoscopy", "cataract_surgery", "angioplasty"],
                "exclusions": ["cosmetic_surgery", "fertility_treatment"],

                # Higher coverage for all diseases
                "disease_specific_limits": {
                    "dengue_fever": {"max_amount": 120000},
                    "malaria": {"max_amount": 90000},
                    "typhoid": {"max_amount": 120000},
                    "heart_attack": {"max_amount": 800000},
                    "angina": {"max_amount": 400000},
                    "fracture_tibia": {"max_amount": 500000},
                    "fracture_radius": {"max_amount": 350000},
                    "appendicitis": {"max_amount": 250000},
                    "gallstones": {"max_amount": 400000},
                    "pneumonia": {"max_amount": 150000},
                    "asthma": {"max_amount": 120000},
                    "stroke": {"max_amount": 800000},
                    "migraine": {"max_amount": 50000},
                    "diabetes": {"max_amount": 100000},
                    "thyroid_disorder": {"max_amount": 90000},
                    "pyelonephritis": {"max_amount": 180000},
                    "kidney_stones": {"max_amount": 300000},
                    "cataract": {"max_amount": 120000},
                    "glaucoma": {"max_amount": 150000}
                }
            }
        }

    def _initialize_treatment_guidelines(self) -> Dict:
        """Standard treatment cost guidelines"""
        return {
            'room_rent': {
                'general': 2000,
                'private': 5000, 
                'deluxe': 8000,
                'icu': 10000
            },
            'procedure_costs': {
                'angiography': 30000,
                'bypass_surgery': 200000,
                'angioplasty': 150000,
                'fracture_surgery': 80000,
                'appendectomy': 60000
            },
            'investigation_costs': {
                'blood_tests': 2000,
                'xray': 1500,
                'ultrasound': 3000,
                'ct_scan': 8000,
                'mri': 12000
            }
        }
    
    def _initialize_fraud_patterns(self) -> Dict:
        """Common fraud patterns across diseases"""
        return {
            'room_rent_abuse': {
                'description': 'Room rent exceeds policy limits significantly',
                'severity': 'high',
                'detection_logic': 'room_rent > room_rent_limit * 1.5'
            },
            'unnecessary_procedures': {
                'description': 'Medically unnecessary procedures billed',
                'severity': 'high', 
                'detection_logic': 'procedure not in disease_guidelines'
            },
            'extended_stay': {
                'description': 'Hospital stay longer than medically necessary',
                'severity': 'medium',
                'detection_logic': 'stay_days > max_typical_days * 1.3'
            }
        }
    
    def get_disease_info(self, diagnosis: str) -> Optional[Dict]:
        """Get disease information by diagnosis name"""
        diagnosis_key = self._normalize_diagnosis(diagnosis)
        return self.diseases.get(diagnosis_key)
    
    def validate_treatment_appropriateness(self, diagnosis: str, claim_data: Dict) -> Dict:
        """Validate if treatment matches disease guidelines"""
        disease_info = self.get_disease_info(diagnosis)
        
        if not disease_info:
            return {
                'is_valid': True,
                'warnings': [f'Unknown diagnosis "{diagnosis}" - cannot validate'],
                'errors': [],
                'score': 0.5
            }
        
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'score': 1.0,
            'disease_name': disease_info['name']
        }
        
        # Validate treatment duration
        treatment_days = claim_data.get('treatment_duration', 0)
        min_days, max_days = disease_info['typical_duration']
        
        if treatment_days < min_days:
            validation_result['warnings'].append(
                f"Short stay ({treatment_days} days) for {disease_info['name']} (typical: {min_days}-{max_days} days)"
            )
            validation_result['score'] -= 0.1
        
        if treatment_days > max_days * 1.3:
            validation_result['errors'].append(
                f"Extended stay ({treatment_days} days) for {disease_info['name']} (typical: {min_days}-{max_days} days)"
            )
            validation_result['score'] -= 0.3
        
        # Validate claim amount
        claim_amount = claim_data.get('total_claim_amount', 0)
        min_cost, max_cost = disease_info['cost_range']
        max_reasonable = disease_info['max_reasonable']
        
        if claim_amount > max_reasonable:
            validation_result['errors'].append(
                f"Claim amount ₹{claim_amount:,} exceeds maximum reasonable amount ₹{max_reasonable:,} for {disease_info['name']}"
            )
            validation_result['score'] -= 0.4
        
        elif claim_amount < min_cost:
            validation_result['warnings'].append(
                f"Low claim amount ₹{claim_amount:,} for {disease_info['name']} (typical: ₹{min_cost:,}-₹{max_cost:,})"
            )
        
        validation_result['score'] = max(0.0, validation_result['score'])
        
        return validation_result

    def _normalize_diagnosis(self, diagnosis: str) -> str:
        """Normalize diagnosis to match database keys"""
        diagnosis_lower = diagnosis.lower().strip()

        # Map common diagnosis terms to standardized disease keys
        diagnosis_mapping = {
            # 🦠 Infectious
            'dengue': 'dengue_fever',
            'dengue fever': 'dengue_fever',
            'malaria': 'malaria',
            'p. vivax': 'malaria',
            'vivax': 'malaria',
            'plasmodium': 'malaria',
            'falciparum': 'malaria',
            'typhoid': 'typhoid',
            'enteric fever': 'typhoid',

            # ❤️ Cardiac
            'heart attack': 'heart_attack',
            'myocardial infarction': 'heart_attack',
            'mi': 'heart_attack',
            'angina': 'angina',
            'chest pain': 'angina',

            # 🦴 Orthopedic
            'fracture': 'fracture_tibia',  # default mapping if unspecified
            'tibia fracture': 'fracture_tibia',
            'leg fracture': 'fracture_tibia',
            'radius fracture': 'fracture_radius',
            'hand fracture': 'fracture_radius',
            'arm fracture': 'fracture_radius',

            # 🍽️ Gastrointestinal
            'appendicitis': 'appendicitis',
            'appendectomy': 'appendicitis',
            'gallstones': 'gallstones',
            'cholelithiasis': 'gallstones',
            'gall bladder stones': 'gallstones',

            # 🌬️ Respiratory
            'pneumonia': 'pneumonia',
            'lung infection': 'pneumonia',
            'asthma': 'asthma',
            'bronchial asthma': 'asthma',

            # 🧠 Neurological
            'stroke': 'stroke',
            'cva': 'stroke',
            'brain stroke': 'stroke',
            'migraine': 'migraine',
            'headache': 'migrange',

            # 🩸 Endocrine
            'diabetes': 'diabetes',
            'sugar': 'diabetes',
            'hyperglycemia': 'diabetes',
            'thyroid': 'thyroid_disorder',
            'hypothyroidism': 'thyroid_disorder',
            'hyperthyroidism': 'thyroid_disorder',

            # 🚽 Urological
            'pyelonephritis': 'pyelonephritis',
            'kidney infection': 'pyelonephritis',
            'uti': 'pyelonephritis',
            'urinary tract infection': 'pyelonephritis',
            'kidney stone': 'kidney_stones',
            'renal calculus': 'kidney_stones',
            'urolithiasis': 'kidney_stones',

            # 👁️ Ophthalmology
            'cataract': 'cataract',
            'lens opacity': 'cataract',
            'glaucoma': 'glaucoma',
            'eye pressure': 'glaucoma'
        }

        # Find the first matching key in mapping
        for key, value in diagnosis_mapping.items():
            if key in diagnosis_lower:
                return value

        # Default fallback: replace spaces with underscores
        return diagnosis_lower.replace(' ', '_')
    
    def get_coverage_rules(self, policy_type: str = "basic_health_plan") -> Dict:
        """Get insurance coverage rules for policy type"""
        return self.insurance_coverage_rules.get(policy_type, {})
    
    def get_all_diseases(self) -> List[str]:
        """Get list of all supported diseases"""
        return [disease['name'] for disease in self.diseases.values()]
