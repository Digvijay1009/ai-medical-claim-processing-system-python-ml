# scripts/db_handler.py

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

class DatabaseHandler:
    def __init__(self, db_path: str = "database/claims.db"):
        self.db_path = db_path
        self.initialize_db()

    def _get_connection(self):
        """
        Creates a thread-safe SQLite connection.
        """
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def initialize_db(self):
        """Create enhanced claims tables and add missing columns if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Enhanced main claims table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    policy_number TEXT,
                    patient_name TEXT,
                    admission_date TEXT,
                    discharge_date TEXT,
                    total_claim_amount REAL,
                    claim_type TEXT CHECK(claim_type IN ('cashless', 'reimbursement', 'accident')),
                    hospital_name TEXT,
                    diagnosis TEXT,
                    treating_doctor TEXT,
                    
                    -- Enhanced Analysis Fields
                    fraud_score REAL,
                    validation_score REAL,
                    medical_appropriateness_score REAL,
                    overall_risk_score REAL,
                    
                    analysis_reason TEXT,
                    fraud_reason TEXT,
                    medical_validation_result TEXT, -- Old field, kept for compatibility
                    
                    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Denied', 'More Info Needed', 'Fraud Suspected', 'Under Review')),
                    reviewer_name TEXT,
                    review_comments TEXT,
                    
                    -- Timestamps
                    created_at TEXT,
                    updated_at TEXT,
                    
                    -- Document Data
                    consolidated_text TEXT,
                    extracted_json TEXT, -- Old field, kept for compatibility
                    associated_files TEXT,
                    
                    -- Validation Details
                    validation_errors TEXT,
                    medical_warnings TEXT,
                    fraud_indicators TEXT
                )
            ''')
            
            # --- FIX: Add all missing flat columns non-destructively ---
            self._add_missing_columns(cursor)
            
            # Claim documents table (no changes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS claim_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT,
                    document_type TEXT CHECK(document_type IN (
                        'policy', 'hospital_bill', 'medical_bill', 'discharge_summary', 
                        'claim_form', 'fir', 'pre_authorization', 'investigation_report', 'other'
                    )),
                    file_name TEXT,
                    file_path TEXT,
                    extracted_data TEXT,
                    upload_date TEXT,
                    FOREIGN KEY (claim_id) REFERENCES claims (claim_id) ON DELETE CASCADE
                )
            ''')
            
            # Validation rules table (no changes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validation_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT UNIQUE,
                    rule_description TEXT,
                    rule_condition TEXT,
                    rule_type TEXT CHECK(rule_type IN ('medical', 'financial', 'document', 'policy')),
                    severity TEXT CHECK(severity IN ('error', 'warning', 'info')),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            # Disease guidelines table (no changes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disease_guidelines (
                    disease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disease_name TEXT UNIQUE,
                    disease_category TEXT,
                    typical_duration_min INTEGER,
                    typical_duration_max INTEGER,
                    cost_range_min REAL,
                    cost_range_max REAL,
                    max_reasonable_amount REAL,
                    room_type TEXT,
                    icu_required BOOLEAN DEFAULT 0,
                    surgery_required BOOLEAN DEFAULT 0,
                    required_treatments TEXT,
                    unnecessary_treatments TEXT,
                    common_medications TEXT,
                    red_flags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            self._insert_default_validation_rules(cursor)
            self._insert_default_disease_guidelines(cursor)
            
            conn.commit()
            print("✅ Enhanced database schema initialized")
        
        except Exception as e:
            print(f"❌ Error during DB initialization: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _add_missing_columns(self, cursor):
        """
        Adds all new flat columns to the claims table
        if they don't already exist.
        """
        columns_to_add = {
            # Financial Extraction
            "room_rent": "REAL",
            "doctor_fees": "REAL",
            "medicine_costs": "REAL",
            "investigation_costs": "REAL",
            "surgery_costs": "REAL",
            "sum_insured": "REAL",
            
            # Medical Extraction
            "treatment_duration": "INTEGER",
            "room_type": "TEXT",
            "procedures": "TEXT",
            "medications": "TEXT",

            # Medical Analysis
            "is_medically_appropriate": "BOOLEAN",
            "disease_identified": "TEXT",
            "medical_errors": "TEXT",
            
            # Cost Analysis
            "cost_analysis_within_guidelines": "BOOLEAN",
            "cost_analysis_typical_range": "TEXT",
            "cost_analysis_max_reasonable": "TEXT",
            
            # Policy Analysis
            "policy_status": "TEXT",
            "policy_exclusions": "TEXT",
            "policy_limits_exceeded": "TEXT",
            "policy_waiting_period_issues": "TEXT",
            
            # Final Decision
            "approved_amount": "REAL",
            "co_pay_amount": "REAL",
            "patient_responsibility": "REAL",
            "rejection_reason": "TEXT",
            "reviewed_by": "TEXT",
            "reviewed_at": "TEXT",
            "fraud_reason": "TEXT"
        }
        
        for column_name, column_type in columns_to_add.items():
            try:
                cursor.execute(f"ALTER TABLE claims ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    pass # Column already exists, which is fine
                else:
                    raise e # Raise other errors

    def _insert_default_validation_rules(self, cursor):
        """Insert default validation rules"""
        default_rules = [
            ('room_rent_limit', 'Room rent exceeds policy limit', 
             'room_rent > room_rent_limit', 'policy', 'error'),
            ('network_hospital', 'Treatment in non-network hospital for cashless', 
             'claim_type = "cashless" AND hospital_not_in_network', 'policy', 'error'),
            ('pre_auth_required', 'Pre-authorization missing for high amount', 
             'total_claim_amount > 50000 AND pre_authorization_missing', 'document', 'error'),
            ('fir_required', 'FIR missing for accident claim', 
             'claim_type = "accident" AND fir_missing', 'document', 'error'),
            ('extended_stay', 'Hospitalization longer than typical', 
             'treatment_duration > typical_max_duration * 1.3', 'medical', 'warning'),
            ('cost_inflation', 'Claim amount exceeds reasonable limits', 
             'total_claim_amount > max_reasonable_amount', 'financial', 'error'),
            ('unnecessary_procedures', 'Medically unnecessary procedures', 
             'unnecessary_treatments_present', 'medical', 'warning')
        ]
        
        current_time = datetime.now().isoformat()
        
        for rule_name, description, condition, rule_type, severity in default_rules:
            cursor.execute('''
                INSERT OR IGNORE INTO validation_rules 
                (rule_name, rule_description, rule_condition, rule_type, severity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (rule_name, description, condition, rule_type, severity, current_time, current_time))

    def _insert_default_disease_guidelines(self, cursor):
        """Insert default disease guidelines"""
        diseases = [
            ('Dengue Fever', 'infectious', 3, 7, 15000, 50000, 80000, 'general', 0, 0,
             '["iv_fluids", "blood_tests", "platelet_monitoring"]',
             '["antibiotics", "mri", "ct_scan"]',
             '["paracetamol", "iv_fluids"]',
             '["antibiotics_prescribed", "extended_stay", "icu_admission"]'),
            
            ('Malaria', 'infectious', 3, 7, 12000, 40000, 60000, 'general', 0, 0,
             '["antimalarial_drugs", "blood_tests"]',
             '["surgery", "mri"]',
             '["chloroquine", "artemisinin"]',
             '["surgery_billed", "extended_stay"]'),
            
            ('Heart Attack', 'cardiac', 5, 14, 150000, 500000, 600000, 'icu', 1, 1,
             '["ecg", "angiography", "troponin_test"]',
             '[]',
             '["aspirin", "clopidogrel", "statins"]',
             '["no_angiography", "short_stay", "low_cost"]'),
            
            ('Pneumonia', 'respiratory', 5, 10, 25000, 70000, 100000, 'general', 0, 0,
             '["chest_xray", "antibiotics", "iv_fluids"]',
             '["bronchoscopy", "ct_scan"]',
             '["antibiotics", "bronchodilators"]',
             '["no_antibiotics", "surgery_billed"]')
        ]
        
        current_time = datetime.now().isoformat()
        
        for disease in diseases:
            cursor.execute('''
                INSERT OR IGNORE INTO disease_guidelines 
                (disease_name, disease_category, typical_duration_min, typical_duration_max,
                 cost_range_min, cost_range_max, max_reasonable_amount, room_type, icu_required,
                 surgery_required, required_treatments, unnecessary_treatments, common_medications,
                 red_flags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*disease, current_time, current_time))

    def insert_claim(self, claim_data: Dict):
        """
        Insert a new processed claim record dynamically.
        This will save any key from claim_data that matches a column name.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get the list of actual columns from the claims table
            cursor.execute("PRAGMA table_info(claims)")
            table_columns = {row[1] for row in cursor.fetchall()}

            # Prepare data for insertion
            data_to_insert = claim_data.copy()
            
            # --- FIX: Removing old nested fields, they are flat now ---
            if 'extracted_json' in data_to_insert:
                del data_to_insert['extracted_json']
            if 'medical_validation_result' in data_to_insert:
                del data_to_insert['medical_validation_result']
            
            # Handle status mapping
            status_value = data_to_insert.get('status', 'Pending')
            if str(status_value).upper() in ('UNDER_REVIEW', 'IN_REVIEW', 'REVIEW'):
                data_to_insert['status'] = 'Under Review'
            
            # Set update timestamp
            data_to_insert['updated_at'] = datetime.now().isoformat()
            if 'created_at' not in data_to_insert:
                 data_to_insert['created_at'] = data_to_insert['updated_at']

            # Build the query dynamically
            cols = []
            vals = []
            placeholders = []
            
            for key, value in data_to_insert.items():
                if key in table_columns:
                    cols.append(key)
                    placeholders.append('?')
                    
                    # Convert lists/dicts to JSON strings for TEXT columns
                    if isinstance(value, (dict, list)):
                        vals.append(json.dumps(value))
                    else:
                        vals.append(value)

            if 'claim_id' not in cols:
                raise ValueError("claim_id is missing from the data to be inserted.")

            sql = f"INSERT INTO claims ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            
            cursor.execute(sql, tuple(vals))
            conn.commit()
        
        except Exception as e:
            print(f"❌ Error in insert_claim: {e}")
            print(f"Failing data (first 500 chars): {str(claim_data)[:500]}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_claim_status(self, claim_id: str, status: str, 
                            reviewer_name: str = None, review_comments: str = None):
        """Update the status of an existing claim"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if str(status).upper() in ('UNDER_REVIEW', 'IN_REVIEW', 'REVIEW'):
                status = 'Under Review'

            cursor.execute('''
                UPDATE claims 
                SET status = ?, reviewer_name = ?, review_comments = ?, updated_at = ?
                WHERE claim_id = ?
            ''', (status, reviewer_name, review_comments, datetime.now().isoformat(), claim_id))
            
            conn.commit()
        except Exception as e:
            print(f"❌ Error in update_claim_status: {e}")
            conn.rollback()
        finally:
            conn.close()

    def update_claim_analysis(self, claim_id: str, analysis_data: Dict):
        """
        Update analysis results for a claim.
        --- NOTE: This is an old function. For the new pipeline, 
        it's better to update fields individually or re-run the claim.
        This function is kept for backward compatibility but is less efficient. ---
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Build SET clause dynamically
            set_clauses = []
            values = []
            
            for key, value in analysis_data.items():
                set_clauses.append(f"{key} = ?")
                if isinstance(value, (dict, list)):
                    values.append(json.dumps(value))
                else:
                    values.append(value)
            
            if not set_clauses:
                return # Nothing to update
                
            # Add updated_at
            set_clauses.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            
            # Add claim_id for WHERE
            values.append(claim_id)
            
            sql = f"UPDATE claims SET {', '.join(set_clauses)} WHERE claim_id = ?"
            
            cursor.execute(sql, tuple(values))
            conn.commit()
        except Exception as e:
            print(f"❌ Error in update_claim_analysis: {e}")
            conn.rollback()
        finally:
            conn.close()

    def add_claim_document(self, claim_id: str, document_type: str, 
                           file_name: str, file_path: str, extracted_data: Dict = None):
        """Add a document record for a claim"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO claim_documents 
                (claim_id, document_type, file_name, file_path, extracted_data, upload_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                claim_id,
                document_type,
                file_name,
                file_path,
                json.dumps(extracted_data) if extracted_data else None,
                datetime.now().isoformat()
            ))
            
            conn.commit()
        except Exception as e:
            print(f"❌ Error in add_claim_document: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_claim_documents(self, claim_id: str) -> List[Dict]:
        """Get all documents for a claim"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM claim_documents WHERE claim_id = ? ORDER BY upload_date
            ''', (claim_id,))
            
            documents = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                doc = dict(zip(columns, row))
                try:
                    doc['extracted_data'] = json.loads(doc['extracted_data']) if doc['extracted_data'] else {}
                except:
                    doc['extracted_data'] = {}
                documents.append(doc)
            
            return documents
        finally:
            conn.close()

    def get_all_claims(self) -> List[Dict]:
        """Fetch all claim records with enhanced fields"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM claims ORDER BY created_at DESC')
            columns = [column[0] for column in cursor.description]
            claims = []
            
            for row in cursor.fetchall():
                claim = dict(zip(columns, row))
                claim = self._parse_json_fields(claim)
                claims.append(claim)
            
            return claims
        finally:
            conn.close()

    def get_claim_by_id(self, claim_id: str) -> Optional[Dict]:
        """Fetch a specific claim by ID with all enhanced data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM claims WHERE claim_id = ?', (claim_id,))
            row = cursor.fetchone()
            
            if row:
                columns = [column[0] for column in cursor.description]
                claim = dict(zip(columns, row))
                claim = self._parse_json_fields(claim)
                
                claim['documents'] = self.get_claim_documents(claim_id)
                
                return claim
            
            return None
        finally:
            conn.close()

    def get_claims_by_status(self, status: str) -> List[Dict]:
        """Get claims by status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if str(status).upper() in ('UNDER_REVIEW', 'IN_REVIEW', 'REVIEW'):
                status = 'Under Review'
                
            cursor.execute('SELECT * FROM claims WHERE status = ? ORDER BY created_at DESC', (status,))
            columns = [column[0] for column in cursor.description]
            claims = []
            
            for row in cursor.fetchall():
                claim = dict(zip(columns, row))
                claim = self._parse_json_fields(claim)
                claims.append(claim)
            
            return claims
        finally:
            conn.close()

    def get_high_risk_claims(self, risk_threshold: float = 0.6) -> List[Dict]:
        """Get claims with high risk scores"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM claims 
                WHERE overall_risk_score >= ? OR fraud_score >= ?
                ORDER BY overall_risk_score DESC
            ''', (risk_threshold, risk_threshold))
            
            columns = [column[0] for column in cursor.description]
            claims = []
            
            for row in cursor.fetchall():
                claim = dict(zip(columns, row))
                claim = self._parse_json_fields(claim)
                claims.append(claim)
            
            return claims
        finally:
            conn.close()

    def get_validation_rules(self, rule_type: str = None) -> List[Dict]:
        """Get validation rules"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if rule_type:
                cursor.execute('SELECT * FROM validation_rules WHERE rule_type = ? AND is_active = 1', (rule_type,))
            else:
                cursor.execute('SELECT * FROM validation_rules WHERE is_active = 1')
            
            rules = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                rules.append(dict(zip(columns, row)))
            
            return rules
        finally:
            conn.close()

    def get_disease_guidelines(self, disease_name: str = None) -> List[Dict]:
        """Get disease guidelines"""
        conn = self_get_connection()
        cursor = conn.cursor()
        
        try:
            if disease_name:
                cursor.execute('SELECT * FROM disease_guidelines WHERE disease_name = ?', (disease_name,))
            else:
                cursor.execute('SELECT * FROM disease_guidelines')
            
            guidelines = []
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                guideline = dict(zip(columns, row))
                for field in ['required_treatments', 'unnecessary_treatments', 'common_medications', 'red_flags']:
                    try:
                        guideline[field] = json.loads(guideline[field]) if guideline[field] else []
                    except:
                        guideline[field] = []
                guidelines.append(guideline)
            
            return guidelines
        finally:
            conn.close()

    def _parse_json_fields(self, claim: Dict) -> Dict:
        """Parse JSON fields in claim data"""
        # --- FIX: Added new list-based fields ---
        json_fields = [
            'extracted_json', 'associated_files', 'validation_errors',
            'medical_warnings', 'fraud_indicators', 'medical_validation_result',
            'procedures', 'medications', 'medical_errors',
            'policy_exclusions', 'policy_limits_exceeded', 'policy_waiting_period_issues'
        ]
        
        for field in json_fields:
            if claim.get(field):
                try:
                    claim[field] = json.loads(claim[field])
                except json.JSONDecodeError:
                    # Default for fields that should be dicts vs lists
                    if field in ['extracted_json', 'medical_validation_result']:
                        claim[field] = {}
                    else:
                        claim[field] = []
            else:
                if field in ['extracted_json', 'medical_validation_result']:
                    claim[field] = {}
                else:
                    claim[field] = []
        
        return claim

    # Backward compatibility methods
    def insert_claim_basic(self, claim_data: Dict):
        """Backward compatible method for basic claim insertion"""
        # (This will now correctly call the new dynamic insert_claim)
        enhanced_data = {
            'claim_id': claim_data['claim_id'],
            'policy_number': claim_data.get('policy_number'),
            'patient_name': claim_data.get('patient_name'),
            'admission_date': claim_data.get('admission_date'),
            'discharge_date': claim_data.get('discharge_date'),
            'total_claim_amount': claim_data.get('total_claim_amount'),
            'fraud_score': claim_data.get('fraud_score'),
            'analysis_reason': claim_data.get('analysis_reason'),
            'status': claim_data.get('status', 'Pending'),
            'reviewer_name': claim_data.get('reviewer_name'),
            'review_comments': claim_data.get('review_comments'),
            'created_at': claim_data.get('created_at', datetime.now().isoformat()),
            'consolidated_text': claim_data.get('consolidated_text'),
            'associated_files': claim_data.get('associated_files', [])
        }
        self.insert_claim(enhanced_data)
