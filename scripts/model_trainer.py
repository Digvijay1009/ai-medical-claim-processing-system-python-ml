# scripts/model_trainer.py - ENHANCED
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb
import pickle
import os
import json
from typing import Dict, List

class EnhancedFraudModelTrainer:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
    
    def prepare_medical_features(self, df):
        """Prepare enhanced features with medical intelligence"""
        features = df.copy()
        
        # Basic feature engineering
        features['claim_amount_log'] = np.log1p(features['total_claim_amount'])
        features['length_of_stay'] = features['treatment_duration']
        features['is_weekend_admission'] = features['weekend_admission']
        
        # MEDICAL INTELLIGENCE FEATURES (NEW)
        features['medical_appropriateness_score'] = features['validation_score']
        features['medical_risk'] = 1 - features['validation_score']  # Convert to risk
        features['cost_appropriateness'] = self._calculate_cost_appropriateness(features)
        features['treatment_duration_ratio'] = self._calculate_duration_ratio(features)
        
        # Diagnosis complexity encoding
        features['diagnosis_complexity'] = features['diagnosis'].apply(self._encode_diagnosis_complexity)
        
        # Room type factor
        features['room_type_factor'] = features['room_type'].apply(self._get_room_type_factor)
        
        # Fraud pattern indicators
        features['has_medical_errors'] = features['medical_errors_count'] > 0
        features['has_fraud_indicators'] = features['fraud_indicators_count'] > 0
        features['high_room_rent'] = features['room_rent'] > features['room_rent_limit'] * 1.5
        
        # Categorical encoding
        categorical_cols = ['diagnosis_category', 'claim_type', 'room_type', 'hospital_tier']
        for col in categorical_cols:
            if col in features.columns:
                self.label_encoders[col] = LabelEncoder()
                features[col] = self.label_encoders[col].fit_transform(features[col].astype(str))
        
        # Select final feature set with medical intelligence
        feature_cols = [
            # Basic features
            'claim_amount_log', 'length_of_stay', 'is_weekend_admission',
            'previous_claims_count', 'patient_age',
            
            # MEDICAL INTELLIGENCE FEATURES (NEW)
            'medical_appropriateness_score', 'medical_risk', 'cost_appropriateness',
            'treatment_duration_ratio', 'diagnosis_complexity', 'room_type_factor',
            'has_medical_errors', 'has_fraud_indicators', 'high_room_rent'
        ]
        
        # Add encoded categorical features
        for col in categorical_cols:
            if col in features.columns:
                feature_cols.append(col)
        
        return features[feature_cols]
    
    def _calculate_cost_appropriateness(self, features):
        """Calculate cost appropriateness score"""
        # This would compare claim amount against disease-specific cost ranges
        # Simplified version for demo
        typical_cost = features['total_claim_amount'].median()
        cost_ratio = features['total_claim_amount'] / typical_cost
        return np.where(cost_ratio > 2, 0.8, np.where(cost_ratio > 1.5, 0.5, 0.2))
    
    def _calculate_duration_ratio(self, features):
        """Calculate treatment duration appropriateness"""
        # Ratio of actual stay vs typical stay for diagnosis
        typical_duration = 7  # Would be diagnosis-specific in real implementation
        duration_ratio = features['treatment_duration'] / typical_duration
        return np.minimum(duration_ratio, 3.0)  # Cap at 3x
    
    def _encode_diagnosis_complexity(self, diagnosis):
        """Encode diagnosis complexity (0=simple, 1=complex)"""
        simple_conditions = ['dengue', 'malaria', 'gastroenteritis', 'uti', 'migraine']
        complex_conditions = ['heart attack', 'stroke', 'cancer', 'major surgery']
        
        diagnosis_lower = str(diagnosis).lower()
        
        for condition in complex_conditions:
            if condition in diagnosis_lower:
                return 1.0
        
        for condition in simple_conditions:
            if condition in diagnosis_lower:
                return 0.3
        
        return 0.5  # Default medium complexity
    
    def _get_room_type_factor(self, room_type):
        """Get cost factor for room type"""
        factors = {
            'general': 1.0,
            'private': 2.0,
            'deluxe': 3.0,
            'executive': 4.0,
            'icu': 5.0
        }
        return factors.get(str(room_type).lower(), 2.0)
    
    def train(self, training_data_path, target_col='is_fraud'):
        """Train the enhanced fraud detection model with medical features"""
        df = pd.read_csv(training_data_path)
        
        print(f"📊 Training with {len(df)} records")
        print(f"🎯 Fraud rate: {df[target_col].mean():.2%}")
        
        # Prepare enhanced features
        X = self.prepare_medical_features(df)
        y = df[target_col]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"🔧 Features used: {list(X.columns)}")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train XGBoost model with medical features
        self.model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=8,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            scale_pos_weight=len(y_train[y_train==0])/len(y_train[y_train==1])
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Enhanced evaluation
        y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
        y_pred = self.model.predict(X_test_scaled)
        
        print("\n" + "="*50)
        print("🤖 ENHANCED MODEL PERFORMANCE (with Medical Intelligence)")
        print("="*50)
        print(f"📈 ROC-AUC: {roc_auc_score(y_test, y_pred_proba):.4f}")
        print(f"🎯 Fraud Detection Rate: {confusion_matrix(y_test, y_pred)[1, 1] / y_test.sum():.2%}")
        print("\n📋 Classification Report:")
        print(classification_report(y_test, y_pred))
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n🔍 Top 10 Feature Importances:")
        print(feature_importance.head(10))
        
        return self.model
    
    def save_model(self, model_path):
        """Save trained model and preprocessors"""
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders,
            'training_timestamp': pd.Timestamp.now().isoformat(),
            'model_type': 'Enhanced XGBoost with Medical Intelligence'
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"💾 Model saved: {model_path}")
    
    def load_model(self, model_path):
        """Load trained model and preprocessors"""
        if not os.path.exists(model_path):
            print(f"❌ Model file not found: {model_path}")
            return None
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.label_encoders = model_data['label_encoders']
        
        print(f"✅ Model loaded: {model_path}")
        return self.model

# Usage example:
def train_enhanced_model():
    """Train the enhanced model with medical features"""
    trainer = EnhancedFraudModelTrainer()
    
    # Train on collected data
    model = trainer.train('data/enhanced_training_data.csv')
    
    # Save the model
    trainer.save_model('models/enhanced_xgb_fraud_model.pkl')
    
    return trainer

if __name__ == "__main__":
    train_enhanced_model()