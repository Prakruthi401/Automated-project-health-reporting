import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json
import os
import tempfile
from google import genai
from dotenv import load_dotenv
from project_health_agent import load_project_from_excel

# Load environment variables from .env file
load_dotenv(override=True)

RAG_COLORS = {'Green': '#28A745', 'Amber': '#FFC107', 'Red': '#DC3545'}
RAG_SCORE_VALUES = {'Green': 3, 'Amber': 2, 'Red': 1}
CATEGORY_ORDER = ["Schedule", "Blockages", "Stakeholder Attitude", "Budget Burn"]
CATEGORY_WEIGHTS = {
    "Schedule": 0.25,
    "Budget Burn": 0.25,
    "Blockages": 0.25,
    "Stakeholder Attitude": 0.25,
}
WEIGHTED_STATUS_PCT = {'Green': 100, 'Amber': 50, 'Red': 0}

GEMINI_MODEL_FALLBACKS = [
    'gemini-2.5-flash',
    'gemini-flash-latest',
    'gemini-2.0-flash',
    'gemini-2.5-pro',
    'gemini-pro-latest',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash',
]

# Page configuration
st.set_page_config(
    page_title="Project Health Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dashboard aesthetic
def load_custom_css():
    st.markdown("""
    <style>
    /* Main container styling */
    .main {
        background-color: #F8F9FA;
    }
    
    /* Card styling with floating effect */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 15px 15px 15px 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #00B4D8;
        margin: 10px 0;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        min-height: 80px;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Metric value styling */
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #0A192F;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .metric-label {
        font-size: 0.65rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.2px;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 6px;
    }
    
    /* Header styling */
    .header-title {
        color: #0A192F;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 10px;
    }
    
    .header-subtitle {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 8px;
        padding: 10px 20px;
        border: 1px solid #e0e0e0;
    }
    
    /* Chat interface styling */
    .chat-container {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Risk alert styling */
    .risk-critical {
        border-left: 4px solid #DC3545;
    }
    
    .risk-high {
        border-left: 4px solid #FFC107;
    }
    
    .risk-medium {
        border-left: 4px solid #00B4D8;
    }
    
    /* Status badges */
    .status-green {
        background-color: #28A745;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .status-amber {
        background-color: #FFC107;
        color: #0A192F;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .status-red {
        background-color: #DC3545;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: white;
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# Load project data
def load_project_data():
    """Load project health data from uploaded files only"""
    from project_health_agent import ProjectHealthAgent, load_project_from_excel

    projects = []

    # Only check for uploaded files in session state
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        agent = ProjectHealthAgent()

        for uploaded_file in st.session_state.uploaded_files:
            tmp_path = None
            try:
                try:
                    uploaded_file.seek(0)
                except Exception:
                    pass

                suffix = os.path.splitext(uploaded_file.name or '')[1] or '.xlsx'
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=suffix,
                    dir=tempfile.gettempdir(),
                    prefix='phr_upload_'
                ) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp.flush()
                    try:
                        os.fsync(tmp.fileno())
                    except Exception:
                        pass
                    tmp_path = tmp.name

                try:
                    df = load_project_from_excel(tmp_path)

                    if df is not None and not df.empty:
                        project_name = os.path.splitext(uploaded_file.name)[0]
                        result = agent.evaluate_project(df)
                        projects.append({
                            'project_name': project_name,
                            'overall_status': result.status,
                            'reasoning': result.reasoning,
                            'category_scores': result.category_scores,
                            'category_details': result.details,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'uploaded'
                        })
                    else:
                        st.warning(
                            f"File {uploaded_file.name} produced no project rows after "
                            f"column mapping. Confirm the sheet contains tasks with at "
                            f"least 3 of: Task Name, % Complete, Variance/Days Delayed, "
                            f"At Risk, Comments, Budget Spent, Baseline Start/Finish."
                        )
                except Exception as inner_e:
                    st.error(
                        f"Error evaluating {uploaded_file.name}: {inner_e}"
                    )
                    import traceback
                    with st.expander(f"Stack trace for {uploaded_file.name}"):
                        st.code(traceback.format_exc())
            except Exception as e:
                st.error(f"Error processing uploaded file {uploaded_file.name}: {e}")
                import traceback
                with st.expander("Technical details"):
                    st.code(traceback.format_exc())
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

    return projects if projects else None

# Load raw Excel data for a project
def load_raw_excel_data(project_name):
    """Load raw Excel data for a specific project"""
    from project_health_agent import load_project_from_excel

    # First try to get from uploaded files in session state
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        for uploaded_file in st.session_state.uploaded_files:
            file_project_name = os.path.splitext(uploaded_file.name)[0]
            if file_project_name.lower() == project_name.lower() or project_name.lower() in file_project_name.lower():
                tmp_path = None
                try:
                    try:
                        uploaded_file.seek(0)
                    except Exception:
                        pass
                    suffix = os.path.splitext(uploaded_file.name or '')[1] or '.xlsx'
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix,
                        dir=tempfile.gettempdir(),
                        prefix='phr_raw_'
                    ) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp.flush()
                        try:
                            os.fsync(tmp.fileno())
                        except Exception:
                            pass
                        tmp_path = tmp.name
                    df = load_project_from_excel(tmp_path)
                    return df.copy()
                except Exception:
                    pass
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

    # Fallback to projects directory
    projects_dir = "projects"
    if not os.path.exists(projects_dir):
        return None

    for filename in os.listdir(projects_dir):
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            if project_name.lower() in filename.lower():
                file_path = os.path.join(projects_dir, filename)
                try:
                    import pandas as pd
                    df = pd.read_excel(file_path)
                    return df
                except Exception as e:
                    st.error(f"Error loading Excel data: {e}")
                    return None

    return None

def normalize_rag_status(status):
    """Normalize RAG status strings to canonical Green/Amber/Red."""
    if not status or not isinstance(status, str):
        return None
    normalized = status.strip().title()
    return normalized if normalized in RAG_SCORE_VALUES else None

def rag_to_score_value(status):
    """Map RAG status to numeric chart value (Green=3, Amber=2, Red=1)."""
    normalized = normalize_rag_status(status)
    return RAG_SCORE_VALUES.get(normalized, 0)

def compute_portfolio_health_metrics(projects):
    """Compute multiple portfolio health views beyond binary project rollup."""
    if not projects:
        return {
            'project_rollup': 0,
            'category_rollup': 0,
            'health_index': 0,
            'weighted': 0,
            'green_projects': 0,
            'total_projects': 0,
            'green_categories': 0,
            'total_categories': 0,
        }

    total_projects = len(projects)
    green_projects = sum(1 for p in projects if p.get('overall_status') == 'Green')

    green_categories = 0
    total_categories = 0
    earned_points = 0
    max_points = 0
    project_weighted_scores = []

    for project in projects:
        category_scores = project.get('category_scores', {})
        project_weighted_total = 0.0

        for category in CATEGORY_ORDER:
            status = normalize_rag_status(category_scores.get(category))
            if not status:
                continue

            total_categories += 1
            max_points += RAG_SCORE_VALUES['Green']
            earned_points += RAG_SCORE_VALUES[status]

            if status == 'Green':
                green_categories += 1

            weight = CATEGORY_WEIGHTS.get(category, 0.0)
            project_weighted_total += weight * WEIGHTED_STATUS_PCT[status]

        project_weighted_scores.append(project_weighted_total)

    return {
        'project_rollup': int((green_projects / total_projects) * 100) if total_projects else 0,
        'category_rollup': int((green_categories / total_categories) * 100) if total_categories else 0,
        'health_index': int((earned_points / max_points) * 100) if max_points else 0,
        'weighted': int(sum(project_weighted_scores) / len(project_weighted_scores)) if project_weighted_scores else 0,
        'green_projects': green_projects,
        'total_projects': total_projects,
        'green_categories': green_categories,
        'total_categories': total_categories,
    }

def get_gemini_client():
    """Create a Gemini client using API key from session state or environment."""
    if 'api_key' in st.session_state and st.session_state.api_key:
        return genai.Client(api_key=st.session_state.api_key)

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


@st.cache_data(show_spinner=False, ttl=300)
def check_api_status(api_key_identifier):
    """Probe Gemini connectivity with the active key and return a status dict.

    ``api_key_identifier`` is an opaque string (e.g. masked key) used only to
    invalidate the cache when the user changes the key value.
    """
    client = get_gemini_client()
    if client is None:
        return {
            "ok": False,
            "status": "not_configured",
            "message": "No API key configured — add a key to enable AI insights.",
        }

    probe_models = GEMINI_MODEL_FALLBACKS

    last_message = "All known models are currently unavailable."
    auth_hit = False
    quota_hit = False

    for model_name in probe_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Respond with exactly: OK"
            )
            text = extract_gemini_text(response)
            if text or response is not None:
                return {
                    "ok": True,
                    "status": "connected",
                    "message": f"Connected via {model_name}. AI features ready.",
                    "model": model_name,
                }
        except Exception as e:
            error_msg = str(e)
            if '401' in error_msg or '403' in error_msg or 'API_KEY' in error_msg or 'INVALID' in error_msg.upper():
                auth_hit = True
                last_message = "Invalid API key — please verify the key value or generate a new one at https://aistudio.google.com/apikey"
            elif '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                quota_hit = True
                last_message = "Quota reached — the key is valid but the current plan has no remaining requests. Wait briefly or enable billing at https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com"
            elif '404' in error_msg or 'NOT_FOUND' in error_msg:
                continue
            else:
                last_message = f"Model {model_name} error: {error_msg[:200]}"

    if auth_hit:
        return {"ok": False, "status": "invalid_key", "message": last_message}
    if quota_hit:
        return {"ok": False, "status": "quota_exceeded", "message": last_message}
    return {"ok": False, "status": "unavailable", "message": last_message}

def extract_gemini_text(response):
    """Safely extract text from a Gemini response object."""
    text = getattr(response, 'text', None)
    if text:
        return text

    candidates = getattr(response, 'candidates', None) or []
    for candidate in candidates:
        content = getattr(candidate, 'content', None)
        if not content:
            continue
        parts = getattr(content, 'parts', None) or []
        part_text = ''.join(
            part.text for part in parts
            if getattr(part, 'text', None)
        )
        if part_text:
            return part_text

    return None

def generate_portfolio_insight(prompt, context):
    """Call Gemini for sidebar portfolio insights."""
    client = get_gemini_client()
    if client is None:
        return None, 'missing_key'

    gemini_prompt = f"""You are an expert project management consultant. Answer the user's question based on the following project health data.

{context}

User Question: {prompt}

Provide a concise, actionable response focusing on insights and recommendations."""

    models_to_try = GEMINI_MODEL_FALLBACKS

    auth_error = False
    quota_error = False
    last_error_msg = ""

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=gemini_prompt
            )
            text = extract_gemini_text(response)
            if text:
                return text, None
        except Exception as e:
            error_msg = str(e)
            last_error_msg = error_msg
            if '404' in error_msg or 'NOT_FOUND' in error_msg:
                continue
            if 'API_KEY' in error_msg or '401' in error_msg or '403' in error_msg or 'INVALID' in error_msg.upper():
                auth_error = True
                continue
            if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg or 'quota' in error_msg.lower():
                quota_error = True
                continue
            continue

    if auth_error:
        return None, 'invalid_api_key'
    if quota_error:
        return None, 'quota_exceeded'
    return None, 'model_not_found'

def load_project_excel_mapped(project_name):
    """Load mapped Excel data for a project using the agent's column mapping."""
    from project_health_agent import load_project_from_excel

    # First try to get from uploaded files in session state
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        for uploaded_file in st.session_state.uploaded_files:
            file_project_name = os.path.splitext(uploaded_file.name)[0]
            if file_project_name.lower() == project_name.lower() or project_name.lower() in file_project_name.lower():
                tmp_path = None
                try:
                    try:
                        uploaded_file.seek(0)
                    except Exception:
                        pass
                    suffix = os.path.splitext(uploaded_file.name or '')[1] or '.xlsx'
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix,
                        dir=tempfile.gettempdir(),
                        prefix='phr_map_'
                    ) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp.flush()
                        try:
                            os.fsync(tmp.fileno())
                        except Exception:
                            pass
                        tmp_path = tmp.name
                    df = load_project_from_excel(tmp_path)
                    return df.copy()
                except Exception:
                    pass
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

    # Fallback to projects directory
    projects_dir = "projects"
    if not os.path.exists(projects_dir):
        return None

    for filename in os.listdir(projects_dir):
        if filename.endswith(('.xlsx', '.xls')) and project_name.lower() in filename.lower():
            df = load_project_from_excel(os.path.join(projects_dir, filename))
            return df.copy()
    return None

def build_category_chart_data(projects):
    """Build normalized category performance rows for bar charts."""
    rows = []
    for project in projects:
        project_name = project.get('project_name', 'Unknown')
        for cat, score in project.get('category_scores', {}).items():
            normalized = normalize_rag_status(score)
            if not normalized:
                continue
            rows.append({
                'Project': project_name,
                'Category': cat,
                'Score': normalized,
                'Score_Value': RAG_SCORE_VALUES[normalized],
                'Bar_Label': cat if len(projects) == 1 else f"{project_name} — {cat}",
            })
    return pd.DataFrame(rows)

def get_work_tasks(df):
    """Select leaf/baseline tasks used for schedule and progress analytics."""
    if df is None or df.empty:
        return pd.DataFrame()

    tasks = df.copy()
    
    # Remove any duplicate columns that might cause issues
    tasks = tasks.loc[:, ~tasks.columns.duplicated()]
    
    if 'Baseline Finish' in tasks.columns:
        tasks['Baseline Finish'] = pd.to_datetime(tasks['Baseline Finish'], errors='coerce')
        with_baseline = tasks[tasks['Baseline Finish'].notna()]
        if not with_baseline.empty:
            tasks = with_baseline

    if 'Level' in tasks.columns:
        leaf_level = tasks['Level'].max()
        leaf_tasks = tasks[tasks['Level'] == leaf_level]
        if not leaf_tasks.empty:
            tasks = leaf_tasks

    if 'Duration' in tasks.columns:
        tasks['Duration'] = pd.to_numeric(tasks['Duration'], errors='coerce').fillna(1).clip(lower=0.1)
        tasks = tasks[tasks['Duration'] > 0]
    else:
        tasks['Duration'] = 1.0

    if 'completion_percentage' in tasks.columns:
        tasks['completion_percentage'] = pd.to_numeric(
            tasks['completion_percentage'], errors='coerce'
        ).fillna(0).clip(lower=0, upper=100)
        if tasks['completion_percentage'].max() <= 1.0:
            tasks['completion_percentage'] = tasks['completion_percentage'] * 100

    for date_col in ['Baseline Start', 'Baseline Finish', 'End Date', 'Start Date']:
        if date_col in tasks.columns:
            tasks[date_col] = pd.to_datetime(tasks[date_col], errors='coerce')

    if 'days_delayed' in tasks.columns:
        tasks['days_delayed'] = pd.to_numeric(tasks['days_delayed'], errors='coerce').fillna(0)

    return tasks

def weighted_completion(tasks):
    """Duration-weighted completion percentage."""
    if tasks is None or tasks.empty or 'completion_percentage' not in tasks.columns:
        return 0.0
    durations = tasks['Duration']
    if durations.sum() <= 0:
        return float(tasks['completion_percentage'].mean())
    return float((tasks['completion_percentage'] * durations).sum() / durations.sum())

def compute_progress_vs_target(project_name):
    """
    Build planned vs actual cumulative completion curves from baseline schedule data.
    Returns timeline labels, planned completion %, and actual completion %.
    """
    df = load_project_excel_mapped(project_name)
    if df is None or df.empty:
        return None
    tasks = get_work_tasks(df)
    if tasks.empty:
        return None

    total_duration = tasks['Duration'].sum()
    if total_duration <= 0:
        return None

    start = tasks['Baseline Start'].min() if tasks['Baseline Start'].notna().any() else tasks['Baseline Finish'].min()
    finish = tasks['Baseline Finish'].max()
    today = pd.Timestamp(datetime.now().date())

    if pd.isna(start) or pd.isna(finish) or finish <= start:
        return None

    end_point = max(finish, today)
    timeline = pd.date_range(start=start, end=end_point, freq='W-MON')
    if len(timeline) < 2:
        timeline = pd.date_range(start=start, end=end_point, freq='D')
    if timeline[-1] < end_point:
        timeline = timeline.union(pd.DatetimeIndex([end_point]))

    planned = []
    actual = []

    for point in timeline:
        planned_done = tasks.loc[tasks['Baseline Finish'] <= point, 'Duration'].sum()
        planned.append(round(planned_done / total_duration * 100, 1))

        actual_done = 0.0
        for _, row in tasks.iterrows():
            completion = row['completion_percentage'] / 100.0
            # For points before today, actual completion should be 0 (no progress yet)
            # For points after today, use current completion percentage
            if point >= today:
                actual_done += row['Duration'] * completion
            # If task is marked as complete (>=99%), use its full duration regardless of date
            elif completion >= 0.99:
                done_date = row['End Date'] if pd.notna(row.get('End Date')) else row['Baseline Finish']
                if pd.notna(done_date) and done_date <= point:
                    actual_done += row['Duration']
        actual.append(round(actual_done / total_duration * 100, 1))

    labels = [d.strftime('%b %d') for d in timeline]
    current_planned = planned[-1]
    current_actual = actual[-1]
    gap = round(current_actual - current_planned, 1)

    return {
        'labels': labels,
        'planned': planned,
        'actual': actual,
        'current_planned': current_planned,
        'current_actual': current_actual,
        'gap': gap,
        'today_label': today.strftime('%b %d'),
    }

def build_schedule_delay_data(projects):
    """Build schedule delay summary per project from Excel task data."""
    rows = []
    for project in projects:
        project_name = project.get('project_name', 'Unknown')
        tasks = get_work_tasks(load_project_excel_mapped(project_name))
        if tasks.empty:
            continue
        
        # Try to find delay data from various possible column names
        delay_col = None
        delay_cols = ['days_delayed', 'Days Delayed', 'Delay (days)', 'Variance', 'Schedule Variance']
        
        for col in delay_cols:
            if col in tasks.columns:
                delay_data = tasks[col].dropna()
                if not delay_data.empty:
                    delay_col = col
                    break
        
        if delay_col is None:
            continue
        
        # Calculate delay metrics
        delay_values = tasks[delay_col].dropna()
        max_delay = float(delay_values.abs().max())
        avg_delay = float(delay_values.abs().mean())
        
        rows.append({
            'Project': project_name,
            'Max Delay (days)': int(max_delay),
            'Avg Delay (days)': round(avg_delay, 1),
            'Completion %': round(weighted_completion(tasks), 1),
        })
    return pd.DataFrame(rows)

def build_budget_completion_data(projects):
    """Compare expected completion vs budget proxy per project."""
    rows = []
    for project in projects:
        project_name = project.get('project_name', 'Unknown')
        tasks = get_work_tasks(load_project_excel_mapped(project_name))
        if tasks.empty:
            continue
        completion = weighted_completion(tasks)
        
        # Try to get budget data from various possible column names
        budget = completion  # Default to completion if no budget data
        budget_cols = ['budget_spent_pct', 'Budget Spent %', 'Budget Spent', 'budget_spent', 'Budget Burn']
        
        for col in budget_cols:
            if col in tasks.columns:
                budget_data = tasks[col].dropna()
                if not budget_data.empty:
                    budget = float(budget_data.mean())
                    # Convert to percentage if values are <= 1
                    if budget <= 1.0 and budget_data.max() <= 1.0:
                        budget *= 100
                    break
        
        rows.append({
            'Project': project_name,
            'Completion %': round(completion, 1),
            'Budget Spent %': round(budget, 1),
            'Variance': round(budget - completion, 1),
        })
    return pd.DataFrame(rows)

def build_category_radar_data(projects):
    """Build radar chart data from category score values."""
    rows = []
    for project in projects:
        project_name = project.get('project_name', 'Unknown')
        for category in CATEGORY_ORDER:
            status = normalize_rag_status(project.get('category_scores', {}).get(category))
            if status:
                rows.append({
                    'Project': project_name,
                    'Category': category,
                    'Score': RAG_SCORE_VALUES[status],
                })
    return pd.DataFrame(rows)

def create_pie_chart(values, names, colors):
    """Create a donut chart that only includes non-zero slices."""
    filtered = [(n, v) for n, v in zip(names, values) if v > 0]
    if not filtered:
        return None

    filtered_names, filtered_values = zip(*filtered)
    fig = px.pie(
        values=list(filtered_values),
        names=list(filtered_names),
        color=list(filtered_names),
        color_discrete_map=colors,
        hole=0.4,
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=True, height=400, margin=dict(t=0, b=0, l=0, r=0))
    return fig

# Create metric card component
def create_metric_card(label, value, delta=None, help_text=None):
    """Create a styled metric card"""
    card_html = f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
    """
    if delta:
        card_html += f"<div style='color: {'green' if delta > 0 else 'red'}; font-size: 0.9rem;'>{delta:+.1f}% from last week</div>"
    if help_text:
        card_html += f"<div style='color: #999; font-size: 0.8rem; margin-top: 5px;'>{help_text}</div>"
    
    card_html += "</div>"
    st.markdown(card_html, unsafe_allow_html=True)

# Tab 1: Project Intake & Status
def project_intake_tab(projects):
    """Display project intake and status information"""
    st.subheader("Project Intake & Status")
    
    if not projects:
        st.warning("No project data available. Please run the agent first.")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Current Sprint Goals")
        for project in projects:
            with st.expander(f"{project.get('project_name', 'Unknown')}"):
                st.write(f"**Status:** {project.get('overall_status', 'Unknown')}")
                st.write(f"**Last Updated:** {project.get('timestamp', 'Unknown')}")
                st.write("**Category Scores:**")
                for cat, score in project.get('category_scores', {}).items():
                    status_class = f"status-{score.lower()}" if score.lower() in ['green', 'amber', 'red'] else ''
                    st.markdown(f"<span class='{status_class}'>{cat}: {score}</span>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("### Recent Activity")
        activity_data = [
            {"Project": p.get('project_name', 'Unknown'), "Status": p.get('overall_status', 'Unknown'), 
             "Time": p.get('timestamp', 'Unknown')[:10] if p.get('timestamp') else 'N/A'}
            for p in projects
        ]
        st.dataframe(pd.DataFrame(activity_data), width='stretch')

# Tab 2: Analytics & Velocity
def analytics_tab(projects, key_prefix="portfolio"):
    """Display analytics and velocity charts
    
    Args:
        projects: List of project dictionaries
        key_prefix: Unique prefix for chart keys to avoid duplicate element IDs
    """
    st.subheader("Portfolio Analytics & Delivery Pace")
    
    if not projects:
        st.warning("No project data available for analytics.")
        return
    
    is_single_project = len(projects) == 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### RAG Category Radar")
        df_radar = build_category_radar_data(projects)
        if not df_radar.empty:
            fig = px.line_polar(
                df_radar,
                r='Score',
                theta='Category',
                color='Project',
                line_close=True,
                range_r=[0, 3],
                category_orders={'Category': CATEGORY_ORDER},
                color_discrete_sequence=px.colors.qualitative.Set2,
                height=420,
            )
            fig.update_traces(fill='toself', opacity=0.35)
            fig.update_layout(
                polar=dict(radialaxis=dict(dtick=1, range=[0, 3], tickvals=[1, 2, 3], ticktext=['Red', 'Amber', 'Green'])),
                margin=dict(t=30, b=30, l=60, r=60),
                legend=dict(orientation='h', yanchor='bottom', y=-0.2),
            )
            st.plotly_chart(fig, width='stretch', key=f"radar_{key_prefix}")
        else:
            st.info("No category data available for radar chart.")
    
    with col2:
        st.markdown("### Key Indicators Performance")
        df_cat = build_category_chart_data(projects)

        if not df_cat.empty:
            if is_single_project:
                df_cat['Category'] = pd.Categorical(
                    df_cat['Category'],
                    categories=CATEGORY_ORDER,
                    ordered=True,
                )
                df_cat = df_cat.sort_values('Category')

                fig = px.bar(
                    df_cat,
                    x='Category',
                    y='Score_Value',
                    color='Score',
                    color_discrete_map=RAG_COLORS,
                    text='Score',
                    height=420,
                )
                fig.update_traces(textposition='outside')
                fig.update_layout(
                    xaxis_title="",
                    yaxis_title="Score (Green=3, Amber=2, Red=1)",
                    margin=dict(t=0, b=0, l=0, r=0),
                    showlegend=False,
                    yaxis=dict(range=[0, 3.5], dtick=1),
                )
            else:
                df_cat = df_cat.sort_values(['Project', 'Category'])
                fig = px.bar(
                    df_cat,
                    x='Score_Value',
                    y='Bar_Label',
                    color='Score',
                    color_discrete_map=RAG_COLORS,
                    orientation='h',
                    text='Score',
                    height=max(420, len(df_cat) * 40),
                )
                fig.update_traces(textposition='outside')
                fig.update_layout(
                    xaxis_title="Score (Green=3, Amber=2, Red=1)",
                    yaxis_title="",
                    margin=dict(t=0, b=0, l=0, r=0),
                    showlegend=False,
                    xaxis=dict(range=[0, 3.5], dtick=1),
                )

            st.plotly_chart(fig, width='stretch', key=f"category_bar_{key_prefix}")
        else:
            st.info("No category data available for visualization.")

    st.markdown("### Progress vs Target — Cumulative Completion")
    progress_col1, progress_col2 = st.columns(2)

    with progress_col1:
        for project in projects:
            project_name = project.get('project_name', 'Unknown')
            progress = compute_progress_vs_target(project_name)
            if not progress:
                st.info(f"No baseline schedule data available for {project_name}.")
                continue

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=progress['labels'],
                y=progress['planned'],
                mode='lines+markers',
                name='Planned (Baseline)',
                line=dict(color='#00B4D8', width=3),
                marker=dict(size=6),
            ))
            fig.add_trace(go.Scatter(
                x=progress['labels'],
                y=progress['actual'],
                mode='lines+markers',
                name='Actual',
                line=dict(color='#0A192F', width=3),
                marker=dict(size=6),
            ))
            # Find today's position in the labels
            today_label = progress.get('today_label', '')
            today_idx = next(
                (i for i, label in enumerate(progress['labels']) if label == today_label),
                len(progress['labels']) - 1,
            )
            fig.add_vline(
                x=today_idx,
                line_dash='dot',
                line_color='#999',
                annotation_text='Today',
            )
            fig.update_layout(
                title=f"{project_name}: Planned {progress['current_planned']}% vs Actual {progress['current_actual']}%",
                xaxis_title="Timeline",
                yaxis_title="Cumulative Completion (%)",
                height=380,
                margin=dict(t=60, b=40, l=40, r=20),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                yaxis=dict(range=[0, 105]),
            )
            st.plotly_chart(fig, width='stretch', key=f"progress_{project_name}_{key_prefix}")

            gap = progress['gap']
            if gap >= 0:
                st.success(f"**{project_name}** is **{abs(gap):.1f} pts ahead** of baseline schedule.")
            else:
                st.warning(f"**{project_name}** is **{abs(gap):.1f} pts behind** baseline — schedule recovery needed.")

    with progress_col2:
        df_delay = build_schedule_delay_data(projects)
        if not df_delay.empty:
            st.markdown("#### Schedule Delay vs Completion")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_delay['Project'],
                y=df_delay['Max Delay (days)'],
                name='Max Delay (days)',
                marker_color='#DC3545',
                text=df_delay['Max Delay (days)'],
                textposition='outside',
            ))
            fig.add_trace(go.Scatter(
                x=df_delay['Project'],
                y=df_delay['Completion %'],
                name='Completion %',
                mode='lines+markers+text',
                text=df_delay['Completion %'],
                textposition='top center',
                yaxis='y2',
                line=dict(color='#28A745', width=2),
                marker=dict(size=10),
            ))
            fig.update_layout(
                height=380,
                yaxis=dict(title='Max Delay (days)', side='left'),
                yaxis2=dict(title='Completion %', overlaying='y', side='right', range=[0, 105]),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                margin=dict(t=40, b=20, l=40, r=40),
            )
            st.plotly_chart(fig, width='stretch', key=f"delay_{key_prefix}")
        else:
            st.info("No schedule delay data available.")

        df_budget = build_budget_completion_data(projects)
        if not df_budget.empty:
            st.markdown("#### Budget vs Completion Alignment")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Completion %',
                x=df_budget['Project'],
                y=df_budget['Completion %'],
                marker_color='#00B4D8',
            ))
            fig.add_trace(go.Bar(
                name='Budget Spent %',
                x=df_budget['Project'],
                y=df_budget['Budget Spent %'],
                marker_color='#0A192F',
            ))
            fig.update_layout(
                barmode='group',
                height=320,
                yaxis=dict(title='Percentage', range=[0, 105]),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                margin=dict(t=40, b=20, l=40, r=20),
            )
            st.plotly_chart(fig, width='stretch', key=f"budget_{key_prefix}")

    if not is_single_project:
        st.markdown("### Portfolio Health Distribution")
        status_counts = {'Green': 0, 'Amber': 0, 'Red': 0}
        for project in projects:
            status = normalize_rag_status(project.get('overall_status', 'Unknown'))
            if status:
                status_counts[status] += 1

        fig = create_pie_chart(
            list(status_counts.values()),
            list(status_counts.keys()),
            RAG_COLORS,
        )
        if fig:
            st.plotly_chart(fig, width='stretch', key=f"pie_{key_prefix}")

# Tab 3: Risk Radar
def risk_radar_tab(projects):
    """Display risk radar and potential bottlenecks"""
    st.subheader("Executive Risk Dashboard")
    
    if not projects:
        st.warning("No project data available for risk analysis.")
        return
    
    # Identify risks
    risks = []
    for project in projects:
        status = project.get('overall_status', 'Unknown')
        category_scores = project.get('category_scores', {})
        
        if status == 'Red':
            risks.append({
                'Project': project.get('project_name', 'Unknown'),
                'Risk Type': 'Overall Project Health',
                'Severity': 'Critical',
                'Description': 'Project in critical condition requiring immediate intervention'
            })
        
        for category, score in category_scores.items():
            if score == 'Red':
                risks.append({
                    'Project': project.get('project_name', 'Unknown'),
                    'Risk Type': category,
                    'Severity': 'High',
                    'Description': f'Critical {category} issues detected'
                })
            elif score == 'Amber':
                risks.append({
                    'Project': project.get('project_name', 'Unknown'),
                    'Risk Type': category,
                    'Severity': 'Medium',
                    'Description': f'Warning indicators in {category}'
                })
    
    if risks:
        st.markdown("### Critical Business Risks")
        
        # Risk summary cards
        critical_count = sum(1 for r in risks if r['Severity'] == 'Critical')
        high_count = sum(1 for r in risks if r['Severity'] == 'High')
        medium_count = sum(1 for r in risks if r['Severity'] == 'Medium')
        
        col1, col2, col3 = st.columns(3)
        with col1:
            create_metric_card("Critical Risks", critical_count, help_text="Immediate attention required")
        with col2:
            create_metric_card("High Priority", high_count, help_text="Monitor closely")
        with col3:
            create_metric_card("Medium Priority", medium_count, help_text="Track progress")
        
        # Risk breakdown table
        st.markdown("### Risk Impact Analysis")
        risk_df = pd.DataFrame(risks)
        
        def color_severity(val):
            if val == 'Critical':
                return 'background-color: #FFE5E5'
            elif val == 'High':
                return 'background-color: #FFF3CD'
            else:
                return 'background-color: #E8F4F8'
        
        styled_df = risk_df.style.map(color_severity, subset=['Severity'])
        st.dataframe(styled_df, width='stretch')
        
        # Detailed risk analysis
        st.markdown("### Strategic Risk Assessment")
        for project in projects:
            if project.get('overall_status') in ['Red', 'Amber']:
                with st.expander(f"Risk Analysis: {project.get('project_name', 'Unknown')}"):
                    st.write("**Reasoning:**")
                    st.write(project.get('reasoning', 'No reasoning available'))
                    
                    st.write("**Category Details:**")
                    for cat, detail in project.get('category_details', {}).items():
                        st.write(f"- {cat}: {detail}")
    else:
        st.success("No active risks detected across all projects!")

# AI Chat Interface
def ai_chat_interface():
    """Display AI chat interface in sidebar with Gemini integration"""
    st.sidebar.markdown("### Executive Insights Assistant")
    st.sidebar.markdown("Ask questions about portfolio performance")
    
    # Initialize chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat messages
    chat_container = st.sidebar.container()
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.sidebar.chat_input("Ask about portfolio insights..."):
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.sidebar.chat_message("user"):
            st.markdown(prompt)
        
        # Generate AI response with Gemini
        with st.sidebar.chat_message("assistant"):
            with st.spinner("Analyzing project data..."):
                # Load project data for context - use session state directly for immediate access
                if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
                    # Process uploaded files directly for AI context
                    from project_health_agent import ProjectHealthAgent, load_project_from_excel

                    projects = []
                    agent = ProjectHealthAgent()

                    for uploaded_file in st.session_state.uploaded_files:
                        tmp_path = None
                        try:
                            try:
                                uploaded_file.seek(0)
                            except Exception:
                                pass
                            suffix = os.path.splitext(uploaded_file.name or '')[1] or '.xlsx'
                            with tempfile.NamedTemporaryFile(
                                delete=False,
                                suffix=suffix,
                                dir=tempfile.gettempdir(),
                                prefix='phr_chat_'
                            ) as tmp:
                                tmp.write(uploaded_file.getbuffer())
                                tmp.flush()
                                try:
                                    os.fsync(tmp.fileno())
                                except Exception:
                                    pass
                                tmp_path = tmp.name

                            df = load_project_from_excel(tmp_path)
                            if df is not None and not df.empty:
                                project_name = os.path.splitext(uploaded_file.name)[0]
                                result = agent.evaluate_project(df)
                                projects.append({
                                    'project_name': project_name,
                                    'overall_status': result.status,
                                    'reasoning': result.reasoning,
                                    'category_scores': result.category_scores,
                                    'category_details': result.details,
                                    'timestamp': datetime.now().isoformat(),
                                    'source': 'uploaded'
                                })
                        except Exception:
                            pass
                        finally:
                            if tmp_path and os.path.exists(tmp_path):
                                try:
                                    os.unlink(tmp_path)
                                except Exception:
                                    pass
                else:
                    projects = []
                
                # Build context for Gemini
                context = "PROJECT HEALTH DATA:\n"
                if projects:
                    for project in projects:
                        context += f"\nProject: {project.get('project_name', 'Unknown')}\n"
                        context += f"Status: {project.get('overall_status', 'Unknown')}\n"
                        context += f"Category Scores: {project.get('category_scores', {})}\n"
                        context += f"Reasoning: {project.get('reasoning', 'N/A')}\n"
                else:
                    context += "No project data available. Please upload Excel files using the sidebar to analyze project health.\n"
                
                # Check session state first, then environment variable
                api_key = st.session_state.get('api_key', os.getenv('GEMINI_API_KEY'))
                if api_key:
                    try:
                        ai_response, error_code = generate_portfolio_insight(prompt, context)
                        if error_code == 'missing_key':
                            ai_response = (
                                "To enable AI capabilities, set your Gemini API key in `.env` as "
                                "`GEMINI_API_KEY=your_key_here`, then restart the app."
                            )
                        elif error_code == 'model_not_found':
                            st.error("No compatible Gemini model could be reached. This usually indicates transient API instability — retry shortly.")
                            ai_response = "The AI model layer is temporarily unreachable. Please try again in a few minutes."
                        elif error_code == 'invalid_api_key':
                            st.error("Invalid Gemini API key — verify the value in Settings or paste a new key from https://aistudio.google.com/apikey")
                            ai_response = "Your API key was rejected. Please check the key in Settings > API Configuration or generate a new one."
                        elif error_code == 'quota_exceeded':
                            st.error("Gemini API quota reached. Wait 60 seconds, then retry; or enable billing for higher limits at https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com")
                            ai_response = (
                                "Request quota exhausted on the current plan. Immediate options:\n\n"
                                "1. Wait 60 seconds and retry (free-tier limits reset every minute)\n"
                                "2. Upgrade the associated Google Cloud project to a paid tier\n"
                                "3. Swap in a different API key from another Google account\n"
                            )
                        elif error_code == 'empty_response':
                            st.error("Gemini returned an empty response. Please try again.")
                            ai_response = "I couldn't generate a response this time. Please try again."
                        elif ai_response is None:
                            st.error("The insights engine is temporarily unavailable. Please try again later.")
                            ai_response = "I apologize, but I'm unable to provide insights at this moment. Please try again later."
                    except Exception as e:
                        error_msg = str(e)
                        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                            st.error("Gemini API quota exceeded. Wait a minute and retry, or review billing at https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com")
                        elif 'API_KEY' in error_msg or '401' in error_msg or '403' in error_msg or 'INVALID' in error_msg.upper():
                            st.error("Invalid Gemini API key — re-check the key in Settings or fetch a new one from https://aistudio.google.com/apikey")
                        else:
                            st.error("The insights engine hit an unexpected error.")
                            with st.expander("Technical details"):
                                st.code(error_msg)
                        ai_response = "I apologize, but I'm unable to provide insights at this moment. Please try again later."
                else:
                    ai_response = (
                        "To enable AI capabilities, set your Gemini API key:\n\n"
                        "1. Get a key from: https://aistudio.google.com/apikey\n"
                        "2. Create a `.env` file with: `GEMINI_API_KEY=your_key_here`\n"
                        "3. Restart the app\n\n"
                        f"Your question about '{prompt}' will be answered once the API is configured."
                    )
                
                st.markdown(ai_response)
        
        # Add assistant response to chat history
        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

# Main application
def main():
    """Main Streamlit application"""
    # Load custom CSS
    load_custom_css()
    
    # Header
    st.markdown("""
    <div class="header-title">Project Health Reporting Agent</div>
    <div class="header-subtitle">Smart Portfolio Insights</div>
    """, unsafe_allow_html=True)
    
    # Load project data
    projects = load_project_data()
    
    # KPI Cards
    if projects:
        total_projects = len(projects)
        green_count = sum(1 for p in projects if p.get('overall_status') == 'Green')
        amber_count = sum(1 for p in projects if p.get('overall_status') == 'Amber')
        red_count = sum(1 for p in projects if p.get('overall_status') == 'Red')
        health_metrics = compute_portfolio_health_metrics(projects)
        health_score = health_metrics['weighted']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            create_metric_card(
                "Portfolio Health Score",
                f"{health_score}%",
                help_text="Weighted score: Schedule 25%, Budget 25%, Blockages 25%, Stakeholder 25%"
            )
        with col2:
            create_metric_card("Critical Risks", red_count, help_text="Projects requiring immediate attention")
        with col3:
            create_metric_card("Urgent Escalations", amber_count, help_text="Projects needing monitoring")
        with col4:
            create_metric_card("Total Projects", total_projects, help_text="Active projects in portfolio")

        st.caption(
            f"Category rollup: {health_metrics['category_rollup']}% green parameters "
            f"({health_metrics['green_categories']}/{health_metrics['total_categories']}) · "
            f"Health index: {health_metrics['health_index']}% · "
            f"Legacy project rollup: {health_metrics['project_rollup']}% fully green projects"
        )
    else:
        st.warning("No project data available. Upload Excel files using the sidebar to analyze project health.")
    
    st.markdown("---")
    
    # Sidebar with AI chat
    with st.sidebar:
        st.markdown("### Settings")
        st.markdown("Configure your AI assistant and data sources")
        
        # API Key input
        st.markdown("### API Configuration")
        current_api_key = st.session_state.get('api_key', os.getenv('GEMINI_API_KEY', ''))
        api_key_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=current_api_key,
            help="Enter your Gemini API key for AI features",
            key="api_key_input"
        )
        
        if api_key_input and api_key_input != current_api_key:
            st.session_state.api_key = api_key_input
            st.success("API key updated successfully!")
            st.cache_data.clear()
            st.cache_resource.clear()
        elif api_key_input == '' and 'api_key' in st.session_state:
            del st.session_state.api_key
            st.info("API key removed. Using environment variable if available.")
            st.cache_data.clear()
            st.cache_resource.clear()

        active_key = st.session_state.get('api_key') or os.getenv('GEMINI_API_KEY', '')
        key_fingerprint = f"{active_key[:6]}...{active_key[-4:]}" if active_key else "none"
        with st.spinner("Checking AI connectivity..."):
            status = check_api_status(key_fingerprint)
        st.markdown("**AI Assistant Status**")
        if status["status"] == "connected":
            st.success(f"✅ {status['message']}")
        elif status["status"] == "quota_exceeded":
            st.warning("⚠️ " + status["message"])
        elif status["status"] == "invalid_key":
            st.error("❌ " + status["message"])
        elif status["status"] == "not_configured":
            st.info("ℹ️ " + status["message"])
        else:
            st.warning("⚠️ " + status["message"])
        
        st.markdown("### Upload Project Data")
        st.markdown("Upload Excel files (.xlsx, .xls) to analyze project health")
        
        uploaded_files = st.file_uploader(
            "Choose Excel files",
            type=['xlsx', 'xls'],
            accept_multiple_files=True,
            help="Upload project Excel files to generate health reports"
        )
        
        # Store uploaded files in session state
        if uploaded_files:
            # Check if files have changed
            current_files = st.session_state.get('uploaded_files', None)
            current_names = set(f.name for f in current_files) if current_files else set()
            new_names = set(f.name for f in uploaded_files)
            
            if current_names != new_names:
                st.session_state.uploaded_files = uploaded_files
                st.success(f"{len(uploaded_files)} file(s) uploaded successfully. Dashboard will update automatically.")
                # Clear all caches to ensure fresh data processing
                st.cache_data.clear()
            else:
                st.session_state.uploaded_files = uploaded_files
            
            # Show column detection for each uploaded file
            with st.expander("📋 View Detected Columns"):
                for uploaded_file in uploaded_files:
                    try:
                        import pandas as pd
                        df = pd.read_excel(uploaded_file)
                        df.columns = df.columns.str.strip()
                        st.markdown(f"**{uploaded_file.name}** - {len(df.columns)} columns detected:")
                        st.write(list(df.columns))
                    except Exception as e:
                        st.error(f"Error reading {uploaded_file.name}: {e}")
        else:
            if 'uploaded_files' not in st.session_state:
                st.session_state.uploaded_files = None
        
        st.markdown("### Data Sources")
        st.markdown("- **Upload** - Manual file upload (primary)")
        
        st.markdown("### Quick Actions")
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        
        if st.button("Generate Executive Presentation"):
            try:
                from generate_presentation import PresentationGenerator, _compute_portfolio_metrics, _clean_reasoning
                uploaded_files = st.session_state.get('uploaded_files', None)
                try:
                    generator = PresentationGenerator()
                except Exception:
                    generator = PresentationGenerator(output_dir=os.path.join(tempfile.gettempdir(), "phr_presentations"))
                projects_data = None

                if uploaded_files:
                    projects_data = generator.load_project_data(uploaded_files=uploaded_files)
                if not projects_data and projects:
                    projects_data = list(projects)
                if not projects_data:
                    projects_data = generator.load_project_data(uploaded_files=None)

                if not projects_data:
                    st.warning("No project data available — upload Excel files in the sidebar or add files to the `projects/` directory first.")
                    return

                prs = generator.create_presentation(projects_data)
                if not prs:
                    st.error("Failed to generate presentation")
                    return

                pptx_bytes, pptx_filename = generator.presentation_to_bytes(prs)
                if pptx_bytes is None:
                    st.error("Failed to serialize presentation to memory")
                    return

                filepath = generator.save_presentation(prs)
                st.success(f"Presentation generated successfully! ({len(pptx_bytes):,} bytes)")

                metrics = _compute_portfolio_metrics(projects_data)
                total_projects = metrics['total_projects']
                green_count = metrics['green_count']
                amber_count = metrics['amber_count']
                red_count = metrics['red_count']
                weighted_score = metrics['weighted_pct']
                health_index = metrics['health_index_pct']
                category_rollup = metrics['category_rollup_pct']
                project_rollup = metrics['project_rollup_pct']

                st.markdown("### Executive Presentation Preview")

                with st.expander("📊 Slide 1: Title & Overview", expanded=True):
                    st.markdown(f"### Project Health Executive Summary")
                    st.markdown(f"**Portfolio Health Score (Weighted KPI): {weighted_score}%**  ·  Health Index {health_index}%  ·  Green Parameters {category_rollup}%  ·  {datetime.now().strftime('%B %d, %Y')}")
                    st.markdown(f"_Project Rollup (fully-green projects): {project_rollup}% — {green_count}/{total_projects} projects Green, {amber_count} Amber, {red_count} Red_")

                with st.expander("📈 Slide 2: Portfolio Overview"):
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Projects", total_projects)
                    col2.metric("Weighted KPI", f"{weighted_score}%")
                    col3.metric("Green Projects", green_count, delta_color="normal")
                    col4.metric("Red Projects", red_count, delta_color="inverse")
                    colA, colB = st.columns(2)
                    colA.metric("Health Index", f"{health_index}%")
                    colB.metric("Green Parameters", f"{category_rollup}%")
                    verdict = 'HEALTHY' if weighted_score >= 75 else 'MODERATE RISK' if weighted_score >= 50 else 'HIGH RISK'
                    st.markdown(f"**Portfolio Status:** {verdict}")

                with st.expander("⚠️ Slide 3: Key Risks & Highlights"):
                    red_projects = [p for p in projects_data if (p.get('overall_status') or '').strip().title() == 'Red']
                    amber_projects = [p for p in projects_data if (p.get('overall_status') or '').strip().title() == 'Amber']
                    green_projects = [p for p in projects_data if (p.get('overall_status') or '').strip().title() == 'Green']

                    if red_projects:
                        st.error("**CRITICAL RISKS (Immediate Attention Required):**")
                        for project in red_projects:
                            st.markdown(f"• **{project.get('project_name', 'Unknown')}**: {_clean_reasoning(project.get('reasoning'))}")
                    if amber_projects:
                        st.warning("**MONITORING REQUIRED:**")
                        for project in amber_projects:
                            st.markdown(f"• **{project.get('project_name', 'Unknown')}**: {_clean_reasoning(project.get('reasoning'))}")
                    if green_projects:
                        st.success("**HIGHLIGHTS (On Track):**")
                        for project in green_projects:
                            st.markdown(f"• **{project.get('project_name', 'Unknown')}**: {_clean_reasoning(project.get('reasoning'), 120)}")
                    if not red_projects and not amber_projects and not green_projects:
                        st.info("No project data available for risk analysis.")

                with st.expander("📋 Slide 4: Project Status Details"):
                    for project in projects_data:
                        raw_status = (project.get('overall_status') or 'Unknown').strip().title()
                        status_emoji = "🟢" if raw_status == 'Green' else "🟡" if raw_status == 'Amber' else "🔴"
                        st.markdown(f"**{status_emoji} {project.get('project_name', 'Unknown')} — {raw_status}**")
                        st.markdown(f"_{_clean_reasoning(project.get('reasoning'), 260)}_")
                        category_scores = project.get('category_scores', {}) or {}
                        cat_rows = []
                        for category in ["Schedule", "Blockages", "Stakeholder Attitude", "Budget Burn"]:
                            score = (category_scores.get(category) or '').strip().title()
                            if score:
                                score_emoji = "🟢" if score == 'Green' else "🟡" if score == 'Amber' else "🔴"
                                cat_rows.append(f"{score_emoji} {category}: {score}")
                        if cat_rows:
                            st.markdown(" &nbsp; &nbsp; | &nbsp; &nbsp; ".join(cat_rows))
                        st.markdown("---")

                with st.expander("💡 Slide 5: Trends & Insights"):
                    sc = lambda s: (s or '').strip().title()
                    schedule_issues = sum(1 for p in projects_data if sc((p.get('category_scores') or {}).get('Schedule')) in ['Red', 'Amber'])
                    budget_issues = sum(1 for p in projects_data if sc((p.get('category_scores') or {}).get('Budget Burn')) in ['Red', 'Amber'])
                    blockage_issues = sum(1 for p in projects_data if sc((p.get('category_scores') or {}).get('Blockages')) in ['Red', 'Amber'])
                    stakeholder_issues = sum(1 for p in projects_data if sc((p.get('category_scores') or {}).get('Stakeholder Attitude')) in ['Red', 'Amber'])
                    st.markdown(f"**PORTFOLIO AT A GLANCE:** {total_projects} projects · Weighted KPI **{weighted_score}%** · Category Rollup **{category_rollup}%**")
                    st.markdown("**KEY OBSERVATIONS:**")
                    st.markdown(f"• Schedule: **{schedule_issues}** project(s) behind baseline. Timeline execution is the #1 driver of current RAG status.")
                    st.markdown(f"• Budget: **{budget_issues}** project(s) with burn variance — financial oversight recommended.")
                    st.markdown(f"• Blockages: **{blockage_issues}** project(s) with active blockers — verify escalation paths.")
                    st.markdown(f"• Stakeholders: **{stakeholder_issues}** project(s) with attitude flags — increase communication cadence.")
                    st.markdown("*Portfolio health is driven primarily by schedule adherence. Focus recovery first on late critical-path milestones; confirm Duration and % Complete are updated weekly.*")

                with st.expander("🎯 Slide 6: Strategic Recommendations"):
                    red_projects = [p for p in projects_data if (p.get('overall_status') or '').strip().title() == 'Red']
                    amber_projects = [p for p in projects_data if (p.get('overall_status') or '').strip().title() == 'Amber']
                    st.markdown("**IMMEDIATE ACTIONS (This Week):**")
                    if red_projects:
                        for project in red_projects:
                            st.markdown(f"• **{project.get('project_name', 'Unknown')}**: Activate recovery plan; re-plan critical-path baseline; daily stand-up until caught up.")
                    if amber_projects:
                        for project in amber_projects:
                            st.markdown(f"• **{project.get('project_name', 'Unknown')}**: Add schedule buffer to slipping milestones; confirm stakeholder commitment.")
                    if not red_projects and not amber_projects:
                        st.markdown("• Continue current practices — portfolio is healthy.")
                    st.markdown("**ONGOING MONITORING:**")
                    st.markdown("• Weekly health reviews with updated Duration, % Complete, and Start/End dates")
                    st.markdown("• Proactive stakeholder communication for Amber/Red projects (bi-weekly minimum)")
                    st.markdown("• Resource allocation adjustments based on schedule priority and baseline gaps")

                with st.expander("📅 Slide 7: Next Steps"):
                    st.markdown("**IMMEDIATE (This Week):**")
                    st.markdown("• Review critical project recovery plans for Red items")
                    st.markdown("• Schedule stakeholder update meetings for Amber/Red projects")
                    st.markdown("")
                    st.markdown("**SHORT-TERM (Next 2 Weeks):**")
                    st.markdown("• Implement interventions from Recommendations")
                    st.markdown("• Monitor progress on action items and publish a weekly delta")
                    st.markdown("• Re-run the health agent with updated task data and refresh the presentation")
                    st.markdown("")
                    followup = (datetime.fromtimestamp(datetime.now().timestamp() + 7 * 24 * 3600)).strftime('%B %d, %Y')
                    st.markdown(f"*Follow-up presentation scheduled for: {followup}*")

                st.markdown("---")
                try:
                    st.download_button(
                        label="📥 Download Full PowerPoint Presentation",
                        data=pptx_bytes,
                        file_name=pptx_filename,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        key="pptx_download_main_v3"
                    )
                except Exception as de:
                    # Fallback: try reading from disk if bytes path failed unexpectedly
                    if filepath and os.path.exists(filepath):
                        try:
                            with open(filepath, 'rb') as f:
                                st.download_button(
                                    label="📥 Download Full PowerPoint Presentation (Fallback)",
                                    data=f.read(),
                                    file_name=os.path.basename(filepath),
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                    key="pptx_download_fallback_v3"
                                )
                        except Exception:
                            st.info(f"Presentation ready on server at: `{filepath}`")
                    else:
                        st.info("Presentation generated in memory — please use the download button above.")

            except Exception as e:
                st.error(f"Error generating presentation: {e}")
                import traceback
                with st.expander("Technical details"):
                    st.code(traceback.format_exc())
    
    # AI Chat Interface
    ai_chat_interface()
    
    # Main content - tab-based navigation
    if projects:
        # Create tabs for Portfolio Overview and Individual Project Assessment
        tab1, tab2 = st.tabs(["Portfolio Overview", "Individual Project Assessment"])
        
        with tab1:
            # Portfolio Overview - show all projects together
            st.subheader("Portfolio Overview")
            
            # Show overall KPI cards
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                create_metric_card(
                    "Portfolio Health Score",
                    f"{health_score}%",
                    help_text="Weighted score: Schedule 25%, Budget 25%, Blockages 25%, Stakeholder 25%"
                )
            with col2:
                create_metric_card("Critical Risks", red_count, help_text="Projects requiring immediate attention")
            with col3:
                create_metric_card("Urgent Escalations", amber_count, help_text="Projects needing monitoring")
            with col4:
                create_metric_card("Total Projects", total_projects, help_text="Active projects in portfolio")

            # Additional metrics in separate boxes
            col5, col6, col7 = st.columns(3)
            with col5:
                create_metric_card(
                    "Category Rollup",
                    f"{health_metrics['category_rollup']}%",
                    help_text=f"Green parameters: {health_metrics['green_categories']}/{health_metrics['total_categories']}"
                )
            with col6:
                create_metric_card(
                    "Health Index",
                    f"{health_metrics['health_index']}%",
                    help_text="Overall portfolio health index"
                )
            with col7:
                create_metric_card(
                    "Fully Green Projects",
                    f"{health_metrics['project_rollup']}%",
                    help_text="Projects with all green categories"
                )
            
            st.markdown("---")
            
            # Show all projects in a consolidated view
            st.subheader("All Projects Summary")
            for project in projects:
                with st.expander(f"{project.get('project_name', 'Unknown')} - {project.get('overall_status', 'Unknown')}"):
                    st.write(f"**Status:** {project.get('overall_status', 'Unknown')}")
                    st.write(f"**Last Updated:** {project.get('timestamp', 'Unknown')}")
                    st.write("**Category Scores:**")
                    for cat, score in project.get('category_scores', {}).items():
                        status_class = f"status-{score.lower()}" if score.lower() in ['green', 'amber', 'red'] else ''
                        st.markdown(f"<span class='{status_class}'>{cat}: {score}</span>", unsafe_allow_html=True)
                    st.write("**Reasoning:**")
                    st.write(project.get('reasoning', 'No reasoning available'))
            
            # Analytics for all projects
            st.markdown("---")
            analytics_tab(projects, key_prefix="portfolio")
            
            # Risk radar for all projects
            st.markdown("---")
            risk_radar_tab(projects)
        
        with tab2:
            # Individual Project Assessment - show single project with all features
            project_names = [p.get('project_name', 'Unknown') for p in projects]
            selected_project_name = st.selectbox("Select Project", project_names)
            
            # Get selected project data
            selected_project = next((p for p in projects if p.get('project_name') == selected_project_name), None)
            
            if selected_project:
                st.subheader(f"Project: {selected_project_name}")
                
                # Project-specific KPI cards

                project_status = selected_project.get('overall_status', 'Unknown')
                category_scores = selected_project.get('category_scores', {})
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    create_metric_card("Overall Status", project_status, help_text="Project health status")
                with col2:
                    create_metric_card("Last Updated", selected_project.get('timestamp', 'Unknown')[:10] if selected_project.get('timestamp') else 'N/A', help_text="Report generation date")
                with col3:
                    create_metric_card("Categories Evaluated", len(category_scores), help_text="Number of RAG categories")
                
                st.markdown("---")
                
                # Category breakdown
                st.subheader("Category Breakdown")
                for cat, score in category_scores.items():
                    status_class = f"status-{score.lower()}" if score.lower() in ['green', 'amber', 'red'] else ''
                    st.markdown(f"<span class='{status_class}'>{cat}: {score}</span>", unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Analytics for single project
                st.subheader("Analytics for This Project")
                analytics_tab([selected_project], key_prefix=f"single_{selected_project_name}")
                
                st.markdown("---")
                
                # Risk radar for single project
                st.subheader("Risk Analysis for This Project")
                risk_radar_tab([selected_project])
                
                st.markdown("---")
                
                # Executive Summary (AI-generated insights)
                st.markdown("---")
                st.subheader("Executive Summary")
                st.write("**Reasoning:**")
                st.write(selected_project.get('reasoning', 'No reasoning available'))
                
                # Detailed Analysis and Root Cause in expander
                with st.expander("View Data Telemetry & Raw Metrics"):
                    # Category details if available
                    if selected_project.get('category_details'):
                        st.write("**Category Details:**")
                        for cat, detail in selected_project.get('category_details', {}).items():
                            st.write(f"- {cat}: {detail}")
                    
                    st.markdown("---")
                    
                    # Root Cause Analysis
                    st.subheader("Root Cause Analysis - Driving Factors")
                    st.markdown("Below shows the actual data that triggered the current status:")
                    
                    # Load raw Excel data
                    raw_data = load_raw_excel_data(selected_project_name)
                    
                    if raw_data is not None:
                        # Show the raw data
                        st.markdown("**Complete Excel Data:**")
                        st.dataframe(raw_data, width='stretch', height=300)
                        
                        # Highlight specific issues based on category scores
                        st.markdown("**Issues Identified in Excel Data:**")
                        
                        category_scores = selected_project.get('category_scores', {})
                        
                        if category_scores.get('Schedule') in ['Red', 'Amber']:
                            st.markdown(f"🔴 **Schedule ({category_scores.get('Schedule')})**: Check 'Variance' or 'days_delayed' columns for delays > 10 days (Red) or 0-10 days (Amber)")
                        
                        if category_scores.get('Blockages') in ['Red', 'Amber']:
                            st.markdown(f"🔴 **Blockages ({category_scores.get('Blockages')})**: Check 'At Risk?' column - 'Yes' indicates Red status")
                        
                        if category_scores.get('Stakeholder Attitude') in ['Red', 'Amber']:
                            st.markdown(f"🔴 **Stakeholder Attitude ({category_scores.get('Stakeholder Attitude')})**: Check 'Comments' or 'Status Comment' columns for negative keywords")
                        
                        if category_scores.get('Budget Burn') in ['Red', 'Amber']:
                            st.markdown(f"🔴 **Budget Burn ({category_scores.get('Budget Burn')})**: Check budget variance - >15% over expected is Red, 5-15% is Amber")
                        
                        # Show specific columns that matter
                        st.markdown("**Key Columns to Check:**")
                        important_cols = ['Task Name', 'At Risk?', 'Status', '% Complete', 'Variance', 'Comments', 'Status Comment']
                        available_cols = [col for col in important_cols if col in raw_data.columns]
                        
                        if available_cols:
                            st.dataframe(raw_data[available_cols], width='stretch', height=200)
                        else:
                            st.info("No standard column names found. Showing all columns above.")
                    else:
                        st.warning("Could not load raw Excel data for this project. Make sure the Excel file exists in the 'projects' directory.")
    else:
        # Fallback if no projects
        tab1, tab2, tab3 = st.tabs(["Project Intake & Status", "Analytics & Velocity", "Risk Radar"])
        
        with tab1:
            project_intake_tab(projects)
        
        with tab2:
            analytics_tab(projects, key_prefix="fallback")
        
        with tab3:
            risk_radar_tab(projects)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
    Project Health Reporting Agent | Smart Portfolio Insights
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
