import sys
import time
from pprint import pprint
from statistics import median

from tabulate import tabulate

from DbConnector import DbConnector


def task_1(db):
    pipeline = [
        {"$unwind": "$crew"},

        {"$match": {"crew.job": "Director"}},

        {"$group": {
            "_id": {
                "director": "$crew.id",
                "movie": "$_id"
            },
            "name": {"$first": "$crew.name"},
            "revenue": {"$first": "$revenue"},
            "vote_average": {"$first": "$vote_average"}
        }},

        {"$group": {
            "_id": "$_id.director",
            "director": {"$first": "$name"},
            "movie_count": {"$sum": 1},
            "revenues": {"$push": "$revenue"},
            "mean_vote_average": {"$avg": "$vote_average"}
        }},

        # Regissøren må ha minst fem filmer
        {"$match": {"movie_count": {"$gte": 5}}}
    ]

    results = list(db.movies.aggregate(pipeline))

    for director in results:
        director["median_revenue"] = median(director.pop("revenues"))

    results.sort(key=lambda director: (
        -director["median_revenue"], director["_id"]
    ))

    pprint(results[:10], sort_dicts=False)



def task_2(db):
    pipeline = [
        {"$set": {
            "cast_a": "$cast",
            "cast_b": "$cast"
        }},

        {"$unwind": "$cast_a"},
        {"$unwind": "$cast_b"},

        {"$match": {
            "$expr": {"$lt": ["$cast_a.id", "$cast_b.id"]}
        }},

        {"$group": {
            "_id": {
                "actor_a": "$cast_a.id",
                "actor_b": "$cast_b.id"
            },
            "actor_a": {"$first": "$cast_a.name"},
            "actor_b": {"$first": "$cast_b.name"},
            "movie_count": {"$sum": 1},
            "mean_vote_average": {"$avg": "$vote_average"}
        }}
    ]

    results = db.movies.aggregate(pipeline)

    for pair in results:
        pprint(pair, sort_dicts=False)


def task_3(db):
    return 0

def task_4(db):
    return 0

def task_5(db):
    return 0

def task_6(db):
    """Kvinneandel blant de fem øverst krediterte, per tiår."""
    pipeline = [
        {"$match": {"release_date": {"$ne": None}, "cast.0": {"$exists": True}}},
        # 'order' starter ikke alltid på 0, så vi sorterer og tar de fem første.
        {"$project": {
            "decade": {"$multiply": [{"$floor": {"$divide": [{"$year": "$release_date"}, 10]}}, 10]},
            "top5": {"$slice": [{"$sortArray": {"input": "$cast", "sortBy": {"order": 1}}}, 5]},
        }},
        {"$project": {
            "decade": 1,
            "female": {"$size": {"$filter": {"input": "$top5", "cond": {"$eq": ["$$this.gender", 1]}}}},
            "known": {"$size": {"$filter": {"input": "$top5", "cond": {"$in": ["$$this.gender", [1, 2]]}}}},
        }},
        # Filmer uten noen kjent kjønn blant de fem har ingen andel.
        {"$match": {"known": {"$gt": 0}}},
        {"$group": {
            "_id": "$decade",
            "avg_female_share": {"$avg": {"$divide": ["$female", "$known"]}},
            "movies": {"$sum": 1},
        }},
        {"$sort": {"avg_female_share": -1}},
    ]
    rows = list(db.movies.aggregate(pipeline))
    print(tabulate([[f"{int(r['_id'])}s", f"{r['avg_female_share']:.3f}", r["movies"]] for r in rows],
                   headers=["Tiår", "Snitt kvinneandel", "Antall filmer"], tablefmt="github"))


def task_7(db):
    """Tekstsøk etter noir / neo-noir."""
    pipeline = [
        # Indeksen deler 'neo-noir' i tokenene 'neo' og 'noir', så 'noir' fanger begge.
        {"$match": {"$text": {"$search": "noir"}, "vote_count": {"$gte": 50}}},
        {"$sort": {"vote_average": -1, "vote_count": -1, "title": 1}},
        {"$limit": 20},
        {"$project": {"_id": 0, "title": 1, "year": {"$year": "$release_date"},
                      "vote_average": 1, "vote_count": 1}},
    ]
    rows = list(db.movies.aggregate(pipeline))
    print(tabulate([[r["title"], r.get("year"), r["vote_average"], r["vote_count"]] for r in rows],
                   headers=["Tittel", "År", "vote_average", "vote_count"], tablefmt="github"))


def task_8(db):
    """Regissør-skuespiller-par med minst 3 felles filmer (vote_count >= 100)."""
    pipeline = [
        {"$match": {"vote_count": {"$gte": 100}}},
        {"$project": {
            "vote_average": 1,
            "revenue": {"$cond": [{"$gt": ["$revenue", 0]}, "$revenue", None]},  # 0 betyr ukjent
            "directors": {"$filter": {"input": "$crew", "cond": {"$eq": ["$$this.job", "Director"]}}},
            "cast": 1,
        }},
        {"$unwind": "$directors"},
        {"$unwind": "$cast"},
        # Samme person som regissør og skuespiller i samme film er ikke et samarbeid.
        {"$match": {"$expr": {"$ne": ["$directors.id", "$cast.id"]}}},
        # Først én rad per (regissør, skuespiller, film) så dobbeltoppføringer ikke teller to ganger.
        {"$group": {
            "_id": {"d": "$directors.id", "a": "$cast.id", "m": "$_id"},
            "director": {"$first": "$directors.name"}, "actor": {"$first": "$cast.name"},
            "vote_average": {"$first": "$vote_average"}, "revenue": {"$first": "$revenue"},
        }},
        {"$group": {
            "_id": {"d": "$_id.d", "a": "$_id.a"},
            "director": {"$first": "$director"}, "actor": {"$first": "$actor"},
            "films": {"$sum": 1},
            "mean_vote_average": {"$avg": "$vote_average"},
            "mean_revenue": {"$avg": "$revenue"},  # $avg hopper over null (ukjent revenue)
        }},
        {"$match": {"films": {"$gte": 3}}},
        {"$sort": {"mean_vote_average": -1, "films": -1, "director": 1, "actor": 1}},
        {"$limit": 20},
    ]
    rows = list(db.movies.aggregate(pipeline, allowDiskUse=True))
    print(tabulate([[r["director"], r["actor"], r["films"], f"{r['mean_vote_average']:.3f}",
                     "" if r["mean_revenue"] is None else f"{r['mean_revenue']:,.0f}"] for r in rows],
                   headers=["Regissør", "Skuespiller", "Filmer", "Snitt vote_average", "Snitt revenue"],
                   tablefmt="github"))


def task_9(db):
    """Ikke-engelske filmer med amerikansk tilknytning."""
    # Land har ISO-kode. Selskap har bare navn, så de identifiseres på navn som starter med 'United States'.
    us = {"$or": [
        {"production_countries.iso_3166_1": "US"},
        {"production_companies.name": {"$regex": "^United States"}},
    ]}
    pipeline = [
        {"$match": {"original_language": {"$nin": [None, "en"]}, **us}},
        {"$sort": {"vote_count": -1, "title": 1}},  # eksempeltittel = mest stemte film
        {"$group": {"_id": "$original_language", "count": {"$sum": 1}, "example": {"$first": "$title"}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 10},
    ]
    rows = list(db.movies.aggregate(pipeline))
    print(tabulate([[r["_id"], r["count"], r["example"]] for r in rows],
                   headers=["original_language", "Antall", "Eksempeltittel"], tablefmt="github"))


def task_10(db):
    """Per bruker: antall ratings, populasjonsvarians og antall ulike sjangre."""
    pipeline = [
        {"$group": {
            "_id": "$userId",
            "n": {"$sum": 1},
            "sd": {"$stdDevPop": "$rating"},
            "movies": {"$addToSet": "$tmdbId"},  # tmdbId er null uten treff i movies
        }},
        {"$match": {"n": {"$gte": 20}}},
        {"$lookup": {"from": "movies", "localField": "movies", "foreignField": "_id",
                     "pipeline": [{"$project": {"_id": 0, "genres.name": 1}}], "as": "rated"}},
        {"$project": {
            "n": 1,
            "variance": {"$pow": ["$sd", 2]},
            "genres": {"$size": {"$reduce": {
                "input": "$rated.genres.name", "initialValue": [],
                "in": {"$setUnion": ["$$value", "$$this"]}}}},
        }},
        {"$facet": {
            "diverse": [{"$sort": {"genres": -1, "n": -1, "_id": 1}}, {"$limit": 10}],
            "variance": [{"$sort": {"variance": -1, "_id": 1}}, {"$limit": 10}],
        }},
    ]
    result = next(db.ratings.aggregate(pipeline, allowDiskUse=True))
    for key, title in [("diverse", "Mest sjangerbrede brukere"), ("variance", "Høyest varians")]:
        print(f"\n{title}")
        print(tabulate([[r["_id"], r["n"], f"{r['variance']:.4f}", r["genres"]] for r in result[key]],
                       headers=["userId", "Antall ratings", "Varians", "Ulike sjangre"], tablefmt="github"))


# task_2 er ikke ferdig (ubegrenset antall par), så den kjøres ikke ennå
TASKS = {1: task_1, 6: task_6, 7: task_7, 8: task_8, 9: task_9, 10: task_10}


def main():
    wanted = [int(a) for a in sys.argv[1:]] or list(TASKS)
    connection = DbConnector()
    try:
        for number in wanted:
            print(f"\n=== Oppgave {number} ===")
            start = time.time()
            TASKS[number](connection.db)
            print(f"({time.time() - start:.1f} s)")
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
