from services.qdrant_service import QdrantService


def main():
    qdrant = QdrantService()

    print("Health:", qdrant.health_check())
    print("Collection:", qdrant.ensure_collection())


if __name__ == "__main__":
    main()