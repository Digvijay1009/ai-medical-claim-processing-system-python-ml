# code with fallback adjusted first check above and then 
import json
import re
import requests
from typing import Dict, Optional, List
from datetime import datetime

# ------------------------------------------------------------------
# --- JSON repair function (copied from our other fixes) ---
# ------------------------------------------------------------------
def _attempt_json_repair(text: str) -> Optional[dict]:
    """
    Try to fix common JSON formatting issues from LLM outputs.
    """
    if not text:
        return None

    # Find the JSON blob
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        return None
    
    text = json_match.group(0) # Get only the JSON part

    # Remove Markdown fences
    text = text.strip()
    if text.startswith("```json"):
        text = text.strip("`").replace("json", "", 1).strip()
    elif text.startswith("```"):
        text = text.strip("`").strip()

    # Try clean parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try extracting JSON object from within text
    if "{" in text and "}" in text:
        try:
            repaired = text[text.index("{"): text.rindex("}") + 1]
            return json.loads(repaired)
        except Exception:
            pass

    # Try removing trailing commas or control chars
    try:
        text = text.replace("\n", " ").replace("\r", " ").strip()
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        return json.loads(text)
    except Exception:
        return None
# ------------------------------------------------------------------


class AIValidator:
    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        self.ollama_base_url = ollama_base_url

    def validate_and_extract_with_llm(self, consolidated_text: str) -> Dict:
        """
        Extract structured data from consolidated text with enhanced medical fields
        """
        print("🤖 Attempting LLM extraction with enhanced medical fields...")

        # Try LLM first with enhanced prompt
        llm_result = self._call_ollama_enhanced(consolidated_text)
        if llm_result and self._is_valid_extraction(llm_result):
            print("✅ LLM extraction successful!")
            return llm_result

        # Fallback to enhanced rule-based extraction with medical fields
        print("🔄 LLM failed, using enhanced rule-based extraction")
        return self._enhanced_medical_extraction(consolidated_text)

    def _call_ollama_enhanced(self, consolidated_text: str) -> Optional[Dict]:
        """Enhanced LLM call with medical and policy fields"""
        prompt = f"""EXTRACT MEDICAL INSURANCE CLAIM INFORMATION FROM THE DOCUMENTS:

TEXT:
{consolidated_text}  # Increased limit for medical details

EXTRACT AS JSON WITH THESE FIELDS:
- policy_number (string)
- policy_period (string "YYYY-MM-DD to YYYY-MM-DD")
- sum_insured (integer)
- room_rent_limit (integer)
- patient_name (string)
- patient_dob (string "YYYY-MM-DD")
- hospital_name (string)
- diagnosis (string - be specific about medical condition)
- admission_date (string "YYYY-MM-DD")
- discharge_date (string "YYYY-MM-DD")
- treatment_duration (integer - days)
- total_claim_amount (integer)
- room_rent (integer)
- doctor_fees (integer)
- medicine_costs (integer)
- investigation_costs (integer)
- surgery_costs (integer)
- claim_type (string: "cashless", "reimbursement", or "accident")
- procedures (array of strings - list medical procedures)
- medications (array of strings - list medications prescribed)
- room_type (string: "general", "private", "icu", "deluxe")

CRITICAL RULES:
1. 'procedures' and 'medications' MUST be lists of individual strings.
2. DO NOT combine items with "&" or "and". Split them. 
   Example: Write ["Painkillers", "Antibiotics"], NOT ["Painkillers & Antibiotics"].
3. Extract numbers as integers (remove commas and currency symbols).
4. Return ONLY valid JSON, NO EXPLANATIONS.

EXAMPLE 1 :
{{
  "policy_number": "HLT-2024-34567",
  "policy_period": "2025-01-01 to 2025-12-31",
  "sum_insured": 500000,
  "room_rent_limit": 5000,
  "patient_name": "Amit Patel",
  "patient_dob": "1988-06-12",
  "hospital_name": "Yashoda Hospital, Hyderabad",
  "diagnosis": "Dengue Fever (Uncomplicated)",
  "admission_date": "2025-09-05",
  "discharge_date": "2025-09-15",
  "treatment_duration": 10,
  "total_claim_amount": 195000,
  "room_rent": 80000,
  "doctor_fees": 20000,
  "medicine_costs": 40000,
  "investigation_costs": 35000,
  "surgery_costs": 0,
  "claim_type": "reimbursement",
  "procedures": ["IV Fluids", "Blood Tests", "Platelet Monitoring"],
  "medications": ["Paracetamol", "IV Fluids"],
  "room_type": "executive"
}}
EXAMPLE 2 (Accident Claim):
{{
  "policy_number": "POL987654321",
  "policy_period": "2025-04-01 to 2026-03-31",
  "sum_insured": 1000000,
  "room_rent_limit": null,
  "patient_name": "Vikram Verma",
  "patient_dob": "1980-11-22",
  "hospital_name": "Lifeline Trauma Center, Mumbai",
  "diagnosis": "Fracture of Right Tibia due to Road Traffic Accident (RTA)",
  "admission_date": "2025-10-09",
  "discharge_date": "2025-10-16",
  "treatment_duration": 7,
  "total_claim_amount": 253000,
  "room_rent": 35000,
  "doctor_fees": 60000,
  "medicine_costs": 25000,
  "investigation_costs": 12000,
  "surgery_costs": 40000,
  "claim_type": "accident",
  "procedures": ["Open Reduction and Internal Fixation (ORIF)", "X-Ray", "Blood Work", "Physiotherapy"],
  "medications": ["Painkillers & Antibiotics", "IV Fluids", "Anesthesia Drugs"],
  "room_type": "private"
}}"""

        try:
            print("🔄 Calling Ollama with enhanced medical prompt...")
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1
                    }
                },
                timeout=660
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result['response'].strip()
                print(f"📨 Raw LLM response: {response_text[:200]}...")

                # --- START FIX: Use robust JSON repair function ---
                extracted_data = _attempt_json_repair(response_text)
                
                if extracted_data:
                    print(f"✅ Parsed enhanced JSON with {len(extracted_data)} fields")
                    return extracted_data
                else:
                    print(f"❌ JSON parsing failed. Full response: {response_text}")
                # --- END FIX ---

            else:
                print(f"❌ Ollama API error: {response.status_code}")

        except Exception as e:
            print(f"❌ LLM call failed: {e}")

        return None
    
    def _is_valid_extraction(self, data: Dict) -> bool:
        """
        Check if the extracted data is valid.
        We MUST have a diagnosis for the downstream logic to work.
        """
        if not isinstance(data, dict):
            return False

        # --- THIS IS THE NEW RULE ---
        # Rule 1: 'diagnosis' is a hard requirement.
        if not data.get('diagnosis'):
            print("❌ LLM extraction invalid: 'diagnosis' field is missing or empty.")
            return False
        
        # Rule 2: 'total_claim_amount' is also a hard requirement.
        if not data.get('total_claim_amount'):
            print("❌ LLM extraction invalid: 'total_claim_amount' field is missing or empty.")
            return False

        # Only if both checks pass, let the data in.
        return True
    
    # def _is_valid_extraction(self, data: Dict) -> bool:
    #     """Check if the extracted data is valid for medical validation"""
    #     if not isinstance(data, dict):
    #         return False

    #     # Check if we have essential medical fields
    #     required_medical_fields = ['diagnosis', 'total_claim_amount', 'patient_name']
    #     valid_count = sum(1 for field in required_medical_fields if data.get(field) not in [None, ''])

    #     return valid_count >= 2

    def _enhanced_medical_extraction(self, text: str) -> Dict:
        """Enhanced rule-based extraction with medical field support"""
        print("🔍 Using enhanced medical rule-based extraction...")

        extracted = {
            "policy_number": None,
            "policy_period": None,
            "sum_insured": None,
            "room_rent_limit": None,
            "patient_name": None,
            "patient_dob": None,
            "hospital_name": None,
            "diagnosis": None,
            "admission_date": None,
            "discharge_date": None,
            "treatment_duration": None,
            "total_claim_amount": None,
            "room_rent": None,
            "doctor_fees": None,
            "medicine_costs": None,
            "investigation_costs": None,
            "surgery_costs": None,
            "claim_type": None,
            "procedures": [],
            "medications": [],
            "room_type": None
        }

        # Extract policy details
        extracted.update(self._extract_policy_details(text))
        
        # Extract patient details
        extracted.update(self._extract_patient_details(text))
        
        # Extract hospital and treatment details
        extracted.update(self._extract_treatment_details(text))
        
        # Extract financial details
        extracted.update(self._extract_financial_details(text))
        
        # Determine claim type
        extracted["claim_type"] = self._determine_claim_type(text)
        
        # Calculate treatment duration
        if extracted["admission_date"] and extracted["discharge_date"]:
            try:
                # Use the _convert_date function to be safe
                admit_str = self._convert_date(extracted["admission_date"])
                discharge_str = self._convert_date(extracted["discharge_date"])
                
                if admit_str and discharge_str:
                    admit = datetime.strptime(admit_str, '%Y-%m-%d')
                    discharge = datetime.strptime(discharge_str, '%Y-%m-%d')
                    extracted["treatment_duration"] = (discharge - admit).days
            except:
                extracted["treatment_duration"] = None # Default to None if calculation fails

        print(f"✅ Enhanced medical extraction completed with {len([v for v in extracted.values() if v])} fields")
        return extracted

    def _extract_policy_details(self, text: str) -> Dict:
        """Extract policy-related information"""
        details = {}
        
        # Policy number
        policy_patterns = [
            r'Policy Number:\s*([A-Z0-9\-]+)',
            r'Policy No:\s*([A-Z0-9\-]+)',
            r'HLT-\d{4}-\d{5}',
            r'POL[A-Z0-9\-]+' # --- NEW: Generic pattern ---
        ]
        
        for pattern in policy_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["policy_number"] = match.group(1) if match.groups() else match.group(0)
                break

        # Sum insured
        sum_patterns = [
            r'Sum Insured:\s*₹?\s*([\d,]+)',
            r'Coverage Amount:\s*₹?\s*([\d,]+)',
            r'₹\s*([\d,]+)\s*Coverage'
        ]
        
        for pattern in sum_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["sum_insured"] = self._extract_numeric_value(match.group(1))
                break

        # Room rent limit
        room_limit_patterns = [
            r'Room Rent Limit:\s*₹?\s*([\d,]+)',
            r'Room Rent.*₹?\s*([\d,]+).*per day',
            r'up to.*₹?\s*([\d,]+).*room'
        ]
        
        for pattern in room_limit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["room_rent_limit"] = self._extract_numeric_value(match.group(1))
                break

        return details

    def _extract_patient_details(self, text: str) -> Dict:
        """Extract patient-related information"""
        details = {}
        
        # Patient name
        name_patterns = [
            r'Patient Name:\s*([^\n\r]+)',
            r'Name of Patient:\s*([^\n\r]+)',
            r'Patient:\s*([^\n\r]+)',
            r'Mr\.?\s*([A-Za-z\s]+)(\n|\r)' # --- NEW: Handle names like Mr. Rakesh Gupta ---
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["patient_name"] = match.group(1).strip()
                break

        # Date of birth
        dob_patterns = [
            r'Date of Birth:\s*(\d{2}-\d{2}-\d{4})',
            r'DOB:\s*(\d{2}-\w{3}-\d{4})',
            r'Birth Date:\s*(\d{2}/\d{2}/\d{4})'
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["patient_dob"] = self._convert_date(match.group(1))
                break

        return details

    # --- THIS FUNCTION IS NOW UPDATED ---

    def _extract_treatment_details(self, text: str) -> Dict:
        """Extract medical treatment information"""
        details = {}
        
        # Hospital name
        hospital_patterns = [
            r'Hospital Name:\s*([^\n\r]+)',
            r'Name of Hospital:\s*([^\n\r]+)',
            r'Yashoda Hospital[^\n\r]*',
            r'Lifeline Trauma Center[^\n\r]*',
            r'Apollo Heart Institute[^\n\r]*'
        ]
        
        for pattern in hospital_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["hospital_name"] = match.group(1).strip() if match.groups() else match.group(0)
                break

        # --- FIX: Diagnosis (smarter patterns) ---
        # Tries to find specific medical terms, avoids grabbing "Past Medical History:"
        diagnosis_patterns = [
            # This pattern is now non-greedy (.*?) and stops at a newline (\n)
            r'Diagnosis:\s*([A-Za-z0-9\s\(\)\-]+(Fever|Attack|Fracture|Infarction|Failure|Dengue|Malaria|Trauma|Injury).*?)\n',
            r'Final Diagnosis:\s*([A-Za-z0-9\s\(\)\-]+)',
            r'Diagnosis at Time of Admission:\s*([A-Za-z0-9\s\(\)\-]+)',
            r'Medical Condition:\s*([A-Za-z0-9\s\(\)\-]+)'
        ]
        
        for pattern in diagnosis_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                diag = match.group(1).strip()
                diag = re.sub(r"\(.*?\)", "", diag).strip()  # Clean (P. vivax) etc.
                if "history" not in diag.lower(): # Final check
                    details["diagnosis"] = diag
                    break # Found a good one, stop
        
        # Fallback if no smart pattern matched
        if not details.get("diagnosis"):
            match = re.search(r'Diagnosis:\s*([^\n\r]+)', text, re.IGNORECASE)
            if match:
                diag = match.group(1).strip()
                if "history" not in diag.lower() and "procedures" not in diag.lower():
                     details["diagnosis"] = diag

        # --- FIX: Extract Admission and Discharge Dates (added / support) ---
        date_regex = r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})'
        date_patterns = [
            f'Admission Date:\s*{date_regex}',
            f'Date of Admission:\s*{date_regex}',
            f'Admitted on:\s*{date_regex}'
        ]
        for pattern in date_patterns:
             match = re.search(pattern, text, re.IGNORECASE)
             if match:
                details["admission_date"] = self._convert_date(match.group(1))
                break

        date_patterns = [
            f'Discharge Date:\s*{date_regex}',
            f'Date of Discharge:\s*{date_regex}',
            f'Discharged on:\s*{date_regex}',
            f'Bill Date:\s*{date_regex}' # Use Bill Date as a fallback
        ]
        for pattern in date_patterns:
             match = re.search(pattern, text, re.IGNORECASE)
             if match:
                details["discharge_date"] = self._convert_date(match.group(1))
                break
        
        # Room type
        room_type_patterns = [
            r'Room Rent.*(Suite|Executive|Deluxe|Private|General|ICU)',
            r'Room Category.*(Suite|Executive|Deluxe|Private|General|ICU)',
            r'(Suite|Executive|Deluxe|Private|General|ICU).*Room'
        ]
        
        for pattern in room_type_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details["room_type"] = match.group(1).lower()
                break

        # Extract procedures and medications
        details["procedures"] = self._extract_procedures(text)
        details["medications"] = self._extract_medications(text)

        return details

    # scripts/ai_validator.py
    def _extract_financial_details(self, text: str) -> Dict:
        """Extract financial information"""
        details = {}
        
        # 1. Total Claim Amount (Consolidated List)
        # We use '.*?' to jump over OCR noise like quotes (") and commas (,)
        total_patterns = [
            r'TOTAL ESTIMATED COST.*?₹?\s*([\d,]+)', # Matches ALL your Pre-Auth forms
            r'Net Payable.*?₹?\s*([\d,]+)',           # Matches "Perfect Claim" Bill
            r'Gross Total.*?₹?\s*([\d,]+)',           # Matches "Heart Attack/Fraud" Bill
            r'TOTAL CLAIMED AMOUNT.*?₹?\s*([\d,]+)',
            r'TOTAL:.*?₹?\s*([\d,]+)',                # Matches Pharmacy totals
            r'Total Amount.*?₹?\s*([\d,]+)'
        ]
        
        # Find the maximum value among all matches
        max_val = 0
        for pattern in total_patterns:
            # We use DOTALL so '.*?' can jump over newlines if needed
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for m in matches:
                val = self._extract_numeric_value(m)
                if val and val > max_val:
                    max_val = val
        
        details["total_claim_amount"] = max_val if max_val > 0 else None

        # 2. Extract Individual Components 
        # (Updated to use simpler, non-greedy regexes compatible with the new helper)

        # Room Rent
        details["room_rent"] = self._extract_cost_component(text, r'Room Rent.*?₹?\s*([\d,]+)')
        
        # Add ICU charges to Room Rent if found
        icu_val = self._extract_cost_component(text, r'ICU Charges.*?₹?\s*([\d,]+)')
        if icu_val:
            details["room_rent"] = (details["room_rent"] or 0) + icu_val

        # Doctor Fees (Checks for 'Doctor' OR 'Surgeon')
        details["doctor_fees"] = self._extract_cost_component(text, r'Doctor.*?Visit.*?₹?\s*([\d,]+)') or \
                                 self._extract_cost_component(text, r'Surgeon.*?Fees.*?₹?\s*([\d,]+)')

        # Medicine Costs
        details["medicine_costs"] = self._extract_cost_component(text, r'Pharmacy.*?₹?\s*([\d,]+)') or \
                                    self._extract_cost_component(text, r'Medicines.*?Consumables.*?₹?\s*([\d,]+)')
        
        # Lab/Investigation Costs
        details["investigation_costs"] = self._extract_cost_component(text, r'Laboratory.*?₹?\s*([\d,]+)') or \
                                         self._extract_cost_component(text, r'Diagnostic.*?Tests.*?₹?\s*([\d,]+)') or \
                                         self._extract_cost_component(text, r'Investigative.*?Tests.*?₹?\s*([\d,]+)')

        # Surgery Costs
        details["surgery_costs"] = self._extract_cost_component(text, r'Surgery.*?₹?\s*([\d,]+)') or \
                                   self._extract_cost_component(text, r'Procedure.*?Charges.*?₹?\s*([\d,]+)') or \
                                   self._extract_cost_component(text, r'OT.*?Charges.*?₹?\s*([\d,]+)')

        return details

    def _extract_procedures(self, text: str) -> List[str]:
        """Extract normalized medical procedures"""
        normalized = []
        text_lower = text.lower()

        procedure_map = {
            'blood test': 'blood_tests',
            'blood smear': 'blood_tests',
            'iv fluids': 'iv_fluids',
            'x-ray': 'x_ray',
            'ultrasound': 'ultrasound',
            'ecg': 'ecg', # --- NEW ---
            'angiography': 'angiography', # --- NEW ---
            'angioplasty': 'angioplasty' # --- NEW ---
        }

        for key, norm in procedure_map.items():
            if key in text_lower:
                normalized.append(norm)

        return list(set(normalized))

    def _extract_medications(self, text: str) -> List[str]:
        """Extract medications with normalized names for consistent validation"""
        normalized = []
        text_lower = text.lower()

        medication_map = {
            'chloroquine': 'antimalarial_drugs',
            'antimalarial': 'antimalarial_drugs',
            'paracetamol': 'antipyretics',
            'antipyretic': 'antipyretics',
            'iv fluids': 'iv_fluids',
            'antibiotic': 'antibiotics',
            'aspirin': 'aspirin', # --- NEW ---
            'clopidogrel': 'clopidogrel', # --- NEW ---
            'statin': 'statins' # --- NEW ---
        }

        for key, norm in medication_map.items():
            if key in text_lower:
                normalized.append(norm)

        return list(set(normalized))

    def _extract_cost_component(self, text: str, full_regex_pattern: str) -> Optional[int]:
        """
        Extracts a cost using a full regex pattern provided by the caller.
        Expected pattern must have one capture group (...) for the number.
        """
        # We use the pattern exactly as provided, trusting the caller defined the capture group
        match = re.search(full_regex_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            # We assume the caller put the number in group 1
            return self._extract_numeric_value(match.group(1))
        return None

    def _determine_claim_type(self, text: str) -> str:
        """Determine claim type from document content"""
        text_lower = text.lower()
        
        if 'cashless' in text_lower or 'pre-authorization' in text_lower:
            return 'cashless'
        elif 'reimbursement' in text_lower or 'bank account' in text_lower:
            return 'reimbursement'
        elif 'accident' in text_lower or 'fir' in text_lower:
            return 'accident'
        else:
            return 'reimbursement'  # Default

    def _extract_numeric_value(self, value_str: str) -> Optional[int]:
        """Extract numeric value from string"""
        if not value_str:
            return None
        try:
            return int(value_str.replace(',', '').replace('₹', '').strip())
        except ValueError:
            return None

    def _convert_date(self, date_str: str) -> str:
        """Convert various date formats to YYYY-MM-DD"""
        if not date_str:
            return None
            
        date_formats = [
            '%d-%m-%Y',    # 05-09-2025
            '%d-%b-%Y',    # 05-Sep-2025
            '%d/%m/%Y',    # 05/09/2025
            '%Y-%m-%d'     # 2025-09-05
        ]

        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str.strip(), fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None  # Return None if no format matches
    