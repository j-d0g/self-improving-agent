"""
Prompts Module

Utilities for loading prompt files.
"""

from pathlib import Path

__all__ = ["load_prompt"]

# Cache for loaded prompts
_prompt_cache: dict[str, str] = {}


def load_prompt(filename: str) -> str:
    """
    Load a prompt from the prompts directory.

    Args:
        filename: Name of the prompt file (e.g., 'financial_agent.txt')

    Returns:
        The prompt content as a string.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    if filename in _prompt_cache:
        return _prompt_cache[filename]

    prompt_path = Path(__file__).parent / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text()
    _prompt_cache[filename] = content
    return content
