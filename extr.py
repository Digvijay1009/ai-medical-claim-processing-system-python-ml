# debug_llm_extraction.py
import sys
import os
sys.path.append('scripts')

from ai_validator import AIValidator

def debug_llm_extraction():
    # Use the exact extracted text you provided
    consolidated_text = """
--- NEW DOCUMENT: claim form.pdf ---

--- Page 1 ---
Health Insurance Claim Form (Reimbursement)
To be filled by the policyholder after hospital discharge.
SECTION A: POLICYHOLDER & PATIENT DETAILS
Policy Number:
HWP-2023-987654
TPA ID Number (if any):
Name of Policyholder:
Rohan Sharma
Full Name of Patient:
Rohan Sharma
Relationship to Policyholder:
Self
Contact Number:
9876543210
Email Address:
rohan.sharma@example.com
SECTION B: DETAILS IN CASE OF AN ACCIDENT
Was hospitalization due to an
accident?
SECTION C: HOSPITALIZATION DETAILS
Name of Hospital:
City Central Hospital, Mumbai
Hospital Address:
456, Health Avenue, Dadar, Mumbai
Hospital ID / Reg. No.:
HOS-MH-5678
Diagnosis / Illness:
Acute Pyelonephritis with Sepsis
Date of Admission:
05-09-2025
Date of Discharge:
15-09-2025
--- Page 2 ---
SECTION D: CLAIM DETAILS
Hospital Bills (Room, ICU, OT,
etc.)
₹ 210,000
Medicine Bills
₹ 65,000
Doctor's Fees
₹ 30,000
Investigation Bills
₹ 10,000
TOTAL CLAIMED AMOUNT
₹ 315,000
SECTION E: CLAIMANT'S BANK ACCOUNT DETAILS
Account Holder's Name:
Rohan Sharma
Bank Name & Branch:
HDFC Bank, Dadar Branch
Account Number:
0987654321098
IFSC Code:
HDFC0000123
I hereby declare that the information furnished in this claim form is true & correct to
the best of my knowledge and belief. I also consent to the insurance company
seeking medical information from any hospital/doctor who has attended to me. I
agree that if I have provided any false information, my claim shall be void.
Signature of Policyholder
Page 1 of 2
Page 2 of 2

--- NEW DOCUMENT: hospital bill.pdf ---

--- Page 1 ---
City Central Hospital, Mumbai
FINAL BILL
Patient Name: Rohan Sharma
Date of Admission: 05-Sep-2025
Date of Discharge: 15-Sep-2025
Diagnosis: Acute Pyelonephritis with Sepsis
Description of Charges
Amount (INR)
ICU Charges (3 Days)
90,000.00
Private Room Charges (7 Days)
70,000.00
Intensive Care Specialist Fees
30,000.00
Pharmacy & Consumables
65,000.00
Pathology & Radiology Investigations
10,000.00
Nursing & Procedure Charges
50,000.00
Total Bill Amount: ₹ 3,15,000.00

--- NEW DOCUMENT: medical bill for reimbressment.pdf ---

--- Page 1 ---
Subtotal:
₹ 61,904.76
GST @ 5%:
₹ 3,095.24
Grand Total:
₹ 65,000.00
City Central Hospital Pharmacy
In-Patient Pharmacy Bill
GSTIN: 27AAAAA0000A1Z5
Patient Name: Rohan Sharma
Hospitalization Period: 05-Sep-2025 to 15-Sep-2025
Bill Number: PH-2025-5432
Medicine / Item
Quantity
Rate (INR)
Amount (INR)
Inj. Meropenem 1gm
1,711.49
51,344.70
IV Fluids (NS/DNS) & Admin Sets
238.10
4,762.00
Inj. Paracetamol 100ml
190.48
2,857.20
Other Supportive Drugs & Consumables
L.S.
2,940.86

--- NEW DOCUMENT: policycopy.pdf ---

--- Page 1 ---
Health Wellness Plus - Policy Schedule
Your guide to a secured health journey.
Policy Details
Policy Number:
HWP-2023-987654
Policy Period:
01-Sep-2024 to 31-Aug-2025 (Policy Expired)
Sum Insured:
₹ 5,00,000 (Five Lakh Rupees)
Plan Type:
Individual
Insured Person Details
Name:
Rohan Sharma
Date of Birth:
15-Jun-1985
Address:
123, Harmony Apartments, Dadar, Mumbai
"""

    print("🧪 Testing LLM Extraction with Your Exact Text...")
    validator = AIValidator()
    
    print("🔍 Calling LLM...")
    extracted_data = validator.validate_and_extract_with_llm(consolidated_text)
    
    print(f"\n📊 LLM EXTRACTION RESULT:")
    print("=" * 60)
    for key, value in extracted_data.items():
        print(f"  {key}: {repr(value)}")
    print("=" * 60)
    
    # Check what's causing the error
    if extracted_data.get('total_claim_amount') is None:
        print("\n❌ PROBLEM: total_claim_amount is None!")
        print("💡 This will cause: '>' not supported between instances of 'NoneType' and 'int'")
    else:
        print(f"\n✅ total_claim_amount is: {extracted_data['total_claim_amount']} (type: {type(extracted_data['total_claim_amount'])})")
    
    return extracted_data

if __name__ == "__main__":
    debug_llm_extraction()