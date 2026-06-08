from services.text_embedding_service import (
    TextEmbeddingService
)


def main():
    service = TextEmbeddingService()

    text = "Это мошенники"

    vector = service.embed_text(text)

    print()
    print("Embedding dimension:")
    print(service.embedding_dimension())

    print()
    print("Vector length:")
    print(len(vector))

    print()
    print("First 10 values:")
    print(vector[:10])


if __name__ == "__main__":
    main()