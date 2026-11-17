def priority_score(intent: float, relevance: float, opportunity: float, feasibility: float) -> float:
    """Planning heuristic, NOT an algorithm that predicts actual search rank."""
    return round(.35 * intent + .25 * relevance + .20 * opportunity + .20 * feasibility, 2)
