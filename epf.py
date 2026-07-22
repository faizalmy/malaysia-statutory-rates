# patches/epf.py (Refactored Code Snippet)

from typing import TypedDict, List, Dict, Optional, Any
import re

# Define a robust schema for clarity and type checking
class WageBracket(TypedDict):
    wage_min: float
    wage_max: float
    employer_rate: float
    employee_rate: float
    note: str
    total_percent: Optional[float] = None # Standardized field

def standardize_bracket(data: Dict[str, Any]) -> WageBracket:
    """Ensures all incoming bracket data conforms to a single type schema."""
    # Logic to parse and clean mixed-type data from Path B structure.
    
    # Example standardization for Path B fields (employer/employee percentages):
    if 'total' in data and isinstance(data['total'], str) and '%' in data['total']:
        try:
            raw_percent = data['total'].replace('%', '')
            total_val = float(raw_percent) / 100.0
        except ValueError:
            total_val = None # Handle badly formatted percentages
    else:
        total_val = None

    return WageBracket(
        wage_min=float(data['wage_min']), 
        wage_max=float(data['wage_max']), 
        employer_rate=float(data['employer_rate']), 
        employee_rate=float(data['employee_rate']), 
        note=str(data.get('note', '')), 
        total_percent=total_val
    )

# ... (Apply this standardization helper function to both Path A and Path B usage points in epf.py)