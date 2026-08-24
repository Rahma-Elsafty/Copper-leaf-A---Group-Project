try:
    import tiktoken
except ImportError:
    tiktoken = None


def get_encoder():

    if tiktoken is None:
        return None

    try:
        return tiktoken.get_encoding(
            "cl100k_base"
        )
    except Exception:
        return None


def count_tokens(text):

    if text is None:
        return 0

    text = str(text)

    encoder = get_encoder()

    if encoder is None:
        return max(
            1,
            len(text) // 4,
        )

    return len(
        encoder.encode(text)
    )