import markdown

def convert_markdown_to_html(markdown_text):
    """Converts Markdown text to HTML."""
    if markdown_text is None:
        return ""
    return markdown.markdown(markdown_text)