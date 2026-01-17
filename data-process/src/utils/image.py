import io
from io import BytesIO
from pathlib import Path

import pybase64 as base64
from PIL import Image


def convert_to_png(image: Image.Image) -> bytes:
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()


def encode_image_from_bytes(bytes: str):
    return base64.b64encode(bytes).decode("utf-8")


def encode_image(path: str | bytes | Image.Image):
    if isinstance(path, bytes):
        path = Image.open(BytesIO(path))

    if isinstance(path, (str, Path)):
        with Image.open(path) as image:
            mimetype = image.get_format_mimetype()
            if mimetype == "image/png":
                with open(path, "rb") as f:
                    encoded_image = base64.b64encode(f.read()).decode("utf-8")
                    return encoded_image
            else:
                png_image = convert_to_png(image)
                return base64.b64encode(png_image).decode("utf-8")
    else:
        png_image = convert_to_png(path)
        return base64.b64encode(png_image).decode("utf-8")


def encode_image_from_pil(image: Image.Image):
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode("utf-8")


def decode_image(encoded_image: str | bytes) -> Image.Image:
    if isinstance(encoded_image, str):
        if encoded_image.startswith("data:image"):
            encoded_image = encoded_image.split(",")[1]
        image = base64.b64decode(encoded_image)
        image_stream = io.BytesIO(image)
        return Image.open(image_stream)
    else:
        image_stream = io.BytesIO(encoded_image)
        return Image.open(image_stream)


def get_image_size(path: str):
    with Image.open(path) as image:
        return image.size


def get_image_size_from_base64(base64_string):
    if base64_string is None:
        return None
    if base64_string.startswith("data:image"):
        base64_string = base64_string.split(",")[1]
    image_bytes = base64.b64decode(base64_string)
    image = Image.open(BytesIO(image_bytes))
    return image.size

