import os
import csv
import json
from datetime import datetime
from fpdf import FPDF
from scripts.db_handler import DatabaseHandler

# Define path for the AI training data
# We assume this runs from the root, so 'data/verified_fraud_cases.csv'
TRAINING_DATA_PATH = os.path.join("data", "verified_fraud_cases.csv")

def handle_mark_as_fraud(claim_id, user_id, fraud_analysis_result):
    """
    Main handler for the 'Mark as Fraud' button.
    Uses the existing DatabaseHandler to ensure safe connections.
    """
    print(f"🚨 Processing Fraud Rejection for Claim {claim_id}...")
    
    # 1. Update Database (Using the Handler)
    if update_claim_status_custom(claim_id, user_id, fraud_analysis_result):
        
        # 2. Save for AI Training
        save_for_retraining(claim_id, fraud_analysis_result)
        
        # 3. Generate Letter
        pdf_path = generate_rejection_letter(claim_id, fraud_analysis_result)
        
        return True, pdf_path
    
    return False, None

def update_claim_status_custom(claim_id, user_id, analysis):
    """
    Updates the claim status to 'Fraud Suspected' and records the specific reasons.
    """
    try:
        # Initialize your existing handler to get the correct path & connection
        db = DatabaseHandler()
        conn = db._get_connection()
        cursor = conn.cursor()
        
        # Extract reasons
        patterns = analysis.get('detected_patterns', [])
        # Handle case where patterns might be dicts or strings
        reason_list = []
        for p in patterns:
            if isinstance(p, dict):
                reason_list.append(p.get('description', 'Unknown Pattern'))
            else:
                reason_list.append(str(p))
                
        reason_str = "; ".join(reason_list)
        
        # We use 'Fraud Suspected' because your DB Schema restricts status values.
        # It does NOT allow 'REJECTED'.
        status_update = "Fraud Suspected" 
        
        query = """
            UPDATE claims 
            SET status = ?, 
                rejection_reason = ?, 
                reviewed_by = ?, 
                reviewed_at = ?,
                fraud_reason = ? 
            WHERE claim_id = ?
        """
        
        timestamp = datetime.now().isoformat()
        
        # We update both 'rejection_reason' (new column) and 'fraud_reason' (existing column) to be safe
        cursor.execute(query, (status_update, f"FRAUD: {reason_str}", user_id, timestamp, reason_str, claim_id))
        
        conn.commit()
        conn.close()
        print(f"✅ DB Updated: Claim {claim_id} marked as {status_update}.")
        return True
        
    except Exception as e:
        print(f"❌ DB Error in fraud_actions: {e}")
        return False

def save_for_retraining(claim_id, analysis):
    """
    Appends the confirmed fraud case to a CSV for future model training.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(TRAINING_DATA_PATH), exist_ok=True)
    
    # --- BUG FIX START ---
    # We create a clean list of pattern descriptions first
    patterns_list = []
    raw_patterns = analysis.get('detected_patterns', [])
    
    for p in raw_patterns:
        if isinstance(p, dict):
            # Try 'description' first (most common from UI), then 'pattern', then fallback
            text = p.get('description') or p.get('pattern') or "Unknown Pattern"
            patterns_list.append(str(text))
        else:
            # If it's just a string, add it directly
            patterns_list.append(str(p))
    # --- BUG FIX END ---

    # Flatten data for CSV
    row = {
        "claim_id": claim_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_score": analysis.get("overall_risk_score", 0),
        "diagnosis": analysis.get("diagnosis", "Unknown"),
        "fraud_patterns": str(patterns_list),  # Use our fixed list here
        "label": 1  # 1 = Confirmed Fraud
    }
    
    file_exists = os.path.isfile(TRAINING_DATA_PATH)
    try:
        with open(TRAINING_DATA_PATH, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"📈 Training Data Saved: {TRAINING_DATA_PATH}")
    except Exception as e:
        print(f"⚠️ CSV Save Failed: {e}")

# In app/scripts/fraud_actions.py

def clean_text(text):
    """
    Helper to make text PDF-safe:
    1. Replaces Rupee symbol (₹) with 'Rs.'
    2. Removes unsupported characters
    """
    if not text:
        return ""
    text = str(text)
    # Replace Rupee explicitly
    text = text.replace("₹", "Rs. ")
    # Force generic ASCII characters (replaces unknown symbols with '?')
    return text.encode('latin-1', 'replace').decode('latin-1')

# In app/scripts/fraud_actions.py

def generate_rejection_letter(claim_id, analysis):
    """
    Generates a professional PDF rejection letter with smart formatting.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)  # Add margins for better look
    
    # --- 1. Header ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="NOTICE OF CLAIM DECISION", ln=1, align='C')
    pdf.ln(5)
    
    # Draw a line
    pdf.line(20, 35, 190, 35)
    pdf.ln(10)
    
    # --- 2. Claim Details ---
    pdf.set_font("Arial", size=11)
    # Helper to print label: value aligned
    def print_field(label, value):
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(40, 8, txt=label, ln=0)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, txt=clean_text(value), ln=1)

    print_field("Claim ID:", claim_id)
    print_field("Date:", datetime.now().strftime('%Y-%m-%d'))
    print_field("Status:", "FRAUD SUSPECTED / DENIED")
    
    if analysis.get('overall_risk_score'):
         print_field("Risk Score:", f"{analysis.get('overall_risk_score')*100:.1f}%")

    pdf.ln(10)
    
    # --- 3. Body Text ---
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, txt="After a comprehensive review by our automated system and manual verification, we are pleased to inform you that this claim has been flagged for the following irregularities:")
    pdf.ln(5)
    
    # --- 4. Smart Pattern Formatting ---
    patterns = analysis.get('detected_patterns', [])
    
    # Normalize input to list of dicts
    if patterns and isinstance(patterns[0], str):
        patterns = [{'description': p} for p in patterns]

    for p in patterns:
        desc = str(p.get('description', 'Policy Violation'))
        
        # Logic: Extract a 'Title' from the text if it has a colon (e.g. "Medical: Short stay...")
        if ":" in desc and len(desc.split(":")[0]) < 20:
            parts = desc.split(":", 1)
            title = parts[0].strip()
            body = parts[1].strip()
        else:
            title = "Policy Violation"
            body = desc

        # Print Title (Bold Bullet Point)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(10, 8, txt=chr(149), ln=0)  # Bullet point symbol
        pdf.cell(0, 8, txt=clean_text(title), ln=1)
        
        # Print Body (Indented)
        pdf.set_font("Arial", size=11)
        pdf.set_x(30) # Indent
        pdf.multi_cell(0, 6, txt=clean_text(body))
        pdf.ln(3) # Small gap between items
    
    # --- 5. Footer ---
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 6, txt="If you believe this decision is in error, please submit a formal appeal with additional supporting documentation (e.g., Police FIR, detailed doctor notes) within 15 days.")
    
    # Save
    output_folder = os.path.join("data", "reports")
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.join(output_folder, f"rejection_{claim_id}.pdf")
    
    pdf.output(filename)
    return filename
# def generate_rejection_letter(claim_id, analysis):
#     """
#     Generates a PDF rejection letter with Safe Text.
#     """
#     pdf = FPDF()
#     pdf.add_page()
#     pdf.set_font("Arial", size=12)
    
#     # Simple Header
#     pdf.set_font("Arial", 'B', 16)
#     pdf.cell(200, 10, txt="NOTICE OF CLAIM DECISION", ln=1, align='C')
#     pdf.ln(10)
    
#     pdf.set_font("Arial", size=12)
#     pdf.cell(200, 10, txt=clean_text(f"Claim ID: {claim_id}"), ln=1)
#     pdf.cell(200, 10, txt=clean_text(f"Date: {datetime.now().strftime('%Y-%m-%d')}"), ln=1)
#     pdf.ln(10)
    
#     pdf.set_font("Arial", 'B', 12)
#     pdf.cell(200, 10, txt="Status: FRAUD SUSPECTED / DENIED", ln=1)
#     pdf.ln(5)
    
#     pdf.set_font("Arial", size=12)
#     pdf.multi_cell(0, 10, txt="Our automated system, verified by human review, has flagged this claim for the following inconsistencies:")
#     pdf.ln(5)
    
#     # --- SAFE LOOP FOR PATTERNS ---
#     # We use clean_text() on every string to prevent crashes
#     patterns = analysis.get('detected_patterns', [])
    
#     # If patterns is just a list of strings (rare case but possible)
#     if patterns and isinstance(patterns[0], str):
#         patterns = [{'pattern': 'Issue', 'description': p} for p in patterns]

#     for p in patterns:
#         pdf.set_font("Arial", 'B', 12)
        
#         # safely get values
#         pat_name = p.get('pattern', 'Violation')
#         if isinstance(pat_name, str):
#             pat_name = pat_name.replace('_', ' ').title()
            
#         desc = p.get('description', 'Policy Violation')
        
#         # Write to PDF with cleaning
#         pdf.cell(0, 10, txt=clean_text(f"- {pat_name}"), ln=1)
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt=clean_text(f"  Reason: {desc}"))
    
#     # Save into a 'reports' folder
#     output_folder = os.path.join("data", "reports")
#     os.makedirs(output_folder, exist_ok=True)
#     filename = os.path.join(output_folder, f"rejection_{claim_id}.pdf")
    
#     pdf.output(filename)
#     return filename