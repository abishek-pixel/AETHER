"""Code execution tools for Aether research agents."""

import subprocess
import logging
import tempfile
import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class CodeExecutor:
    """Execute and validate Python code snippets safely."""
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        """Initialize code executor.
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_length: Maximum output length in characters
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
    
    async def execute_python(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute Python code safely in a subprocess.
        
        Args:
            code: Python code to execute
            context: Optional context variables to pass to code
        
        Returns:
            Execution result with output, errors, and status
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8"
            ) as f:
                # Inject context if provided
                if context:
                    f.write("# Context variables\n")
                    for key, value in context.items():
                        f.write(f"{key} = {repr(value)}\n")
                    f.write("\n")
                
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute code
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
                
                output = result.stdout[:self.max_output_length]
                errors = result.stderr[:self.max_output_length]
                
                return {
                    "status": "success" if result.returncode == 0 else "error",
                    "output": output,
                    "errors": errors,
                    "return_code": result.returncode,
                    "executed_at": datetime.utcnow().isoformat(),
                }
            
            finally:
                # Clean up
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "output": "",
                "errors": f"Code execution exceeded {self.timeout} second timeout",
                "return_code": -1,
                "executed_at": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            return {
                "status": "error",
                "output": "",
                "errors": str(e),
                "return_code": -1,
                "executed_at": datetime.utcnow().isoformat(),
            }
    
    def validate_python_syntax(self, code: str) -> Dict[str, Any]:
        """Validate Python code syntax without executing.
        
        Args:
            code: Python code to validate
        
        Returns:
            Validation result with syntax errors if any
        """
        try:
            compile(code, "<string>", "exec")
            return {
                "status": "valid",
                "syntax_errors": [],
                "message": "Code syntax is valid",
            }
        
        except SyntaxError as e:
            return {
                "status": "invalid",
                "syntax_errors": [
                    {
                        "line": e.lineno,
                        "offset": e.offset,
                        "message": e.msg,
                        "text": e.text,
                    }
                ],
                "message": f"Syntax error at line {e.lineno}: {e.msg}",
            }
        
        except Exception as e:
            return {
                "status": "error",
                "syntax_errors": [],
                "message": str(e),
            }


class QueryValidator:
    """Validate and assess data query results."""
    
    @staticmethod
    def validate_json(json_str: str) -> Dict[str, Any]:
        """Validate JSON format.
        
        Args:
            json_str: JSON string to validate
        
        Returns:
            Validation result
        """
        try:
            data = json.loads(json_str)
            return {
                "status": "valid",
                "data": data,
                "format": type(data).__name__,
                "size": len(str(data)),
            }
        
        except json.JSONDecodeError as e:
            return {
                "status": "invalid",
                "error": str(e),
                "data": None,
            }
    
    @staticmethod
    def assess_data_quality(data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality of data structure.
        
        Args:
            data: Data to assess
        
        Returns:
            Quality assessment
        """
        assessment = {
            "completeness": 1.0,
            "consistency": 1.0,
            "validity": 1.0,
            "issues": [],
        }
        
        # Check for missing values
        null_count = 0
        total_fields = 0
        
        def check_dict(d):
            nonlocal null_count, total_fields
            
            for v in d.values():
                total_fields += 1
                
                if v is None:
                    null_count += 1
                    assessment["issues"].append("Missing value found")
                elif isinstance(v, dict):
                    check_dict(v)
                elif isinstance(v, (list, tuple)):
                    if len(v) == 0:
                        assessment["issues"].append("Empty array/list found")
        
        if isinstance(data, dict):
            check_dict(data)
        
        if total_fields > 0:
            assessment["completeness"] = 1 - (null_count / total_fields)
        
        # Check consistency (e.g., type consistency)
        assessment["consistency"] = 0.95  # Placeholder
        
        # Overall quality score
        assessment["quality_score"] = (
            assessment["completeness"] * 0.5 +
            assessment["consistency"] * 0.3 +
            assessment["validity"] * 0.2
        )
        
        return assessment


class DataProcessor:
    """Process and transform data from research results."""
    
    @staticmethod
    def extract_numbers(text: str) -> list[float]:
        """Extract numerical values from text.
        
        Args:
            text: Text to process
        
        Returns:
            List of extracted numbers
        """
        import re
        
        # Pattern for numbers (including decimals, percentages)
        pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
        matches = re.findall(pattern, text)
        
        try:
            return [float(match) for match in matches]
        except ValueError:
            return []
    
    @staticmethod
    def extract_dates(text: str) -> list[str]:
        """Extract dates from text.
        
        Args:
            text: Text to process
        
        Returns:
            List of extracted dates
        """
        import re
        
        patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}\b',  # Month DD, YYYY
        ]
        
        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return list(set(dates))  # Remove duplicates
    
    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """Extract URLs from text.
        
        Args:
            text: Text to process
        
        Returns:
            List of extracted URLs
        """
        import re
        
        pattern = r'https?://[^\s]+'
        urls = re.findall(pattern, text)
        
        return urls
    
    @staticmethod
    def extract_entities(text: str, entity_type: str = "named") -> list[str]:
        """Extract entities from text (simplified without NLP).
        
        Args:
            text: Text to process
            entity_type: Type of entity to extract
        
        Returns:
            List of extracted entities
        """
        import re
        
        if entity_type == "email":
            pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        elif entity_type == "phone":
            pattern = r'(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
        elif entity_type == "domain":
            pattern = r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}'
        else:
            # Capitalized words as simple named entity extraction
            pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        
        entities = re.findall(pattern, text)
        return list(set(entities))  # Remove duplicates


class AnalysisExecutor:
    """Execute analysis operations on research data."""
    
    @staticmethod
    def calculate_statistics(values: list[float]) -> Dict[str, float]:
        """Calculate basic statistics.
        
        Args:
            values: List of numerical values
        
        Returns:
            Dictionary with statistical measures
        """
        if not values:
            return {}
        
        values = sorted(values)
        n = len(values)
        
        # Mean
        mean = sum(values) / n
        
        # Median
        if n % 2 == 0:
            median = (values[n//2 - 1] + values[n//2]) / 2
        else:
            median = values[n//2]
        
        # Standard deviation
        variance = sum((x - mean) ** 2 for x in values) / n
        std_dev = variance ** 0.5
        
        return {
            "count": n,
            "mean": round(mean, 2),
            "median": round(median, 2),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
            "std_dev": round(std_dev, 2),
        }
    
    @staticmethod
    def find_trends(values: list[float], window_size: int = 3) -> Dict[str, Any]:
        """Identify trends in numerical data.
        
        Args:
            values: List of numerical values
            window_size: Window size for moving average
        
        Returns:
            Trend analysis
        """
        if not values or len(values) < window_size:
            return {"trend": "insufficient_data"}
        
        # Calculate moving average
        moving_avg = []
        for i in range(len(values) - window_size + 1):
            avg = sum(values[i:i + window_size]) / window_size
            moving_avg.append(avg)
        
        # Determine trend direction
        if len(moving_avg) >= 2:
            trend_direction = "increasing" if moving_avg[-1] > moving_avg[0] else "decreasing"
        else:
            trend_direction = "stable"
        
        return {
            "trend": trend_direction,
            "moving_average": moving_avg,
            "volatility": sum(abs(moving_avg[i] - moving_avg[i-1]) for i in range(1, len(moving_avg))) / max(1, len(moving_avg) - 1),
        }
