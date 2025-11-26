# scripts/data_collector.py - ENHANCED
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List
import os

class EnhancedTrainingDataCollector:
    def __init__(self, db_handler):
        self.db_handler = db_handler
    
    def collect_enhanced_training_data(self, output_path: str):
        """Collect enhanced training data with medical validation features"""
        claims = self.db_handler.get_all_claims()
        
        training_data = []
        for claim in claims:
            # Only use claims that have been reviewed (have human decisions)
            if claim['status'] in ['Approved', 'Denied', 'Fraud Suspected']:
                features = self._extract_enhanced_features(claim)
                
                # Label based on human decisions
                if claim['status'] == 'Approved':
                    features['is_fraud'] = 0
                else:  # Denied or Fraud Suspected
                    features['is_fraud'] = 1
                
                features['claim_id'] = claim['claim_id']
                features['reviewer_decision'] = claim['status']
                features['review_comments'] = claim.get('review_comments', '')
                
                training_data.append(features)
        
        if training_data:
            df = pd.DataFrame(training_data)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"✅ Enhanced training data saved: {output_path}")
            print(f"📊 Records: {len(df)} | Fraud rate: {df['is_fraud'].mean():.2%}")
            
            # Data quality report
            self._generate_data_quality_report(df)
        else:
            print("❌ No training data available. Process and review some claims first.")
        
        return df
    
    def _extract_enhanced_features(self, claim: Dict) -> Dict:
        """Extract enhanced features including medical validation data"""
        features = {}
        
        # BASIC FEATURES
        features['total_claim_amount'] = claim.get('total_claim_amount', 0)
        features['fraud_score'] = claim.get('fraud_score', 0)
        features['validation_score'] = claim.get('validation_score', 1.0)
        features['overall_risk_score'] = claim.get('overall_risk_score', 0.0)
        
        # TEMPORAL FEATURES
        admission_date = claim.get('admission_date')
        discharge_date = claim.get('discharge_date')
        features['treatment_duration'] = self._calculate_length_of_stay(admission_date, discharge_date)
        features['weekend_admission'] = self._is_weekend_admission(admission_date)
        
        # CLAIM TYPE FEATURES
        features['claim_type'] = claim.get('claim_type', 'unknown')
        
        # MEDICAL VALIDATION FEATURES (NEW)
        medical_validation = claim.get('medical_validation_result', {})
        features['medical_appropriateness_score'] = medical_validation.get('appropriateness_score', 1.0)
        features['diagnosis'] = medical_validation.get('disease_identified', 'Unknown')
        features['is_medically_appropriate'] = medical_validation.get('is_medically_appropriate', True)
        
        # Count medical issues
        medical_errors = medical_validation.get('medical_errors', [])
        medical_warnings = medical_validation.get('medical_warnings', [])
        features['medical_errors_count'] = len(medical_errors)
        features['medical_warnings_count'] = len(medical_warnings)
        
        # FRAUD INDICATORS (NEW)
        fraud_indicators = claim.get('fraud_indicators', [])
        features['fraud_indicators_count'] = len(fraud_indicators)
        
        # FINANCIAL FEATURES
        extracted_data = claim.get('extracted_json', {})
        features['room_rent'] = extracted_data.get('room_rent', 0)
        features['room_rent_limit'] = extracted_data.get('room_rent_limit', 5000)
        features['doctor_fees'] = extracted_data.get('doctor_fees', 0)
        features['medicine_costs'] = extracted_data.get('medicine_costs', 0)
        
        # ROOM TYPE FEATURES (NEW)
        features['room_type'] = extracted_data.get('room_type', 'general')
        
        # PATIENT DEMOGRAPHICS (would come from external data in real system)
        features['patient_age'] = 45  # Default - would be extracted from patient data
        features['previous_claims_count'] = 0  # Would come from historical data
        
        # HOSPITAL FEATURES (would come from external data)
        features['hospital_tier'] = 'tier_2'  # Default
        features['provider_fraud_history'] = 0  # Would come from provider database
        
        return features
    
    def _calculate_length_of_stay(self, admission_date: str, discharge_date: str) -> int:
        """Calculate hospitalization duration"""
        try:
            if admission_date and discharge_date:
                admission = datetime.strptime(admission_date, '%Y-%m-%d')
                discharge = datetime.strptime(discharge_date, '%Y-%m-%d')
                return max(0, (discharge - admission).days)
        except:
            pass
        return 0
    
    def _is_weekend_admission(self, admission_date: str) -> bool:
        """Check if admission was on weekend"""
        try:
            if admission_date:
                admission = datetime.strptime(admission_date, '%Y-%m-%d')
                return admission.weekday() >= 5
        except:
            pass
        return False
    
    def _generate_data_quality_report(self, df: pd.DataFrame):
        """Generate data quality report"""
        print("\n" + "="*50)
        print("📋 ENHANCED TRAINING DATA QUALITY REPORT")
        print("="*50)
        print(f"Total records: {len(df)}")
        print(f"Fraud cases: {df['is_fraud'].sum()} ({df['is_fraud'].mean():.2%})")
        print(f"Features available: {len(df.columns)}")
        
        # Check for missing values
        missing_data = df.isnull().sum()
        if missing_data.sum() > 0:
            print("\n⚠️ Missing values:")
            for col, missing_count in missing_data[missing_data > 0].items():
                print(f"  {col}: {missing_count} ({missing_count/len(df):.1%})")
        
        # Feature ranges
        print("\n📊 Key feature ranges:")
        numeric_features = df.select_dtypes(include=[np.number]).columns
        for feature in ['total_claim_amount', 'fraud_score', 'validation_score', 'treatment_duration']:
            if feature in df.columns:
                print(f"  {feature}: {df[feature].min():.0f} - {df[feature].max():.0f} (mean: {df[feature].mean():.1f})")
    
    def create_sample_training_data(self, output_path: str):
        """Create sample training data for demonstration"""
        sample_data = []
        
        # Sample claims representing different patterns
        sample_patterns = [
            # Legitimate claims
            {'total_claim_amount': 45000, 'treatment_duration': 5, 'validation_score': 0.9, 'fraud_score': 0.1, 'is_fraud': 0},
            {'total_claim_amount': 120000, 'treatment_duration': 8, 'validation_score': 0.8, 'fraud_score': 0.2, 'is_fraud': 0},
            
            # Fraudulent claims
            {'total_claim_amount': 250000, 'treatment_duration': 15, 'validation_score': 0.3, 'fraud_score': 0.8, 'is_fraud': 1},
            {'total_claim_amount': 80000, 'treatment_duration': 2, 'validation_score': 0.4, 'fraud_score': 0.7, 'is_fraud': 1},
            
            # Borderline cases
            {'total_claim_amount': 95000, 'treatment_duration': 10, 'validation_score': 0.6, 'fraud_score': 0.5, 'is_fraud': 0},
            {'total_claim_amount': 60000, 'treatment_duration': 4, 'validation_score': 0.7, 'fraud_score': 0.4, 'is_fraud': 1},
        ]
        
        for i, pattern in enumerate(sample_patterns):
            features = {
                'claim_id': f'SAMPLE_{i+1}',
                'total_claim_amount': pattern['total_claim_amount'],
                'fraud_score': pattern['fraud_score'],
                'validation_score': pattern['validation_score'],
                'treatment_duration': pattern['treatment_duration'],
                'weekend_admission': 0,
                'claim_type': 'reimbursement',
                'medical_appropriateness_score': pattern['validation_score'],
                'diagnosis': 'dengue_fever',
                'is_medically_appropriate': pattern['validation_score'] > 0.6,
                'medical_errors_count': 0 if pattern['validation_score'] > 0.7 else 2,
                'medical_warnings_count': 0 if pattern['validation_score'] > 0.8 else 1,
                'fraud_indicators_count': 0 if pattern['fraud_score'] < 0.4 else 2,
                'room_rent': 20000,
                'room_rent_limit': 5000,
                'doctor_fees': 15000,
                'medicine_costs': 10000,
                'room_type': 'general',
                'patient_age': 45,
                'previous_claims_count': 0,
                'hospital_tier': 'tier_2',
                'provider_fraud_history': 0,
                'is_fraud': pattern['is_fraud'],
                'reviewer_decision': 'Approved' if pattern['is_fraud'] == 0 else 'Denied'
            }
            sample_data.append(features)
        
        df = pd.DataFrame(sample_data)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✅ Sample training data created: {output_path}")
        return df

# Usage examples:
def collect_training_data():
    """Collect training data from database"""
    from scripts.db_handler import DatabaseHandler
    
    db_handler = DatabaseHandler()
    collector = EnhancedTrainingDataCollector(db_handler)
    
    # Collect real data from database
    df = collector.collect_enhanced_training_data('data/enhanced_training_data.csv')
    
    # If no data available, create sample data
    if df.empty:
        print("🔄 No reviewed claims found. Creating sample data for demonstration...")
        df = collector.create_sample_training_data('data/sample_training_data.csv')
    
    return df

if __name__ == "__main__":
    collect_training_data()