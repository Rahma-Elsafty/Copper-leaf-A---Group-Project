import tiktoken


def get_encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: str) -> int:
    encoder = get_encoder()

    if encoder is None:
        return max(1, len(text) // 4)

    return len(encoder.encode(text))


def count_message_tokens(messages: list[dict]) -> int:
    text = "\n".join(
        f"{message.get('role', '')}: {message.get('content', '')}"
        for message in messages
    )

    return count_tokens(text)