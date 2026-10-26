from DbConnector import DbConnector

connection = DbConnector()
db = connection.db

if "movies" not in db.list_collection_names():
    db.create_collection("movies", validator={
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "title"],
            "properties": {
                "_id": {"bsonType": ["int", "long"]},
                "title": {"bsonType": "string"},
                "original_title": {"bsonType": ["string", "null"]},
                "original_language": {"bsonType": ["string", "null"]},
                "release_date": {"bsonType": ["date", "null"]},
                "runtime": {"bsonType": ["number", "null"]},
                "budget": {"bsonType": ["number", "null"]},
                "revenue": {"bsonType": ["number", "null"]},
                "popularity": {"bsonType": ["number", "null"]},
                "vote_average": {"bsonType": ["number", "null"]},
                "vote_count": {"bsonType": ["int", "long", "null"]},
                "overview": {"bsonType": ["string", "null"]},
                "tagline": {"bsonType": ["string", "null"]},
                "belongs_to_collection": {"bsonType": ["object", "null"]},
                "genres": {"bsonType": "array"},
                "production_companies": {"bsonType": "array"},
                "production_countries": {"bsonType": "array"},
                "spoken_languages": {"bsonType": "array"},
    
                # Fra credits.csv
                "cast": {"bsonType": "array"},
                "crew": {"bsonType": "array"},
    
                # Fra keywords.csv
                "keywords": {"bsonType": "array"}
            }
        }
    })

if "ratings" not in db.list_collection_names():
    db.create_collection("ratings", validator={
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["userId", "movieId", "rating", "timestamp"],
            "properties": {
                "userId": {"bsonType": ["int", "long"]},
                "movieId": {"bsonType": ["int", "long"]},
                "tmdbId": {"bsonType": ["int", "long", "null"]},
                "rating": {
                    "bsonType": "number",
                    "minimum": 0.5,
                    "maximum": 5.0
                },
                "timestamp": {"bsonType": "date"}
            }
        }
    })



connection.close_connection()
