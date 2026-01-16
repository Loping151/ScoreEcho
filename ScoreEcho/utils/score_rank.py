from typing import List

SCORE_INTERVAL = ["c", "b", "a", "s", "ss", "sss"]
DEFAULT_TOTAL_GRADE: List[float] = [0, 0.48, 0.6, 0.7, 0.78, 0.84]


def get_score_grade(score: float, total_grade: List[float] = DEFAULT_TOTAL_GRADE) -> str:
    if score <= 0:
        return SCORE_INTERVAL[0]
    ratio = score / 250
    idx = 0
    for index, threshold in enumerate(total_grade):
        if ratio >= threshold:
            idx = index
    return SCORE_INTERVAL[idx]
