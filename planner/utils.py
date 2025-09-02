import markdown

def convert_markdown_to_html(markdown_text):
    """Converts Markdown text to HTML."""
    if markdown_text is None:
        return ""
    # Enable common Markdown extensions for better parsing of LLM output
    extensions = [
        'fenced_code',  # For ```code blocks```
        'tables',       # For Markdown tables
        'nl2br',        # For newline to <br> conversion
        'extra',        # A collection of common extensions
    ]
    return markdown.markdown(markdown_text, extensions=extensions)