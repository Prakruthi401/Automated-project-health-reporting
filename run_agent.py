"""
Run the Project Health Agent on project plans and generate weekly outputs.
"""

import os
import json
from datetime import datetime
from project_health_agent import ProjectHealthAgent, load_project_from_csv, load_project_from_excel


def generate_weekly_report(projects_dir: str, output_dir: str):
    """
    Generate weekly RAG reports for all projects in the directory.
    
    Args:
        projects_dir: Directory containing project CSV files
        output_dir: Directory to save output reports
    """
    # Initialize agent
    agent = ProjectHealthAgent()
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load all project files
    projects = {}
    for filename in os.listdir(projects_dir):
        if filename.endswith('.csv'):
            project_name = filename.replace('.csv', '')
            file_path = os.path.join(projects_dir, filename)
            projects[project_name] = load_project_from_csv(file_path)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            project_name = filename.replace('.xlsx', '').replace('.xls', '')
            file_path = os.path.join(projects_dir, filename)
            projects[project_name] = load_project_from_excel(file_path)
    
    if not projects:
        print(f"No CSV or Excel files found in {projects_dir}")
        return {}
    
    # Evaluate all projects
    results = agent.evaluate_multiple_projects(projects)
    
    # Generate timestamp for this report
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Save individual project reports
    for project_name, rag_status in results.items():
        report = {
            "project_name": project_name,
            "timestamp": timestamp,
            "overall_status": rag_status.status,
            "reasoning": rag_status.reasoning,
            "category_scores": rag_status.category_scores,
            "category_details": rag_status.details
        }
        
        # Save as JSON
        output_file = os.path.join(output_dir, f"{project_name}_{timestamp}.json")
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save as readable text
        text_file = os.path.join(output_dir, f"{project_name}_{timestamp}.txt")
        with open(text_file, 'w') as f:
            f.write(f"Project Health Report: {project_name}\n")
            f.write(f"Generated: {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            f.write(rag_status.reasoning)
    
    # Generate summary report
    summary_file = os.path.join(output_dir, f"summary_{timestamp}.txt")
    with open(summary_file, 'w') as f:
        f.write("Weekly Project Health Summary\n")
        f.write(f"Generated: {timestamp}\n")
        f.write("=" * 60 + "\n\n")
        
        for project_name, rag_status in results.items():
            f.write(f"{project_name}: {rag_status.status}\n")
            for category, score in rag_status.category_scores.items():
                f.write(f"  - {category}: {score}\n")
            f.write("\n")
        
        # Count statuses
        status_counts = {"Red": 0, "Amber": 0, "Green": 0}
        for rag_status in results.values():
            status_counts[rag_status.status] += 1
        
        f.write("\nSummary:\n")
        f.write(f"  Red Projects: {status_counts['Red']}\n")
        f.write(f"  Amber Projects: {status_counts['Amber']}\n")
        f.write(f"  Green Projects: {status_counts['Green']}\n")
    
    print(f"Weekly reports generated in: {output_dir}")
    print(f"Total projects evaluated: {len(results)}")
    return results


if __name__ == "__main__":
    import sys
    
    # Allow command line arguments for projects directory and output directory
    if len(sys.argv) >= 3:
        projects_dir = sys.argv[1]
        output_dir = sys.argv[2]
    else:
        # Default directories
        projects_dir = "projects"
        output_dir = "weekly_outputs"
        print("Usage: python run_agent.py <projects_directory> <output_directory>")
        print(f"Using defaults: projects_dir='{projects_dir}', output_dir='{output_dir}'")
    
    if not os.path.exists(projects_dir):
        print(f"Error: Projects directory '{projects_dir}' does not exist")
        print("Please create a 'projects' directory and add your project CSV files")
        sys.exit(1)
    
    results = generate_weekly_report(projects_dir, output_dir)
    
    # Print results to console
    print("\n" + "=" * 60)
    print("PROJECT HEALTH REPORT RESULTS")
    print("=" * 60)
    for project_name, rag_status in results.items():
        print(f"\n{project_name}: {rag_status.status}")
        print(rag_status.reasoning)
