import base64
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

client = OpenAI(
    api_key="",
    base_url="https://api.avalai.ir/v1",
    timeout=300.0,
    max_retries=0,
)

response = client.images.generate(
    model="gpt-image-2",
    prompt="A simple empty wooden desk by a window. No people or text.",
    n=1,
    size="1024x1024",
)

item = response.data[0]

if not item.b64_json:
    raise RuntimeError(
        f"AvalAI returned no b64_json. "
        f"url={getattr(item, 'url', None)!r}; "
        f"response={response.model_dump()}"
    )

image_bytes = base64.b64decode(item.b64_json, validate=True)
Path("avalai-test.png").write_bytes(image_bytes)

print(f"Saved {len(image_bytes):,} bytes")