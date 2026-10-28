from pprint import pprint
from statistics import median
import sys

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

    ranked = []
    for director in results:
        # Inntekt lik 0 behandles som ukjent, slik det er begrunnet i EDA.
        revenues = [value for value in director.pop("revenues")
                    if value is not None and value > 0]
        if revenues:
            director["revenue_count"] = len(revenues)
            director["median_revenue"] = median(revenues)
            ranked.append(director)

    ranked.sort(key=lambda director: (
        -director["median_revenue"], director["_id"]
    ))

    pprint(ranked[:10], sort_dicts=False)



def task_2(db):
    pipeline = [
        # Bare feltene som brukes videre tas med når alle parene lages.
        {"$project": {"cast.id": 1, "cast.name": 1, "vote_average": 1}},

        # En skuespiller kan ha flere roller, men telles én gang per film.
        {"$unwind": "$cast"},
        {"$group": {
            "_id": {"movie": "$_id", "actor": "$cast.id"},
            "name": {"$first": "$cast.name"},
            "vote_average": {"$first": "$vote_average"}
        }},
        {"$group": {
            "_id": "$_id.movie",
            "cast": {"$push": {"id": "$_id.actor", "name": "$name"}},
            "vote_average": {"$first": "$vote_average"}
        }},

        {"$project": {
            "cast_a": "$cast",
            "cast_b": "$cast",
            "vote_average": 1
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
        }},

        {"$match": {"movie_count": {"$gte": 3}}},
        {"$sort": {"movie_count": -1, "_id.actor_a": 1, "_id.actor_b": 1}}
    ]

    results = db.movies.aggregate(pipeline, allowDiskUse=True)

    for pair in results:
        pprint(pair, sort_dicts=False)


def task_3(db):
    # Topp 10 skuespillere med minst 10 filmer og flest forskjellige sjangre.
    pipeline = [
        {"$unwind": "$cast"},
        {"$group": {
            "_id": "$cast.id",
            "actor": {"$first": "$cast.name"},
            "movies": {"$addToSet": "$_id"},
            "genre_lists": {"$addToSet": "$genres.name"}
        }},
        {"$set": {"movie_count": {"$size": "$movies"}}},
        {"$match": {"movie_count": {"$gte": 10}}},
        {"$project": {"movies": 0}}
    ]

    results = list(db.movies.aggregate(pipeline, allowDiskUse=True))
    for actor in results:
        # Set fjerner sjangre som forekommer i flere av skuespillerens filmer.
        genres = set()
        for genre_list in actor.pop("genre_lists"):
            genres.update(genre_list)
        actor["genre_count"] = len(genres)
        actor["example_genres"] = sorted(genres)[:5]

    results.sort(key=lambda actor: (-actor["genre_count"], actor["_id"]))
    pprint(results[:10], sort_dicts=False)


def task_4(db):
    # Topp 10 filmsamlinger med minst tre filmer, sortert etter total inntekt.
    pipeline = [
        {"$match": {"belongs_to_collection.name": {"$type": "string"}}},
        {"$group": {
            "_id": "$belongs_to_collection.id",
            "collection": {"$first": "$belongs_to_collection.name"},
            "movie_count": {"$sum": 1},
            "total_revenue": {"$sum": "$revenue"},
            "revenue_count": {"$sum": {"$cond": [{"$gt": ["$revenue", 0]}, 1, 0]}},
            "votes": {"$push": "$vote_average"},
            "earliest_release": {"$min": "$release_date"},
            "latest_release": {"$max": "$release_date"}
        }},
        {"$match": {"movie_count": {"$gte": 3}, "revenue_count": {"$gt": 0}}},
        {"$sort": {"total_revenue": -1, "_id": 1}},
        {"$limit": 10}
    ]

    results = list(db.movies.aggregate(pipeline))
    for collection in results:
        votes = [value for value in collection.pop("votes") if value is not None]
        collection["median_vote_average"] = median(votes) if votes else None
        # Datointervallet bruker bare registrerte datoer; mangler fylles ikke inn.
        for field in ["earliest_release", "latest_release"]:
            if collection[field] is not None:
                collection[field] = collection[field].strftime("%Y-%m-%d")

    pprint(results, sort_dicts=False)


def task_5(db):
    # Median spilletid og antall filmer per tiår og første registrerte sjanger.
    pipeline = [
        {"$match": {
            "release_date": {"$type": "date"},
            "genres.0": {"$exists": True}
        }},
        {"$project": {
            "year": {"$year": "$release_date"},
            "primary_genre": {"$arrayElemAt": ["$genres.name", 0]},
            "runtime": 1
        }},
        {"$set": {
            "decade": {"$subtract": ["$year", {"$mod": ["$year", 10]}]}
        }},
        {"$group": {
            "_id": {"decade": "$decade", "genre": "$primary_genre"},
            "movie_count": {"$sum": 1},
            "runtimes": {"$push": "$runtime"}
        }}
    ]

    results = list(db.movies.aggregate(pipeline))
    for group in results:
        # Manglende spilletid og 0 minutter utelates fra medianen, ikke filmtallet.
        runtimes = [value for value in group.pop("runtimes")
                    if value is not None and value > 0]
        group["runtime_count"] = len(runtimes)
        group["median_runtime"] = median(runtimes) if runtimes else None

    results.sort(key=lambda group: (
        group["_id"]["decade"],
        -(group["median_runtime"] if group["median_runtime"] is not None else -1),
        group["_id"]["genre"]
    ))
    for group in results:
        pprint(group, sort_dicts=False)


def main():
    tasks = {1: task_1, 2: task_2, 3: task_3, 4: task_4, 5: task_5}
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] not in {"1", "2", "3", "4", "5"}):
        raise SystemExit("Bruk: python queries.py [1-5]")
    number = int(sys.argv[1]) if len(sys.argv) == 2 else 1
    connection = DbConnector()
    try:
        tasks[number](connection.db)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
