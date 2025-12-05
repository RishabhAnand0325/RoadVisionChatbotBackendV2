import re

def clean_text(text) -> str:
    """
    Clean the text by removing special characters and extra spaces.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text.
    """
    return re.sub(r'[^\w\s]', '', text).strip()
