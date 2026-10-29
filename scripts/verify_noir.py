"""Kontroller oppgave 7 direkte mot rå CSV, uten MongoDB eller tekstindeks."""
import json
from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parents[1]
    movies = pd.read_csv(root / "data/movies_metadata.csv", low_memory=False)
    votes = pd.to_numeric(movies["vote_count"], errors="coerce")
    text = movies[["overview", "tagline"]].fillna("").agg(" ".join, axis=1)
    substring = text.str.contains("noir", case=False, regex=False)
    word = text.str.contains(r"(?<!\w)noir(?!\w)", case=False, regex=True)
    fields = ["id", "title", "release_date", "vote_average", "vote_count"]
    matches = movies.loc[word & votes.ge(50), fields].sort_values(
        ["vote_average", "vote_count", "title"], ascending=[False, False, True]
    )
    substring_only = movies.loc[substring & ~word & votes.ge(50), fields]
    examples = ["Sin City", "L.A. Confidential", "Blade Runner", "Chinatown", "Drive", "Pulp Fiction"]
    example_check = movies.loc[movies["title"].isin(examples), ["title"]].copy()
    example_check["contains_noir"] = substring.loc[example_check.index]
    result = {
        "substring_matches": int(substring.sum()),
        "substring_with_50_votes": int((substring & votes.ge(50)).sum()),
        "word_matches": int(word.sum()),
        "word_with_50_votes": len(matches),
        "qualifying_word_matches": matches.to_dict("records"),
        "substring_only_with_50_votes": substring_only.to_dict("records"),
        "example_title_check": example_check.to_dict("records"),
    }
    path = root / "report/noir_verification.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
