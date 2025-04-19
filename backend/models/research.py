from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union

class StatCardData(BaseModel):
    label: str = Field(..., description="The label for the statistic (e.g., 'Points Per Game')")
    value: Union[str, float, int] = Field(..., description="The value of the statistic")
    unit: Optional[str] = Field(None, description="Optional unit (e.g., '%', 'RPG')")
    # trend: Optional[Literal['up', 'down', 'neutral']] = None # Add later if needed

class ChartDataPoint(BaseModel):
    label: str = Field(..., description="Label for the X-axis or category")
    value: Union[float, int] = Field(..., description="Numerical value for the Y-axis")
    # Add more fields if supporting multi-line/bar charts, e.g., value2, value3

class ChartData(BaseModel):
    type: Literal['bar', 'line'] = Field(..., description="The type of chart to render")
    title: str = Field(..., description="The title of the chart")
    data: List[ChartDataPoint] = Field(..., description="The data points for the chart")

class ReportSection(BaseModel):
    title: str = Field(..., description="The title of this section (e.g., 'Key Findings', 'Analysis')")
    content: str = Field(..., description="The main text content for this section in Markdown format.")
    stat_cards: Optional[List[StatCardData]] = Field(default_factory=list, description="Optional list of stat cards relevant to this section.")
    charts: Optional[List[ChartData]] = Field(default_factory=list, description="Optional list of charts relevant to this section.")

class ResearchReportModel(BaseModel):
    report_title: str = Field(..., description="A concise and informative title for the entire research report.")
    topic_summary: str = Field(..., description="A brief restatement of the user's research topic.")
    sections: List[ReportSection] = Field(..., description="List of report sections containing content, stats, and charts.")
    data_sources_used: List[str] = Field(..., description="List of the primary tool_names called to generate this report.")
    report_date: str = Field(..., description="The date the report was generated (YYYY-MM-DD).") 