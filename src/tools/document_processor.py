import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text and metadata from PDF files."""
    
    @staticmethod
    async def extract_text(pdf_path: str) -> Optional[str]:
        """Extract text from PDF.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted text or None
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.get_text()
            
            doc.close()
            return text
        
        except Exception as e:
            logger.error(f"PDF extraction error: {str(e)}")
            return None
    
    @staticmethod
    async def extract_metadata(pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract metadata from PDF.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Metadata dictionary
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            metadata = doc.metadata
            doc.close()
            
            return {
                "title": metadata.get("title"),
                "author": metadata.get("author"),
                "subject": metadata.get("subject"),
                "keywords": metadata.get("keywords"),
                "pages": len(doc),
                "creation_date": metadata.get("creationDate"),
            }
        
        except Exception as e:
            logger.error(f"Metadata extraction error: {str(e)}")
            return None


class DocumentParser:
    """Parse various document formats."""
    
    @staticmethod
    async def parse_document(file_path: str) -> Optional[str]:
        """Parse document based on file type.
        
        Args:
            file_path: Path to document
        
        Returns:
            Extracted content
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return await PDFExtractor.extract_text(file_path)
        
        elif file_ext in [".txt", ".md", ".rst"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Text file reading error: {str(e)}")
                return None
        
        elif file_ext in [".docx", ".doc"]:
            return await DocumentParser._extract_docx(file_path)
        
        else:
            logger.warning(f"Unsupported file format: {file_ext}")
            return None
    
    @staticmethod
    async def _extract_docx(file_path: str) -> Optional[str]:
        """Extract text from DOCX file.
        
        Args:
            file_path: Path to DOCX file
        
        Returns:
            Extracted text
        """
        try:
            from docx import Document
            
            doc = Document(file_path)
            text = ""
            
            for para in doc.paragraphs:
                text += para.text + "\n"
            
            return text
        
        except Exception as e:
            logger.error(f"DOCX extraction error: {str(e)}")
            return None


class TextChunker:
    """Chunk large documents for processing."""
    
    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        overlap: int = 100
    ) -> list[str]:
        """Chunk text into overlapping segments.
        
        Args:
            text: Input text
            chunk_size: Characters per chunk
            overlap: Overlap between chunks
        
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - overlap
        
        return chunks
    
    @staticmethod
    def chunk_by_sentences(
        text: str,
        sentences_per_chunk: int = 5
    ) -> list[str]:
        """Chunk text by sentences.
        
        Args:
            text: Input text
            sentences_per_chunk: Sentences per chunk
        
        Returns:
            List of sentence chunks
        """
        import re
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = " ".join(sentences[i:i + sentences_per_chunk])
            chunks.append(chunk)
        
        return chunks