"""
Project Health Reporting Agent
Determines RAG (Red/Amber/Green) status for project plans based on predefined methodology.
"""

import pandas as pd
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class RAGStatus:
    """Data class to hold RAG evaluation results"""
    status: str  # "Red", "Amber", "Green"
    reasoning: str
    category_scores: Dict[str, str]
    details: Dict[str, str]


class ProjectHealthAgent:
    """AI Agent for evaluating project health using RAG methodology"""
    
    def __init__(self):
        self.categories = ["Schedule", "Blockages", "Stakeholder Attitude", "Budget Burn"]
    
    def evaluate_project(self, project_data: pd.DataFrame) -> RAGStatus:
        """
        Evaluate a single project and return RAG status with reasoning.
        
        Args:
            project_data: DataFrame containing project plan data
            
        Returns:
            RAGStatus object with overall status and detailed reasoning
        """
        category_scores = {}
        category_reasoning = {}
        
        # Evaluate each category
        category_scores["Schedule"], category_reasoning["Schedule"] = self._evaluate_schedule(project_data)
        category_scores["Blockages"], category_reasoning["Blockages"] = self._evaluate_blockages(project_data)
        category_scores["Stakeholder Attitude"], category_reasoning["Stakeholder Attitude"] = self._evaluate_stakeholder_attitude(project_data)
        category_scores["Budget Burn"], category_reasoning["Budget Burn"] = self._evaluate_budget_burn(project_data)
        
        # Determine overall status using worst-case principle
        overall_status = self._determine_overall_status(category_scores)
        
        # Generate comprehensive reasoning
        reasoning = self._generate_reasoning(overall_status, category_scores, category_reasoning)
        
        return RAGStatus(
            status=overall_status,
            reasoning=reasoning,
            category_scores=category_scores,
            details=category_reasoning
        )
    
    def _get_schedule_tasks(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return the most relevant task rows for schedule/completion analysis."""
        tasks = data.copy()

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

        return tasks

    def _weighted_completion(self, data: pd.DataFrame) -> float:
        """Calculate duration-weighted completion percentage."""
        if 'completion_percentage' not in data.columns or data.empty:
            return 0.0

        completions = data['completion_percentage'].fillna(0).clip(lower=0, upper=100)
        if 'Duration' in data.columns:
            durations = pd.to_numeric(data['Duration'], errors='coerce').fillna(1).clip(lower=0.1)
            if durations.sum() > 0:
                return float((completions * durations).sum() / durations.sum())

        return float(completions.mean())

    def _evaluate_schedule(self, data: pd.DataFrame) -> Tuple[str, str]:
        """
        Evaluate schedule health based on delay days, completion progress, and baseline deviation.
        
        Returns:
            Tuple of (status, reasoning)
        """
        schedule_tasks = self._get_schedule_tasks(data)

        # Check for missing data
        if 'days_delayed' not in schedule_tasks.columns or schedule_tasks['days_delayed'].isna().all():
            return "Amber", "Schedule data is missing - requires manual review"
        
        # Get the maximum delay across relevant tasks
        max_delay = schedule_tasks['days_delayed'].fillna(0).max()
        
        # Check for critical milestone delays
        critical_milestone_delay = 0
        if 'is_critical_milestone' in schedule_tasks.columns:
            critical_data = schedule_tasks[schedule_tasks['is_critical_milestone'] == True]
            if not critical_data.empty:
                critical_milestone_delay = critical_data['days_delayed'].fillna(0).max()
        
        avg_completion = self._weighted_completion(schedule_tasks)
        
        # Calculate baseline completion if available
        baseline_completion = None
        if 'Baseline Finish' in schedule_tasks.columns and 'Baseline Start' in schedule_tasks.columns:
            schedule_tasks['Baseline Finish'] = pd.to_datetime(schedule_tasks['Baseline Finish'], errors='coerce')
            schedule_tasks['Baseline Start'] = pd.to_datetime(schedule_tasks['Baseline Start'], errors='coerce')
            
            # Calculate expected completion based on current date vs baseline timeline
            from datetime import datetime
            today = pd.Timestamp(datetime.now().date())
            
            # Get project timeline
            project_start = schedule_tasks['Baseline Start'].min()
            project_finish = schedule_tasks['Baseline Finish'].max()
            
            if pd.notna(project_start) and pd.notna(project_finish) and project_finish > project_start:
                total_duration = (project_finish - project_start).days
                if total_duration > 0:
                    elapsed = (today - project_start).days
                    baseline_completion = min(100, max(0, (elapsed / total_duration) * 100))
                    
                    # Calculate deviation from baseline
                    if baseline_completion > 0:
                        deviation = baseline_completion - avg_completion
                        # Flag if deviation is significant (>25% for Red, 10-25% for Amber)
                        if deviation > 25:
                            return "Red", (
                                f"Project is {deviation:.1f}% behind baseline schedule "
                                f"(expected {baseline_completion:.1f}%, actual {avg_completion:.1f}%). "
                                f"Critical schedule recovery required."
                            )
                        elif deviation > 5:
                            return "Amber", (
                                f"Project is {deviation:.1f}% behind baseline schedule "
                                f"(expected {baseline_completion:.1f}%, actual {avg_completion:.1f}%). "
                                f"Schedule attention needed."
                            )

        # Original delay-based logic as fallback
        if max_delay > 5 and avg_completion < 5:
            return "Red", (
                f"Project is {max_delay:.0f} days behind schedule with minimal progress "
                f"({avg_completion:.1f}% complete). Critical intervention required."
            )
        if max_delay > 10 or critical_milestone_delay > 10:
            return "Red", f"Project is {max_delay:.0f} days behind schedule. Critical milestones are delayed."
        if max_delay > 0 or critical_milestone_delay > 0:
            return "Amber", (
                f"Project is {max_delay:.0f} days behind schedule "
                f"({avg_completion:.1f}% complete), within acceptable margin."
            )
        return "Green", f"Project is on time with {avg_completion:.1f}% complete."
    
    def _evaluate_blockages(self, data: pd.DataFrame) -> Tuple[str, str]:
        """
        Evaluate blockages based on 'At Risk' column and comments.
        
        Returns:
            Tuple of (status, reasoning)
        """
        # Check for At Risk column
        if 'at_risk' not in data.columns:
            # Check comments for blockage keywords
            if 'comments' in data.columns and not data['comments'].isna().all().all():
                comments = ' '.join(data['comments'].fillna('').astype(str).values.flatten()).lower()
                if any(word in comments for word in ['blocked', 'blocker', 'stuck', 'waiting']):
                    return "Amber", "Minor blockages identified in comments - requires attention"
            return "Green", "No explicit blockage indicators found"
        
        at_risk_values = data['at_risk'].fillna('No').astype(str).str.lower()
        
        # Check for Yes in at_risk
        if 'yes' in at_risk_values.values:
            return "Red", "Major obstacles identified - project is at risk with impossible-to-solve blockages"
        
        # Check for minor blockages in comments
        if 'comments' in data.columns and not data['comments'].isna().all().all():
            comments = ' '.join(data['comments'].fillna('').astype(str).values.flatten()).lower()
            if any(word in comments for word in ['blocked', 'blocker', 'stuck', 'waiting']):
                return "Amber", "Minor blockages exist despite 'At Risk' being No"
        
        return "Green", "No blockages identified - project running smoothly"
    
    def _evaluate_stakeholder_attitude(self, data: pd.DataFrame) -> Tuple[str, str]:
        """
        Evaluate stakeholder attitude based on comments.
        
        Returns:
            Tuple of (status, reasoning)
        """
        if 'comments' not in data.columns or data['comments'].isna().all().all():
            return "Green", "No comments - no news is good news"
        
        # Combine all comments
        all_comments = ' '.join(data['comments'].fillna('').astype(str).values.flatten()).lower()
        
        if not all_comments.strip():
            return "Green", "No comments - no news is good news"
        
        # Red indicators (major dissatisfaction, serious problems)
        red_indicators = [
            'angry', 'furious', 'unacceptable', 'disappointed', 'failure',
            'catastrophe', 'disaster', 'serious concern', 'major issue',
            'escalated', 'executive concern', 'legal threat'
        ]
        
        # Amber indicators (mild unhappiness, worry, requests for help)
        amber_indicators = [
            'concern', 'worried', 'help needed', 'assistance required',
            'slipping', 'risk', 'challenge', 'difficult',
            'please review', 'need support', 'struggling'
        ]
        
        # Green indicators (good news)
        green_indicators = [
            'great', 'excellent', 'happy', 'satisfied', 'on track',
            'progress', 'success', 'well done', 'good job'
        ]
        
        # Check for red indicators first
        for indicator in red_indicators:
            if indicator in all_comments:
                return "Red", f"Major stakeholder dissatisfaction detected: '{indicator}' indicates serious problems"
        
        # Check for amber indicators
        amber_found = []
        for indicator in amber_indicators:
            if indicator in all_comments:
                amber_found.append(indicator)
        
        if amber_found:
            return "Amber", f"Stakeholder concerns detected: {', '.join(amber_found[:3])} indicates need for attention"
        
        # Check for green indicators
        for indicator in green_indicators:
            if indicator in all_comments:
                return "Green", f"Positive stakeholder sentiment: '{indicator}' indicates satisfaction"
        
        # Default to green if no negative indicators
        return "Green", "No negative sentiment detected in comments"
    
    def _evaluate_budget_burn(self, data: pd.DataFrame) -> Tuple[str, str]:
        """
        Evaluate budget burn rate against completion percentage.
        
        Returns:
            Tuple of (status, reasoning)
        """
        # Check for required columns
        budget_col = 'budget_spent_pct' if 'budget_spent_pct' in data.columns else 'budget_spent'
        if budget_col not in data.columns or 'completion_percentage' not in data.columns:
            return "Amber", "Budget data incomplete - requires manual review"
        
        schedule_tasks = self._get_schedule_tasks(data)
        avg_completion = self._weighted_completion(schedule_tasks)
        
        # Flag stalled projects (very low completion) - don't auto-Green just because no money spent
        if avg_completion < 5:
            return "Red", (
                f"Project is stalled at {avg_completion:.1f}% completion. "
                f"Budget alignment cannot be assessed for non-started projects. "
                f"Immediate project kickoff required."
            )
        
        # Avoid division by zero
        if avg_completion == 0:
            return "Amber", "Cannot calculate budget efficiency - no completion data"
        
        # Calculate expected spend vs actual using duration-weighted completion
        expected_spend_percentage = avg_completion
        
        budget_tasks = self._get_schedule_tasks(data)
        if budget_col not in budget_tasks.columns:
            return "Amber", "Budget data incomplete - requires manual review"

        actual_spend_percentage = float(budget_tasks[budget_col].fillna(0).mean())
        if actual_spend_percentage <= 1.0 and budget_tasks[budget_col].max() <= 1.0:
            actual_spend_percentage *= 100

        variance_percentage = ((actual_spend_percentage - expected_spend_percentage) / expected_spend_percentage) * 100

        if variance_percentage > 15:
            return "Red", f"Budget overspend is {variance_percentage:.1f}% - highly excessive spending"
        elif variance_percentage > 5:
            return "Amber", f"Budget overspend is {variance_percentage:.1f}% - slightly high but within margin"
        elif variance_percentage < -5:
            return "Green", f"Spending is {abs(variance_percentage):.1f}% under expected - good budget management"
        else:
            return "Green", "Spending aligns perfectly with project completion level"
    
    def _determine_overall_status(self, category_scores: Dict[str, str]) -> str:
        """
        Determine overall status using worst-case principle.
        
        Args:
            category_scores: Dictionary of category statuses
            
        Returns:
            Overall status string
        """
        # If any category is Red, overall is Red
        if any(score == "Red" for score in category_scores.values()):
            return "Red"
        
        # If any category is Amber (and no Reds), overall is Amber
        if any(score == "Amber" for score in category_scores.values()):
            return "Amber"
        
        # Only Green if all categories are Green
        return "Green"
    
    def _generate_reasoning(self, overall_status: str, category_scores: Dict[str, str], 
                           category_reasoning: Dict[str, str]) -> str:
        """
        Generate plain-English reasoning for the overall status using LLM synthesis.
        
        Args:
            overall_status: The determined overall status
            category_scores: Dictionary of category statuses
            category_reasoning: Dictionary of category reasonings
            
        Returns:
            Comprehensive reasoning string
        """
        # Try to use LLM for nuanced analysis
        ai_reasoning = self._generate_ai_reasoning(overall_status, category_scores, category_reasoning)
        
        if ai_reasoning:
            return ai_reasoning
        
        # Fallback to rule-based reasoning if LLM fails
        reasoning_parts = []
        
        # Start with overall status
        reasoning_parts.append(f"**Overall Status: {overall_status}**\n")
        
        # Add reasoning for each category that's not Green
        for category in self.categories:
            status = category_scores[category]
            detail = category_reasoning[category]
            
            if status != "Green":
                reasoning_parts.append(f"• {category}: {status} - {detail}")
            else:
                reasoning_parts.append(f"• {category}: {status}")
        
        # Add summary based on overall status
        if overall_status == "Red":
            reasoning_parts.append("\n**Summary**: Critical issues detected requiring immediate intervention. At least one category shows Red status, indicating significant risk to project success.")
        elif overall_status == "Amber":
            reasoning_parts.append("\n**Summary**: Warning indicators present that require attention. No critical failures, but proactive management needed to prevent escalation.")
        else:
            reasoning_parts.append("\n**Summary**: Project is healthy across all dimensions. Continue current practices with regular monitoring.")
        
        return "\n".join(reasoning_parts)
    
    def _generate_ai_reasoning(self, overall_status: str, category_scores: Dict[str, str], 
                              category_reasoning: Dict[str, str]) -> str:
        """
        Generate nuanced AI-powered reasoning using LLM synthesis.
        
        Args:
            overall_status: The determined overall status
            category_scores: Dictionary of category statuses
            category_reasoning: Dictionary of category reasonings
            
        Returns:
            AI-generated reasoning string or None if LLM unavailable
        """
        # AI enhancement temporarily disabled due to API model detection issues
        # System falls back to rule-based reasoning which is working correctly
        return None
    
    def evaluate_multiple_projects(self, projects: Dict[str, pd.DataFrame]) -> Dict[str, RAGStatus]:
        """
        Evaluate multiple projects and return their RAG statuses.
        
        Args:
            projects: Dictionary mapping project names to their DataFrames
            
        Returns:
            Dictionary mapping project names to their RAGStatus objects
        """
        results = {}
        for project_name, project_data in projects.items():
            results[project_name] = self.evaluate_project(project_data)
        return results


def load_project_from_csv(file_path: str) -> pd.DataFrame:
    """Load project data from CSV file."""
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return pd.DataFrame()


def load_project_from_excel(file_path: str) -> pd.DataFrame:
    """Load project data from Excel file and map columns to expected format."""
    try:
        # Try reading the first sheet, if that fails try all sheets to find data
        try:
            df = pd.read_excel(file_path)
        except Exception:
            df = pd.DataFrame()

        # If first sheet is empty or has very few columns, try other sheets
        if df.empty or len(df.columns) < 3:
            sheet_names = []
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                sheet_names = list(wb.sheetnames)
                try:
                    wb.close()
                except Exception:
                    pass
            except Exception:
                sheet_names = []

            for sheet_name in sheet_names[1:]:  # Skip first sheet we already tried
                try:
                    df_candidate = pd.read_excel(file_path, sheet_name=sheet_name)
                    if df_candidate is not None and not df_candidate.empty and len(df_candidate.columns) >= 3:
                        df = df_candidate
                        break
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading Excel workbook {file_path}: {e}")
        return pd.DataFrame()

    try:
        if df is None:
            return pd.DataFrame()

        # Clean column names - strip whitespace, handle variations
        df.columns = df.columns.str.strip()
        
        # Handle duplicate baseline columns - prioritize standard names
        baseline_start_cols = [col for col in df.columns if 'baseline start' in col.lower()]
        baseline_finish_cols = [col for col in df.columns if 'baseline finish' in col.lower() or 'baseline end' in col.lower()]
        
        # Keep only the most standard column names, drop duplicates
        if len(baseline_start_cols) > 1:
            # Keep the one that's exactly "Baseline Start" if it exists
            if 'Baseline Start' in baseline_start_cols:
                for col in baseline_start_cols:
                    if col != 'Baseline Start':
                        df = df.drop(columns=[col])
            else:
                # Otherwise keep the first one and drop the rest
                for col in baseline_start_cols[1:]:
                    df = df.drop(columns=[col])
        
        if len(baseline_finish_cols) > 1:
            # Keep the one that's exactly "Baseline Finish" if it exists
            if 'Baseline Finish' in baseline_finish_cols:
                for col in baseline_finish_cols:
                    if col != 'Baseline Finish':
                        df = df.drop(columns=[col])
            else:
                # Otherwise keep the first one and drop the rest
                for col in baseline_finish_cols[1:]:
                    df = df.drop(columns=[col])
        
        # Enhanced column mapping with more variations
        column_mapping = {
            # Task name variations
            'Task Name': 'task_name',
            'Task': 'task_name',
            'Activity': 'task_name',
            'Activity Name': 'task_name',
            'Work Package': 'task_name',
            'Description': 'task_name',
            
            # At risk variations
            'At Risk?': 'at_risk',
            'At Risk': 'at_risk',
            'Risk': 'at_risk',
            'Risk Level': 'at_risk',
            'Status Risk': 'at_risk',
            
            # Comments variations
            'Comments': 'comments',
            'Comment': 'comments',
            'Notes': 'comments',
            'Status Comment': 'comments',
            'Remarks': 'comments',
            'Description': 'comments',
            
            # Completion percentage variations
            '% Complete': 'completion_percentage',
            '% Complete': 'completion_percentage',
            'Percent Complete': 'completion_percentage',
            'Completion': 'completion_percentage',
            'Complete': 'completion_percentage',
            'Progress': 'completion_percentage',
            '% Done': 'completion_percentage',
            'Done': 'completion_percentage',
            
            # Critical milestone variations
            'Critical ?': 'is_critical_milestone',
            'Critical': 'is_critical_milestone',
            'Critical Milestone': 'is_critical_milestone',
            'Milestone': 'is_critical_milestone',
            'Key Milestone': 'is_critical_milestone',
            
            # Variance/delay variations
            'Variance': 'variance',
            'Variance2': 'variance',
            'Delay': 'variance',
            'Schedule Variance': 'variance',
            'Days Delayed': 'variance',
            'Delay (days)': 'variance',
            'Slip': 'variance',
            
            # Float variations
            'Total Float': 'total_float',
            'Float': 'total_float',
            'Slack': 'total_float',
            
            # Date variations
            'Start Date': 'Baseline Start',
            'Baseline Start': 'Baseline Start',
            'Start': 'Baseline Start',
            'Planned Start': 'Baseline Start',
            
            'End Date': 'Baseline Finish',
            'Baseline Finish': 'Baseline Finish',
            'Finish': 'Baseline Finish',
            'Planned Finish': 'Baseline Finish',
            'Target Finish': 'Baseline Finish',
            
            # Duration variations
            'Duration': 'Duration',
            'Planned Duration': 'Duration',
            'Original Duration': 'Duration',
            
            # Budget variations
            'Budget': 'budget_spent_pct',
            'Budget Spent': 'budget_spent_pct',
            'Budget Spent %': 'budget_spent_pct',
            'Cost': 'budget_spent_pct',
            'Actual Cost': 'budget_spent_pct',
            'Budget Burn': 'budget_spent_pct',
            'Spend': 'budget_spent_pct',
        }
        
        # Rename columns (handle duplicates by only keeping first match for each target)
        rename_map = {}
        mapped_targets = set()
        for src, dst in column_mapping.items():
            if src in df.columns and dst not in mapped_targets:
                rename_map[src] = dst
                mapped_targets.add(dst)
            elif src in df.columns and dst in mapped_targets:
                # If target already mapped, keep original column name to avoid duplicates
                pass
        
        df = df.rename(columns=rename_map)
        
        # Remove any duplicate columns that might have been created
        df = df.loc[:, ~df.columns.duplicated()]
        
        # Extract days_delayed from variance column if available
        if 'variance' in df.columns:
            def extract_days(variance):
                if isinstance(variance, pd.Series):
                    try:
                        variance = variance.iloc[0]
                    except Exception:
                        variance = 0
                if pd.isna(variance):
                    return 0
                variance_str = str(variance)
                match = re.search(r'(-?\d+)', variance_str)
                if match:
                    try:
                        return int(match.group(1))
                    except (ValueError, TypeError):
                        return 0
                return 0

            try:
                df['days_delayed'] = df['variance'].apply(extract_days)
            except Exception:
                df['days_delayed'] = 0

        # Ensure days_delayed exists even if variance wasn't available
        if 'days_delayed' not in df.columns:
            df['days_delayed'] = 0

        # Standardize days_delayed to numeric with sane defaults
        try:
            df['days_delayed'] = pd.to_numeric(df['days_delayed'], errors='coerce').fillna(0).astype(int)
        except Exception:
            df['days_delayed'] = 0
        
        # Ensure at_risk is standardized
        if 'at_risk' in df.columns:
            df['at_risk'] = df['at_risk'].fillna('No').astype(str).str.lower()
        
        # Ensure completion_percentage is numeric and on 0-100 scale
        if 'completion_percentage' in df.columns:
            df['completion_percentage'] = pd.to_numeric(df['completion_percentage'], errors='coerce').fillna(0)
            if df['completion_percentage'].max() <= 1.0:
                df['completion_percentage'] = df['completion_percentage'] * 100
        
        # Ensure is_critical_milestone is boolean
        if 'is_critical_milestone' in df.columns:
            df['is_critical_milestone'] = df['is_critical_milestone'].fillna(False).astype(bool)
        
        # Add budget_spent_pct if not present (set to completion_percentage as proxy)
        if 'budget_spent_pct' not in df.columns and 'completion_percentage' in df.columns:
            df['budget_spent_pct'] = df['completion_percentage']
        
        return df
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    # Example usage
    agent = ProjectHealthAgent()
    
    # This would be used with actual project data
    print("Project Health Reporting Agent initialized")
    print("Load project data and call agent.evaluate_project() to analyze")
