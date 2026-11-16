# Project Health Reporting

A Python learning project that reads project plans, applies rule-based Red/Amber/Green (RAG) checks, and displays the results in Streamlit. Here RAG means Red/Amber/Green, not retrieval-augmented generation.

Demo: https://automated-project-health-reporting-swfzzqfdr6h6bbugewzicw.streamlit.app/

## What it does

- Reads uploaded Excel project plans and maps common task columns.
- Checks schedule, blockages, stakeholder comments, and budget burn.
- Shows status explanations, portfolio charts, and risk summaries.
- Generates a PowerPoint summary from evaluated data.
- Offers optional Gemini-based questions and explanations when a valid API key is configured.

The status checks and reporting do not require Gemini. The synthetic demo checkbox gives a quick example without uploading files. Uploaded data takes priority over the synthetic example. Treat generated commentary as a draft to review, not a project-management decision.

## Run locally

Use Python 3.11 or 3.12:

```sh
python -m venv .venv
# Activate .venv for your operating system, then:
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For batch JSON/text reports:

```sh
python run_agent.py projects weekly_outputs
```

This command runs once. Weekly automation requires an external scheduler; the repository does not install one.

## Input and scoring

Example CSV columns for the command-line agent are `task_name`, `days_delayed`, `at_risk`, `comments`, `budget_spent_pct`, `completion_percentage`, and `is_critical_milestone`. The web app accepts Excel files and attempts column mapping. Review that mapping and the results when your input format differs.

The rule-based agent combines category results using the worst status: any Red makes the project Red; otherwise any Amber makes it Amber. The portfolio score is a separate weighted summary with equal weights across the four categories. It is not model accuracy. Missing data and keyword-based comment rules can change the result; inspect the source rules in `project_health_agent.py` before using them on another dataset.

## Optional Gemini setup

A missing or revoked key disables AI insights, not the dashboard or rule-based reports. Create a new key only if you want the AI feature. Do not commit keys or paste them in issues.

Locally, copy `.env.example` to `.env` and set `GEMINI_API_KEY` privately. On Streamlit Community Cloud, open this app's management/settings panel, select Secrets, and add:

```toml
GEMINI_API_KEY = "REPLACE_PRIVATELY_WITH_YOUR_NEW_KEY"
```

Save the secrets and reload the app. Confirm the AI Assistant Status shows a successful connection. A quota or model-availability error is separate from key validity. The password field in the sidebar is for an optional session-only key and never displays the server key.

## Limits

The input plans in `projects/` are existing examples; confirm you have permission before using or sharing any real project data. Gemini requests send the relevant context to Google's service only when that optional feature is used. The app has no user-account or multi-tenant data-isolation layer. Use synthetic data in a shared demo. No license claim or business-readiness claim is made here.
