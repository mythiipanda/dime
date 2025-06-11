"""
Data Science Tools for LangGraph Agent.
Provides pandas, CSV, data manipulation, and Python REPL capabilities.
"""

import os
import io
import sys
import json
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from langchain_core.tools import Tool
from langchain_experimental.utilities import PythonREPL
from pydantic import BaseModel, Field


class PandasDataFrameInput(BaseModel):
    """Input for pandas DataFrame operations."""
    operation: str = Field(..., description="The pandas operation to perform")
    data: Optional[Union[str, Dict, List]] = Field(None, description="Data for DataFrame creation (JSON, CSV string, or dict)")
    df_name: Optional[str] = Field("df", description="Name of the DataFrame variable")


class CSVOperationInput(BaseModel):
    """Input for CSV operations."""
    file_path: str = Field(..., description="Path to the CSV file")
    operation: str = Field("read", description="Operation: 'read', 'write', 'info'")
    data: Optional[str] = Field(None, description="Data to write (for write operations)")
    options: Optional[Dict[str, Any]] = Field({}, description="Additional pandas options (index_col, parse_dates, etc.)")


class PythonCodeInput(BaseModel):
    """Input for Python code execution."""
    code: str = Field(..., description="Python code to execute")
    save_variables: bool = Field(True, description="Whether to save variables in session")


class DataVisualizationInput(BaseModel):
    """Input for data visualization."""
    data_source: str = Field(..., description="Data source (DataFrame variable name or CSV path)")
    chart_type: str = Field(..., description="Type of chart: 'line', 'bar', 'scatter', 'histogram', 'box', 'heatmap', 'pie'")
    x_column: Optional[str] = Field(None, description="X-axis column")
    y_column: Optional[str] = Field(None, description="Y-axis column")
    title: Optional[str] = Field(None, description="Chart title")
    save_path: Optional[str] = Field(None, description="Path to save chart")


# Global Python session state for persistence
_python_session = {}


def create_dataframe_from_data(data: Union[str, Dict, List], df_name: str = "df") -> str:
    """Create a pandas DataFrame from various data sources."""
    try:
        if isinstance(data, str):
            # Try to parse as JSON first
            try:
                parsed_data = json.loads(data)
                df = pd.DataFrame(parsed_data)
            except json.JSONDecodeError:
                # Try to parse as CSV
                df = pd.read_csv(io.StringIO(data))
        elif isinstance(data, dict):
            df = pd.DataFrame(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            return f"Error: Unsupported data type {type(data)}"
        
        # Store in global session
        _python_session[df_name] = df
        
        # Return DataFrame info
        buffer = io.StringIO()
        df.info(buf=buffer)
        info = buffer.getvalue()
        
        return f"DataFrame '{df_name}' created successfully!\n\nDataFrame Info:\n{info}\n\nFirst 5 rows:\n{df.head()}"
        
    except Exception as e:
        return f"Error creating DataFrame: {str(e)}\nTraceback: {traceback.format_exc()}"


def perform_pandas_operation(operation: str, data: Optional[Union[str, Dict, List]] = None, df_name: str = "df") -> str:
    """Perform pandas operations on DataFrames."""
    try:
        # If data is provided, create DataFrame first
        if data is not None:
            result = create_dataframe_from_data(data, df_name)
            if "Error" in result:
                return result
        
        # Check if DataFrame exists in session
        if df_name not in _python_session:
            return f"Error: DataFrame '{df_name}' not found. Create it first with data."
        
        df = _python_session[df_name]
        
        # Create safe execution environment
        safe_globals = {
            'pd': pd,
            'np': np,
            'df': df,
            df_name: df,
            '__builtins__': {}
        }
        
        # Add all DataFrames from session
        safe_globals.update(_python_session)
        
        # Execute the operation
        result = eval(operation, safe_globals)
        
        # If result is a DataFrame, store it
        if isinstance(result, pd.DataFrame):
            _python_session[f"{df_name}_result"] = result
            return f"Operation executed successfully!\n\nResult (stored as '{df_name}_result'):\n{result}"
        else:
            return f"Operation executed successfully!\n\nResult:\n{result}"
            
    except Exception as e:
        return f"Error executing pandas operation: {str(e)}\nTraceback: {traceback.format_exc()}"


def read_csv_file(file_path: str, options: Dict[str, Any] = None) -> str:
    """Read a CSV file and return information about it."""
    try:
        if options is None:
            options = {}
            
        # Read the CSV file
        df = pd.read_csv(file_path, **options)
        
        # Store in session with filename as variable name
        var_name = Path(file_path).stem.replace('-', '_').replace(' ', '_')
        _python_session[var_name] = df
        
        # Get DataFrame info
        buffer = io.StringIO()
        df.info(buf=buffer)
        info = buffer.getvalue()
        
        return f"CSV file '{file_path}' loaded successfully as '{var_name}'!\n\nDataFrame Info:\n{info}\n\nFirst 5 rows:\n{df.head()}\n\nLast 5 rows:\n{df.tail()}"
        
    except Exception as e:
        return f"Error reading CSV file: {str(e)}\nTraceback: {traceback.format_exc()}"


def write_csv_file(file_path: str, data_source: str, options: Dict[str, Any] = None) -> str:
    """Write a DataFrame to a CSV file."""
    try:
        if options is None:
            options = {}
            
        # Get DataFrame from session
        if data_source not in _python_session:
            return f"Error: DataFrame '{data_source}' not found in session."
        
        df = _python_session[data_source]
        
        # Write to CSV
        df.to_csv(file_path, **options)
        
        return f"DataFrame '{data_source}' saved to '{file_path}' successfully!"
        
    except Exception as e:
        return f"Error writing CSV file: {str(e)}\nTraceback: {traceback.format_exc()}"


def get_csv_info(file_path: str) -> str:
    """Get information about a CSV file without loading it fully."""
    try:
        # Read just the first few rows to get structure
        df_sample = pd.read_csv(file_path, nrows=5)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Count total rows (approximate)
        with open(file_path, 'r') as f:
            row_count = sum(1 for line in f) - 1  # Subtract header
        
        return f"""CSV File Information: {file_path}
File Size: {file_size_mb:.2f} MB
Estimated Rows: {row_count:,}
Columns: {len(df_sample.columns)}

Column Names and Types:
{df_sample.dtypes}

Sample Data (first 5 rows):
{df_sample}"""
        
    except Exception as e:
        return f"Error getting CSV info: {str(e)}\nTraceback: {traceback.format_exc()}"


def execute_python_code(code: str, save_variables: bool = True) -> str:
    """Execute Python code with access to pandas, numpy, and session variables."""
    try:
        # Create execution environment
        exec_globals = {
            'pd': pd,
            'np': np,
            'plt': plt,
            'sns': sns,
            'os': os,
            'json': json,
            'io': io,
            '__builtins__': __builtins__
        }
        
        # Add session variables
        exec_globals.update(_python_session)
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            # Execute the code
            exec(code, exec_globals)
            
            # Save variables back to session if requested
            if save_variables:
                for key, value in exec_globals.items():
                    # Avoid saving built-in modules or internal variables
                    if not key.startswith('__') and key not in ['pd', 'np', 'plt', 'sns', 'os', 'json', 'io', 'sys', 'tempfile', 'traceback', 'Path']:
                        # Only save types that are generally useful and serializable/manageable
                        if isinstance(value, (pd.DataFrame, pd.Series, dict, list, int, float, str, bool, type(None), np.ndarray)):
                            _python_session[key] = value
            
        finally:
            sys.stdout = old_stdout
        
        output = captured_output.getvalue()
        
        # If no explicit print output, try to get the result of the last expression
        if not output.strip():
            try:
                # Attempt to evaluate the last statement as an expression
                # This is a heuristic and might not always work for multi-line code
                last_line = code.strip().split('\n')[-1]
                result = eval(last_line, exec_globals)
                if result is not None:
                    output = str(result)
            except Exception:
                output = "Code executed successfully (no explicit output or last expression result)"
        
        return f"Python code executed successfully!\n\nOutput:\n{output}"
        
    except Exception as e:
        return f"Error executing Python code: {str(e)}\nTraceback: {traceback.format_exc()}"


def create_data_visualization(data_source: str, chart_type: str, x_column: Optional[str] = None, 
                            y_column: Optional[str] = None, title: Optional[str] = None, 
                            save_path: Optional[str] = None) -> str:
    """Create data visualizations using matplotlib and seaborn."""
    try:
        # Get data source
        if data_source.endswith('.csv'):
            df = pd.read_csv(data_source)
        elif data_source in _python_session:
            df = _python_session[data_source]
        else:
            return f"Error: Data source '{data_source}' not found."
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Create chart based on type
        if chart_type == 'line':
            if x_column and y_column:
                plt.plot(df[x_column], df[y_column])
                plt.xlabel(x_column)
                plt.ylabel(y_column)
            else:
                df.plot(kind='line')
                
        elif chart_type == 'bar':
            if x_column and y_column:
                plt.bar(df[x_column], df[y_column])
                plt.xlabel(x_column)
                plt.ylabel(y_column)
            else:
                df.plot(kind='bar')
                
        elif chart_type == 'scatter':
            if x_column and y_column:
                plt.scatter(df[x_column], df[y_column])
                plt.xlabel(x_column)
                plt.ylabel(y_column)
            else:
                return "Error: Scatter plot requires x_column and y_column"
                
        elif chart_type == 'histogram':
            if y_column:
                plt.hist(df[y_column], bins=30)
                plt.xlabel(y_column)
                plt.ylabel('Frequency')
            else:
                df.hist(figsize=(12, 8))
                
        elif chart_type == 'box':
            if y_column:
                plt.boxplot(df[y_column])
                plt.ylabel(y_column)
            else:
                df.boxplot(figsize=(12, 8))
                
        elif chart_type == 'heatmap':
            numeric_df = df.select_dtypes(include=[np.number])
            sns.heatmap(numeric_df.corr(), annot=True, cmap='coolwarm')
            
        elif chart_type == 'pie':
            if y_column:
                df[y_column].value_counts().plot(kind='pie')
            else:
                return "Error: Pie chart requires y_column"
        else:
            return f"Error: Unsupported chart type '{chart_type}'"
        
        # Set title
        if title:
            plt.title(title)
        else:
            plt.title(f"{chart_type.title()} Chart")
        
        # Save or show
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return f"Chart saved to '{save_path}' successfully!"
        else:
            # Save to temporary file and return path
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                plt.savefig(tmp.name, dpi=150, bbox_inches='tight')
                plt.close()
                return f"Chart created successfully! Saved to: {tmp.name}"
                
    except Exception as e:
        return f"Error creating visualization: {str(e)}\nTraceback: {traceback.format_exc()}"


def list_session_variables() -> str:
    """List all variables in the current Python session."""
    if not _python_session:
        return "No variables in session."
    
    result = "Session Variables:\n"
    for name, value in _python_session.items():
        if isinstance(value, pd.DataFrame):
            result += f"  {name}: DataFrame ({value.shape[0]} rows, {value.shape[1]} columns)\n"
        elif isinstance(value, pd.Series):
            result += f"  {name}: Series ({len(value)} elements)\n"
        elif isinstance(value, np.ndarray):
            result += f"  {name}: NumPy Array {value.shape}\n"
        else:
            result += f"  {name}: {type(value).__name__} - {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}\n"
    
    return result


# Create LangChain tools
pandas_dataframe_tool = Tool(
    name="pandas_dataframe_operations",
    description="""Perform pandas DataFrame operations. Can create DataFrames from data and execute pandas operations.
    
    Input should be a JSON object with:
    - operation: The pandas operation to perform (e.g., "df.head()", "df.groupby('column').mean()", "df.describe()")
    - data: Optional data to create DataFrame (JSON, CSV string, or dict)
    - df_name: Name of the DataFrame variable (default: 'df')
    
    Examples:
    - {"operation": "df.head(10)", "df_name": "my_data"}
    - {"operation": "df.groupby('category').sum()", "data": {"category": ["A", "B", "A"], "value": [1, 2, 3]}}
    - {"operation": "df.describe()"}""",
    func=lambda x: perform_pandas_operation(**json.loads(x) if isinstance(x, str) else x)
)

csv_operations_tool = Tool(
    name="csv_file_operations", 
    description="""Read, write, and analyze CSV files using pandas.
    
    Input should be a JSON object with:
    - file_path: Path to the CSV file
    - operation: 'read', 'write', or 'info'
    - data: DataFrame variable name (for write operations)
    - options: Additional pandas options (index_col, parse_dates, etc.)
    
    Examples:
    - {"file_path": "data.csv", "operation": "read"}
    - {"file_path": "output.csv", "operation": "write", "data": "my_dataframe"}
    - {"file_path": "large_file.csv", "operation": "info"}""",
    func=lambda x: {
        'read': lambda p: read_csv_file(p.get('file_path'), p.get('options', {})),
        'write': lambda p: write_csv_file(p.get('file_path'), p.get('data'), p.get('options', {})),
        'info': lambda p: get_csv_info(p.get('file_path'))
    }[json.loads(x)['operation'] if isinstance(x, str) else x['operation']](json.loads(x) if isinstance(x, str) else x)
)

def _parse_python_code_tool_input(x: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Helper function to parse python_code_execution tool input, handling __arg1."""
    if isinstance(x, str):
        parsed_input = json.loads(x)
    elif isinstance(x, dict):
        parsed_input = x
    else:
        raise ValueError(f"Unsupported input type for python_code_execution tool: {type(x)}")

    # If the LLM wraps the arguments in '__arg1', unwrap it.
    if '__arg1' in parsed_input and isinstance(parsed_input['__arg1'], str):
        # The value of __arg1 is itself a JSON string, so parse it again.
        # This handles cases where the LLM double-encodes the arguments.
        return json.loads(parsed_input['__arg1'])
    elif '__arg1' in parsed_input and isinstance(parsed_input['__arg1'], dict):
        # If __arg1 is already a dict, use it directly.
        return parsed_input['__arg1']
    else:
        return parsed_input

python_repl_tool = Tool(
    name="python_code_execution",
    description="""Execute Python code with access to pandas, numpy, matplotlib, and session variables.
    
    Input should be a JSON object with:
    - code: Python code to execute
    - save_variables: Whether to save variables in session (default: true)
    
    Examples:
    - {"code": "import pandas as pd; df = pd.DataFrame({'A': [1,2,3], 'B': [4,5,6]}); print(df)"}
    - {"code": "result = df.groupby('category').mean(); print(result)"}
    - {"code": "df.plot(); plt.savefig('chart.png')"}""",
    func=lambda x: execute_python_code(**_parse_python_code_tool_input(x))
)

data_visualization_tool = Tool(
    name="create_data_visualization",
    description="""Create charts and visualizations from DataFrames or CSV files.
    
    Input should be a JSON object with:
    - data_source: DataFrame variable name or CSV file path
    - chart_type: 'line', 'bar', 'scatter', 'histogram', 'box', 'heatmap', 'pie'
    - x_column: X-axis column name (optional)
    - y_column: Y-axis column name (optional)
    - title: Chart title (optional)
    - save_path: Path to save chart (optional, creates temp file if not provided)
    
    Examples:
    - {"data_source": "df", "chart_type": "histogram", "y_column": "sales"}
    - {"data_source": "data.csv", "chart_type": "scatter", "x_column": "x", "y_column": "y", "title": "X vs Y"}
    - {"data_source": "df", "chart_type": "heatmap"}""",
    func=lambda x: create_data_visualization(**json.loads(x) if isinstance(x, str) else x)
)

session_variables_tool = Tool(
    name="list_session_variables",
    description="List all variables (DataFrames, arrays, etc.) currently available in the Python session.",
    func=lambda x: list_session_variables()
)

# Export all tools
__all__ = [
    'pandas_dataframe_tool',
    'csv_operations_tool', 
    'python_repl_tool',
    'data_visualization_tool',
    'session_variables_tool'
]