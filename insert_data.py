import csv
import io
from ast import literal_eval
from pathlib import Path

import pandas as pd

from DbConnector import DbConnector


DATA = Path(__file__).parent / "data"


def prepare_movies():
    # De tre filmene som er delt over to CSV-rader, settes sammen igjen.
    with open(DATA / "movies_metadata.csv", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        columns = next(reader)
        rows = list(reader)

    for index in [35586, 29502, 19729]:
        start, continuation = rows[index:index + 2]
        assert len(start) == 10 and len(continuation) == 15
        combined = start[:9] + [start[9] + continuation[0]] + continuation[1:]
        assert len(combined) == len(columns)
        rows[index:index + 2] = [combined]

    # Les de reparerte radene med samme typegjenkjenning som en vanlig CSV.
    repaired_csv = io.StringIO()
    writer = csv.writer(repaired_csv)
    writer.writerow(columns)
    writer.writerows(rows)
    repaired_csv.seek(0)
    movies = pd.read_csv(repaired_csv, low_memory=False)

    for column in ["id", "budget", "popularity"]:
        movies[column] = pd.to_numeric(movies[column])
    movies["release_date"] = pd.to_datetime(movies["release_date"], format="%Y-%m-%d")

    movies = movies.drop_duplicates().copy()
    movies["popularity"] = movies.groupby("id")["popularity"].transform("mean")
    # Behold høyeste registrerte vote_count; øvrige felt er like unntatt popularity.
    movies = movies.sort_values("vote_count", ascending=False, kind="stable")
    movies = movies.drop_duplicates(subset=["id"]).copy()

    credits = pd.read_csv(DATA / "credits.csv").drop_duplicates(subset=["id"])
    keywords = pd.read_csv(DATA / "keywords.csv").drop_duplicates(subset=["id"])

    movies = movies.merge(credits, on="id", how="left", validate="one_to_one")
    movies = movies.merge(keywords, on="id", how="left", validate="one_to_one")

    # CSV-tekst gjøres om til faktiske lister og dictionaries.
    list_columns = ["genres", "production_companies", "production_countries",
                    "spoken_languages", "cast", "crew", "keywords"]
    for column in list_columns:
        movies[column] = movies[column].apply(
            lambda value: literal_eval(value) if isinstance(value, str) else []
        )
    movies["belongs_to_collection"] = movies["belongs_to_collection"].apply(
        lambda value: literal_eval(value) if isinstance(value, str) else None
    )
    movies["keywords"] = movies["keywords"].apply(
        lambda values: [keyword for keyword in values if keyword["name"].strip()]
    )

    movies = movies.rename(columns={"id": "_id"})
    # NaN og NaT kan ikke brukes som manglende BSON-verdier.
    movies = movies.astype(object).where(movies.notna(), None)
    documents = movies.to_dict("records")
    for movie in documents:
        movie["_id"] = int(movie["_id"])
        movie["vote_count"] = int(movie["vote_count"]) if movie["vote_count"] is not None else None
        if movie["release_date"] is not None:
            movie["release_date"] = movie["release_date"].to_pydatetime()

    return documents


def insert_ratings(db, movie_ids, small=False):
    # Småfilene brukes sammen under testing, aldri i tillegg til fullfilene.
    suffix = "_small" if small else ""
    links = pd.read_csv(DATA / f"links{suffix}.csv")
    if links["movieId"].duplicated().any():
        raise ValueError("links har flere koblinger for samme movieId.")

    # En referanse settes bare hvis filmen finnes i movies.
    # Ratingen og den opprinnelige MovieLens-ID-en beholdes også uten treff.
    links.loc[~links["tmdbId"].isin(movie_ids), "tmdbId"] = None

    batch = []
    batch_size = 10000
    inserted = 0
    unmatched = 0

    for ratings in pd.read_csv(DATA / f"ratings{suffix}.csv", chunksize=batch_size):
        ratings = ratings.merge(links[["movieId", "tmdbId"]], on="movieId",
                                how="left", validate="many_to_one")
        ratings["timestamp"] = pd.to_datetime(ratings["timestamp"], unit="s", utc=True)

        for rating in ratings.to_dict("records"):
            rating["userId"] = int(rating["userId"])
            rating["movieId"] = int(rating["movieId"])
            rating["tmdbId"] = int(rating["tmdbId"]) if pd.notna(rating["tmdbId"]) else None
            rating["timestamp"] = rating["timestamp"].to_pydatetime()
            batch.append(rating)
            unmatched += rating["tmdbId"] is None

            if len(batch) >= batch_size:
                db.ratings.insert_many(batch)
                inserted += len(batch)
                batch.clear()
                if inserted % 1000000 == 0:
                    print("Innsatte ratings:", inserted)

    # Sett også inn siste batch hvis den har færre enn 10 000 ratings.
    if batch:
        db.ratings.insert_many(batch)
        inserted += len(batch)

    print("Antall innsatte ratings:", inserted)
    print("Ratings uten kobling til movies:", unmatched)


def main():
    connection = DbConnector()
    try:
        db = connection.db
        if not {"movies", "ratings"}.issubset(db.list_collection_names()):
            raise RuntimeError("Kjør setup_db.py først.")
        if db.movies.count_documents({}) > 0 or db.ratings.count_documents({}) > 0:
            raise RuntimeError("movies eller ratings inneholder allerede data. Ingenting er satt inn.")

        documents = prepare_movies()
        for start in range(0, len(documents), 1000):
            db.movies.insert_many(documents[start:start + 1000])

        print("Antall innsatte filmer:", db.movies.count_documents({}))
        example = db.movies.find_one({"_id": 862})
        print("Eksempelfilm:", example["title"])
        print("Cast:", len(example["cast"]), "Crew:", len(example["crew"]),
              "Keywords:", len(example["keywords"]))

        movie_ids = {movie["_id"] for movie in documents}
        insert_ratings(db, movie_ids)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
