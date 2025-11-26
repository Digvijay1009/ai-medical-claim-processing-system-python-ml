import os
import fitz  # PyMuPDF an python library 
from PIL import Image
import pytesseract
from typing import List
import io

class TextExtractor:
    def __init__(self):
        # Configure tesseract path if needed (Windows) path needs to be added for using OCR
        if os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    def extract_and_consolidate_text(self, file_paths: List[str]) -> str:
        """
        Extract text from multiple files and consolidate into a single string
        """
        consolidated_text = ""
        
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            consolidated_text += f"\n--- NEW DOCUMENT: {filename} ---\n\n"
            
            try:
                if file_path.lower().endswith('.pdf'):
                    text = self._extract_from_pdf_improved(file_path)
                elif file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                    text = self._extract_from_image(file_path)
                else:
                    text = self._extract_from_text_file(file_path)
                
                consolidated_text += text + "\n"
                
            except Exception as e:
                consolidated_text += f"Error extracting text from {filename}: {str(e)}\n"
        
        print(f"📄 Total extracted text: {len(consolidated_text)} characters")
        return consolidated_text
    
    def _extract_from_pdf_improved(self, file_path: str) -> str:
        """Improved PDF text extraction with fallback to OCR"""
        doc = fitz.open(file_path)
        text = ""
        
        # Method 1: Try direct text extraction first
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            if page_text.strip():  # If we got meaningful text
                text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            else:
                # Method 2: Fallback to OCR for scanned PDFs
                print(f"📄 Page {page_num + 1}: No text found, using OCR...")
                ocr_text = self._extract_from_pdf_with_ocr(doc, page_num)
                text += f"\n--- Page {page_num + 1} (OCR) ---\n{ocr_text}\n"
        
        doc.close()
        
        # Clean up the text
        text = self._clean_extracted_text(text)
        return text
    
    def _extract_from_pdf_with_ocr(self, doc, page_num: int) -> str:
        """Extract text from PDF page using OCR"""
        try:
            page = doc[page_num]
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            
            # Use PIL to open the image
            image = Image.open(io.BytesIO(img_data))
            
            # Use tesseract to do OCR on the image
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            return f"OCR failed: {str(e)}"
    
    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove common PDF artifacts
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that are likely PDF metadata/artifacts
            if any(artifact in line for artifact in [
                '<<', '>>', 'obj', 'endobj', 'stream', 'endstream',
                'xref', 'trailer', 'startxref', '/Page', '/Contents',
                '/Producer', '/Creator', '/CreationDate', 'Net Income'
            ]):
                continue
            
            # Skip very short lines that are likely artifacts
            if len(line.strip()) > 3:
                cleaned_lines.append(line.strip())
        
        return '\n'.join(cleaned_lines)
    
    def _extract_from_image(self, file_path: str) -> str:
        """Extract text from image using Tesseract OCR"""
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text
    
    def _extract_from_text_file(self, file_path: str) -> str:
        """Extract text from plain text files"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        return text
    
    def render_pdf_as_image(self, file_path: str, page_num: int = 0):
        """Render PDF page as image for Streamlit display"""
        if file_path.lower().endswith('.pdf'):
            doc = fitz.open(file_path)
            if page_num < len(doc):
                page = doc[page_num]
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                doc.close()
                return img_data
            doc.close()
        return None