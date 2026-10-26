from pprint import pprint
from statistics import median

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


def main():
    connection = DbConnector()
    try:
        task_1(connection.db)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
