# generating synthetic data for model training

import pandas as pd
import numpy as np
import random
import os
import sys
from datetime import datetime, timedelta

# ✅ Add project root to path so we can import the knowledge base
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
sys.path.append(ROOT_DIR)

# ✅ Import your "Single Source of Truth"
from app.scripts.disease_knowledge_base import DiseaseKnowledgeBase

# -------------------------------
# GLOBAL SETTINGS
# -------------------------------
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

OUTPUT_DIR = "data"
OUTPUT_FILE = "enhanced_training_data.csv"

# -------------------------------
# CONFIGURATION
# -------------------------------
ROOM_MULTIPLIER = {
    "general": 1.0,  # Normalized to 1.0 based on your KB
    "semi_private": 1.3,
    "private": 1.5,
    "deluxe": 2.0,
    "icu": 2.5,
}

HOSPITAL_RISK = {
    "Tier 1": 0.05,
    "Tier 2": 0.10,
    "Tier 3": 0.18,
}

def generate_synthetic_data(num_samples=2000, fraud_rate=0.18):
    print(f"🧪 Initializing Medical Knowledge Base...")
    kb = DiseaseKnowledgeBase()
    
    # Get the list of all disease keys (e.g., 'dengue_fever', 'heart_attack')
    disease_keys = list(kb.diseases.keys())
    
    print(f"🧬 Generating {num_samples} synthetic claims based on {len(disease_keys)} diseases...")

    records = []
    start_date = datetime(2024, 1, 1)

    for i in range(num_samples):
        # 1. Pick a random disease from YOUR Knowledge Base
        disease_key = random.choice(disease_keys)
        disease_info = kb.diseases[disease_key]
        
        # 2. Extract Real Rules from KB
        disease_name = disease_info['name']
        min_stay, max_stay = disease_info['typical_duration']
        min_cost, max_cost = disease_info['cost_range']
        max_reasonable = disease_info['max_reasonable']
        required_room = disease_info['room_type'] # e.g., 'icu' or 'general'

        # 3. Select Hospital & Room Details
        hospital_tier = random.choice(list(HOSPITAL_RISK.keys()))
        
        # If disease requires ICU, force ICU or higher, otherwise random
        if required_room == 'icu':
            room_type = 'icu'
        else:
            # Weighted random choice favoring the required room type
            room_options = list(ROOM_MULTIPLIER.keys())
            room_type = random.choice(room_options)

        # 4. Generate Base Metrics
        base_cost = random.randint(min_cost, max_cost)
        base_stay = random.randint(min_stay, max_stay)
        
        # Apply Multipliers
        room_factor = ROOM_MULTIPLIER.get(room_type, 1.0)
        hospital_bias = HOSPITAL_RISK[hospital_tier]

        # 5. Dates
        admission_date = start_date + timedelta(days=random.randint(0, 365))
        discharge_date = admission_date + timedelta(days=base_stay)
        claim_delay_days = random.randint(3, 45)

        # 6. Fraud Logic (Probabilistic)
        fraud_probability = fraud_rate + hospital_bias
        is_fraud = 1 if random.random() < fraud_probability else 0

        # 7. Financial Calculations
        inflation_factor = 1.0
        unnecessary_stay = 0
        validation_score = random.uniform(0.85, 0.98) # High score by default

        if is_fraud:
            fraud_pattern = random.choice(["inflation", "extended_stay", "soft_abuse"])

            if fraud_pattern == "inflation":
                # Bill significantly higher than max_reasonable
                inflation_factor = random.uniform(1.5, 2.5)
                validation_score -= random.uniform(0.15, 0.35)

            elif fraud_pattern == "extended_stay":
                # Stay 3-7 days longer than max_stay
                unnecessary_stay = random.randint(3, 7)
                validation_score -= random.uniform(0.1, 0.2)

            else:  # soft abuse
                inflation_factor = random.uniform(1.1, 1.3)
                validation_score -= random.uniform(0.05, 0.1)

        total_stay = base_stay + unnecessary_stay
        
        # Calculate final amount
        # Formula: Base Cost * Room Factor * Fraud Inflation
        total_claim_amount = base_cost * room_factor * inflation_factor

        # Add some noise (random variance)
        total_claim_amount *= random.uniform(0.95, 1.05)

        # 8. Risk Indicators (Derived)
        fraud_indicators_count = int((1 - validation_score) * 10)
        if is_fraud:
            fraud_indicators_count = max(1, fraud_indicators_count)
            medical_errors_count = random.randint(1, 3)
        else:
            fraud_indicators_count = 0
            medical_errors_count = 0
            
        # 9. Room Rent Calculation (for Model Trainer)
        # Assume 15-25% of the bill is room rent
        room_rent = total_claim_amount * random.uniform(0.15, 0.25)
        room_rent_limit = 5000 if room_type in ['general', 'semi_private'] else 10000

        # 10. Construct Record
        records.append({
            "claim_id": f"SYN_{i:05d}",
            "diagnosis": disease_name,  # Using the clean name from KB
            "room_type": room_type.title(),
            "hospital_tier": hospital_tier,
            "patient_age": random.randint(25, 80),
            "previous_claims_count": random.randint(0, 6),
            "weekend_admission": int(admission_date.weekday() >= 5),

            # Dates
            "admission_date": admission_date,
            "discharge_date": discharge_date + timedelta(days=unnecessary_stay),
            "claim_delay_days": claim_delay_days,
            
            # Key Columns required by Model Trainer
            "total_claim_amount": round(total_claim_amount, 2),
            "treatment_duration": total_stay,
            "validation_score": round(validation_score, 2),
            "fraud_score": round(1 - validation_score, 2), 
            "overall_risk_score": round(1 - validation_score, 2),
            "room_rent": round(room_rent, 2),
            "room_rent_limit": room_rent_limit,
            "claim_type": "Reimbursement",

            # Quality & risk signals
            "fraud_indicators_count": fraud_indicators_count,
            "medical_errors_count": medical_errors_count,

            # Target
            "is_fraud": is_fraud,
        })

    df = pd.DataFrame(records)

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    df.to_csv(output_path, index=False)

    print(f"✅ Generated {len(df)} records using 'DiseaseKnowledgeBase' logic.")
    print(f"📂 Saved to: {output_path}")
    print(f"📊 Fraud Rate: {df['is_fraud'].mean():.2%}")

    return df

if __name__ == "__main__":
    generate_synthetic_data()