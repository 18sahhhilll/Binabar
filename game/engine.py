"""Game scoring and answer matching logic."""

import re
import unicodedata


def normalize_answer(text: str) -> str:
    """
    Normalize an answer string for comparison.
    - Lowercase
    - Strip whitespace
    - Remove punctuation
    - Collapse multiple spaces
    - Unicode normalize
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.lower().strip()
    # Common artist/track stylings in DHH (e.g. KR$NA -> krsna)
    text = text.replace("$", "s")
    # Replace hyphens, underscores and slashes with spaces
    text = re.sub(r"[-_/]+", " ", text)
    # Remove all punctuation except spaces
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def check_answer(guess: str, song) -> bool:
    """
    Check if a guess matches the song.
    Matches against title and all accepted_answers.
    Case-insensitive, ignores punctuation and extra spaces.
    """
    normalized_guess = normalize_answer(guess)
    if not normalized_guess:
        return False

    # Check against title
    if normalized_guess == normalize_answer(song.title):
        return True

    # Check against accepted answers
    if isinstance(song.accepted_answers, list):
        for answer in song.accepted_answers:
            if normalized_guess == normalize_answer(answer):
                return True

    return False


def calculate_score(correct: bool, hints_used: int) -> int:
    """
    Calculate score for a round.
    - 100 for correct with no hints
    - Minus 25 per hint used
    - Minimum 25 for a correct answer
    - 0 for wrong or skip
    """
    if not correct:
        return 0
    score = 100 - (25 * hints_used)
    return max(25, score)
