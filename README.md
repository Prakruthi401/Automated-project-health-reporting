# Automated Project Health Reporting System
https://automated-project-health-reporting-swfzzqfdr6h6bbugewzicw.streamlit.app/

An AI-powered enterprise system for automated project health reporting using RAG (Red/Amber/Green) status methodology with a professional Streamlit dashboard.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This system provides automated visibility into project health without manual chasing of Project Managers. It evaluates project plans against predefined criteria and generates clear, actionable reports with plain-English reasoning, all presented in a modern, professional dashboard.

## Features

- **Automated RAG Status Determination**: Evaluates projects across four key dimensions
- **Plain-English Reasoning**: Provides clear explanations for status assignments
- **Handles Messy Data**: Gracefully handles incomplete or missing data
- **Weekly Reporting**: Generates weekly health reports for all projects
- **Interactive Dashboard**: Professional Streamlit UI with real-time analytics
- **Executive Presentations**: One-click PowerPoint generation for stakeholder meetings
- **Risk Radar**: Visual risk identification and breakdown
- **Velocity Analytics**: Interactive charts for project performance tracking
- **Progress Tracking**: Detects zero-progress issues and schedule delays
- **Professional UI**: Clean, business-friendly interface without distractions

## RAG Methodology

The system evaluates projects based on four indicators:

### 1. Schedule
- **Green**: On time (0 days delayed) or ahead of schedule
- **Amber**: Up to 10 days late
- **Red**: More than 10 days late or critical milestones delayed

### 2. Blockages
- **Green**: No blockages, running smoothly
- **Amber**: Minor blockages exist
- **Red**: Major, impossible-to-solve obstacles

### 3. Stakeholder Attitude
- **Green**: Positive comments or blank (no news is good news)
- **Amber**: Mild unhappiness, worry, or requests for assistance
- **Red**: Major dissatisfaction or serious problems

### 4. Budget Burn
- **Green**: Spending aligns with completion level
- **Amber**: 5-15% over expected spending
- **Red**: More than 15% over expected spending

### Final Status (Worst-Case Principle)
- **Red**: If ANY category is Red
- **Amber**: If any category is Amber (and no Reds)
- **Green**: Only if ALL categories are Green

## Installation

### Prerequisites

- Python 3.7 or higher
- Required Python packages

### Setup

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Clone or download this repository

## Project Data Format

Create a `projects` directory and add your project CSV files. Each CSV should have the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| task_name | Name of the task/milestone | "Requirements Gathering" |
| days_delayed | Number of days behind schedule | 0, 5, 15 |
| at_risk | Whether task is at risk | "Yes", "No" |
| comments | Stakeholder comments/notes | "Great progress", "Concerns about timeline" |
| budget_spent_pct | Percentage of budget spent | 20, 30, 50 |
| completion_percentage | Percentage of task completion | 20, 30, 50 |
| is_critical_milestone | Whether this is a critical milestone | True, False |

### Example CSV Structure

```csv
task_name,days_delayed,at_risk,comments,budget_spent_pct,completion_percentage,is_critical_milestone
Requirements Gathering,0,No,Great progress,20,20,False
Design Phase,5,No,Some concerns,35,30,True
Development Sprint 1,8,No,Need help,45,40,False
```

## Usage

### Run Weekly Health Report

Generate weekly RAG reports for all projects:

```bash
python run_agent.py <projects_directory> <output_directory>
```

Example:
```bash
python run_agent.py projects weekly_outputs
```

Or use defaults (will look for `projects` directory):
```bash
python run_agent.py
```

This will:
- Load all CSV/Excel files from the projects directory
- Evaluate each project using the RAG methodology
- Generate individual JSON and text reports for each project
- Create a summary report with overall portfolio status
- Save all outputs to the specified directory

### Launch Interactive Dashboard

Start the Streamlit dashboard for real-time analytics:

```bash
streamlit run app.py
```

Or using Python:
```bash
python -m streamlit run app.py
```

The dashboard provides:
- **KPI Cards**: Overall health score, active blockers, warnings
- **Portfolio Overview**: Aggregate metrics across all projects
- **Individual Project Assessment**: Detailed analysis per project
- **Analytics Tab**: Interactive charts and velocity tracking
- **Risk Radar Tab**: Risk identification and detailed breakdown
- **Executive Summary**: Business-focused insights and recommendations
- **Presentation Generation**: One-click PowerPoint generation and download

### Generate Executive Presentations

Create professional PowerPoint presentations for stakeholder meetings:

```bash
python generate_presentation.py
```

Or generate directly from the dashboard using the "Generate Executive Presentation" button in the sidebar.

### Programmatic Usage

You can also use the agent programmatically:

```python
from project_health_agent import ProjectHealthAgent, load_project_from_csv

# Initialize agent
agent = ProjectHealthAgent()

# Load project data
project_data = load_project_from_csv("projects/my_project.csv")

# Evaluate project
result = agent.evaluate_project(project_data)

print(f"Status: {result.status}")
print(f"Reasoning: {result.reasoning}")
```

## Output Files

### Weekly Reports

- `<project_name>_<timestamp>.json`: Detailed JSON report with all metrics
- `<project_name>_<timestamp>.txt`: Human-readable text report
- `summary_<timestamp>.txt`: Portfolio summary with status counts

These reports are automatically loaded by the Streamlit dashboard for visualization.

## Scheduling (Bonus)

To run the agent on a weekly schedule, you can use:

### Windows Task Scheduler

1. Open Task Scheduler
2. Create a new task
3. Set trigger to "Weekly"
4. Set action to run `python run_agent.py projects weekly_outputs`
5. Configure as needed

### Linux Cron

```bash
# Add to crontab -e
0 9 * * 1 cd /path/to/Zycus_RAG_Agent && python run_agent.py projects weekly_outputs
```

## Data Handling

The agent handles messy data gracefully:

- **Missing Numbers**: Flagged as Amber (requires manual review)
- **Empty Comments**: Interpreted as Green (no news is good news)
- **"Slipping"**: Treated literally as delay
- **Multiple Missing Values**: Flagged as Amber for human intervention

## File Structure

```
Zycus_RAG_Agent/
├── project_health_agent.py      # Core RAG evaluation logic
├── run_agent.py                  # Weekly report generator
├── app.py                        # Streamlit dashboard
├── RAG_METHODOLOGY.md           # Detailed methodology document
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── .streamlit/
│   └── config.toml              # Streamlit theme configuration
├── projects/                     # Directory for project CSV/Excel files (you create this)
└── weekly_outputs/              # Generated weekly reports (auto-created)
```

## Troubleshooting

### No CSV/Excel files found
Ensure your project files are in CSV or Excel format and placed in the projects directory.

### Missing columns
The agent will flag missing required columns as Amber. Ensure your files have the required columns or use the Excel column mapping.

### Dashboard not loading
Ensure all dependencies are installed: `pip install -r requirements.txt`

### AI Assistant not responding
1. Install the current SDK: `pip install google-genai`
2. Get a key from: https://aistudio.google.com/apikey
3. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
4. Restart the app: `streamlit run app.py`

**Windows (temporary, current session only):**
```cmd
set GEMINI_API_KEY=your_api_key_here
```

**Note:** Do not paste API keys directly into Python files — use the `.env` file instead.

## Support

For questions or issues, refer to the RAG_METHODOLOGY.md document for detailed evaluation criteria.
