from pydantic import BaseModel, Field as PydanticField
from typing import List as PyList, Optional as PyOptional, Dict as PyDict, Any as PyAny

# --- Pydantic Models for Rich Outputs ---
class StatCard(BaseModel):
    label: str = PydanticField(..., description="The label for the statistic.")
    value: str = PydanticField(..., description="The value of the statistic.")
    unit: PyOptional[str] = PydanticField(None, description="Optional unit for the statistic (e.g., '%', 'pts').")
    trend: PyOptional[str] = PydanticField(None, description="Optional trend indicator (e.g., 'up', 'down', 'neutral').")
    description: PyOptional[str] = PydanticField(None, description="Optional brief description or context for the stat.")

class ChartDataItem(BaseModel):
    label: str = PydanticField(..., description="Label for the data point (e.g., x-axis category).")
    value: float = PydanticField(..., description="Numerical value for the data point (e.g., y-axis value).")
    group: PyOptional[str] = PydanticField(None, description="Optional group name for grouped charts.")

class ChartOutput(BaseModel):
    type: str = PydanticField(..., description="Type of chart (e.g., 'bar', 'line', 'pie', 'scatter').")
    title: str = PydanticField(..., description="Title of the chart.")
    data: PyList[ChartDataItem] = PydanticField(..., description="Data for the chart.")
    x_axis_label: PyOptional[str] = PydanticField(None, description="Label for the X-axis.")
    y_axis_label: PyOptional[str] = PydanticField(None, description="Label for the Y-axis.")
    options: PyOptional[PyDict[str, PyAny]] = PydanticField(None, description="Additional chart display options.")

class TableColumn(BaseModel):
    key: str = PydanticField(..., description="The key for this column in the data objects (rows).")
    header: str = PydanticField(..., description="The display header for this column.")
    align: PyOptional[str] = PydanticField("left", description="Column content alignment ('left', 'center', 'right').")

class TableOutput(BaseModel):
    title: PyOptional[str] = PydanticField(None, description="Optional title for the table.")
    columns: PyList[TableColumn] = PydanticField(..., description="Defines the columns of the table.")
    data: PyList[PyDict[str, PyAny]] = PydanticField(..., description="List of data objects (rows) for the table.")
    caption: PyOptional[str] = PydanticField(None, description="Optional caption for the table.") 