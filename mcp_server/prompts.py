"""
prompts.py

Prompt templates for the Copperleaf Kitchen MCP Server.
"""


def health_inspection_report():
    return (
        "Generate a health inspection report using the current "
        "food safety incidents and inventory information. "
        "Highlight violations and recommended corrective actions."
    )
