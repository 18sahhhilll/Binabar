"""Unit tests for scoring engine and answer normalization."""

from game.engine import calculate_score, check_answer, normalize_answer


class DummySong:
    def __init__(self, title, accepted_answers=None):
        self.title = title
        self.accepted_answers = accepted_answers or []


class TestAnswerNormalization:
    def test_lowercase(self):
        assert normalize_answer("Kohinoor") == "kohinoor"

    def test_strip_whitespace(self):
        assert normalize_answer("  Kohinoor  ") == "kohinoor"

    def test_ignore_punctuation(self):
        assert normalize_answer("Say My Name!") == "say my name"
        assert normalize_answer("No-Cap") == "no cap"
        assert normalize_answer("A.G.R.") == "agr"

    def test_collapse_multiple_spaces(self):
        assert normalize_answer("Gully    Gang") == "gully gang"

    def test_unicode_normalization(self):
        assert normalize_answer("Beyoncé") == "beyonce"


class TestAnswerMatching:
    def test_exact_match(self):
        song = DummySong("Kohinoor")
        assert check_answer("Kohinoor", song) is True

    def test_case_insensitive_match(self):
        song = DummySong("Kohinoor")
        assert check_answer("kohinoor", song) is True
        assert check_answer("KOHINOOR", song) is True

    def test_punctuation_and_space_insensitive(self):
        song = DummySong("No Cap (feat. KR$NA)")
        assert check_answer("no cap feat krsna", song) is True

    def test_accepted_answers_match(self):
        song = DummySong(
            "Machayenge",
            accepted_answers=["Machayenge 1", "Machayege"],
        )
        assert check_answer("Machayenge", song) is True
        assert check_answer("Machayenge 1", song) is True
        assert check_answer("machayege", song) is True

    def test_wrong_answer(self):
        song = DummySong("Kohinoor")
        assert check_answer("Mirchi", song) is False
        assert check_answer("", song) is False


class TestScoringEngine:
    def test_correct_no_hints(self):
        assert calculate_score(True, 0) == 100

    def test_correct_one_hint(self):
        assert calculate_score(True, 1) == 75

    def test_correct_two_hints(self):
        assert calculate_score(True, 2) == 50

    def test_correct_three_hints(self):
        # 100 - (3 * 25) = 25, minimum 25
        assert calculate_score(True, 3) == 25

    def test_correct_four_hints_minimum_floor(self):
        # Minimum 25 for any correct answer
        assert calculate_score(True, 4) == 25

    def test_wrong_answer_zero_points(self):
        assert calculate_score(False, 0) == 0
        assert calculate_score(False, 2) == 0

    def test_skip_zero_points(self):
        assert calculate_score(False, 0) == 0
