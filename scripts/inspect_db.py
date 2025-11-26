import sqlite3
import os

# Path to your database
db_path = "database/claims.db"

print(f"📂 Checking database at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print(f"❌ Database file not found!")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. List all columns in the 'claims' table
        print("-" * 50)
        print("📊 TABLE SCHEMA: claims")
        print("-" * 50)
        
        cursor.execute("PRAGMA table_info(claims)")
        columns = cursor.fetchall()
        
        text_col = None
        for col in columns:
            # col structure: (id, name, type, notnull, dflt_value, pk)
            col_name = col[1]
            col_type = col[2]
            print(f" • {col_name} ({col_type})")
            
            # Look for the column that likely holds the text
            if "text" in col_name.lower() or "consolidated" in col_name.lower():
                text_col = col_name

        # 2. Inspect the latest claim text (if a text column exists)
        print("-" * 50)
        if text_col:
            print(f"✅ Found text column: '{text_col}'")
            print("🔍 Checking latest claim for keywords...")
            
            cursor.execute(f"SELECT claim_id, patient_name, {text_col} FROM claims ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                claim_id, patient, content = row
                content_str = str(content).lower()
                print(f"   Claim: {claim_id} ({patient})")
                print(f"   Text Length: {len(content_str)} chars")
                
                # Check for the smoking gun keywords
                keywords = ["alcohol", "breathalyzer", "positive", "intoxicated"]
                found = [k for k in keywords if k in content_str]
                
                if found:
                    print(f"   🚨 KEYWORDS FOUND: {found}")
                else:
                    print(f"   ❌ Keywords NOT found in DB text.")
            else:
                print("   No claims found in table.")
        else:
            print("❌ Could not identify a text column (looked for 'text' or 'consolidated').")

        conn.close()

    except Exception as e:
        print(f"❌ Error reading database: {e}")