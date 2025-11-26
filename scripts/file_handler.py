import os
import uuid
from datetime import datetime
from typing import List, Tuple
import streamlit as st

class FileHandler:
    def __init__(self, upload_dir: str = "data/raw_claims"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    def save_uploaded_files(self, uploaded_files: List) -> Tuple[str, List[str]]:
        """
        Save uploaded files and generate a unique claim ID for the batch
        
        Returns:
            Tuple of (claim_id, list of saved file paths)
        """
        # Generate unique claim ID
        claim_id = f"CLM_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"
        
        saved_paths = []
        
        for uploaded_file in uploaded_files:
            # Create safe filename
            original_name = uploaded_file.name
            safe_filename = f"{claim_id}_{original_name.replace(' ', '_')}"
            file_path = os.path.join(self.upload_dir, safe_filename)
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            saved_paths.append(file_path)
        
        return claim_id, saved_paths
    
    def get_file_preview(self, file_path: str) -> str:
        """Get a clean text preview of the file"""
        try:
            if file_path.lower().endswith('.pdf'):
                import fitz
                doc = fitz.open(file_path)
                text = ""
                for page_num in range(min(2, len(doc))):  # First 2 pages
                    page_text = doc[page_num].get_text()
                    lines = page_text.split('\n')
                    clean_lines = [
                        line for line in lines
                        if len(line.strip()) > 3 and not any(
                            artifact in line for artifact in ['<<', '>>', 'obj', 'Net Income']
                        )
                    ]
                    text += '\n'.join(clean_lines[:20])
                doc.close()
                return text[:500] + "..." if len(text) > 500 else text
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return content[:500] + "..." if len(content) > 500 else content
        except Exception as e:
            return f"Preview unavailable: {str(e)}"
