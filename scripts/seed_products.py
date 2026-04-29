#!/usr/bin/env python3
"""
Seed products from a data/ directory.

Each image file becomes a product:
  - Name: filename stem (e.g. "Jabłko.jpg" → "Jabłko")
  - Price: 0.00 (update manually after import)
  - Unit: pcs (default, change with --unit kg)

Usage:
    uv run --active python scripts/seed_products.py --data-dir data --unit pcs --api-url http://127.0.0.1:8000
"""

import argparse
import mimetypes
import sys
from pathlib import Path

import httpx

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def get_token(api_url: str, email: str, password: str) -> str:
    resp = httpx.post(
        f"{api_url}/api/v1/login/access-token",
        data={"username": email, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_product(api_url: str, token: str, name: str, unit: str) -> str:
    resp = httpx.post(
        f"{api_url}/api/v1/products/",
        json={"name": name, "price": "0.00", "unit": unit},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def upload_image(api_url: str, token: str, product_id: str, image_path: Path) -> None:
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    with image_path.open("rb") as f:
        resp = httpx.post(
            f"{api_url}/api/v1/products/{product_id}/image",
            files={"file": (image_path.name, f, mime)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed products from image files.")
    parser.add_argument(
        "--data-dir", default="data", help="Directory with product images"
    )
    parser.add_argument(
        "--unit", default="pcs", choices=["pcs", "kg"], help="Default product unit"
    )
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000", help="Backend API URL"
    )
    parser.add_argument(
        "--email", default=None, help="Superuser email (overrides .env)"
    )
    parser.add_argument(
        "--password", default=None, help="Superuser password (overrides .env)"
    )
    args = parser.parse_args()

    email = args.email
    password = args.password
    if not email or not password:
        try:
            from app.core.config import settings

            email = email or settings.FIRST_SUPERUSER
            password = password or settings.FIRST_SUPERUSER_PASSWORD
        except Exception:
            print(
                "ERROR: Provide --email and --password or run from the backend directory with .env present."
            )
            sys.exit(1)

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir.resolve()}")
        sys.exit(1)

    images = sorted(
        p for p in data_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        print(f"No image files found in {data_dir.resolve()}")
        sys.exit(0)

    print(f"Logging in as {email} ...")
    token = get_token(args.api_url, email, password)

    ok = 0
    for image_path in images:
        name = image_path.stem
        try:
            product_id = create_product(args.api_url, token, name, args.unit)
            upload_image(args.api_url, token, product_id, image_path)
            print(f"  OK  {name}  ({image_path.name})")
            ok += 1
        except httpx.HTTPStatusError as exc:
            print(
                f"  FAIL  {name}: HTTP {exc.response.status_code} -- {exc.response.text}"
            )
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")

    print(f"\nDone: {ok}/{len(images)} products imported.")


if __name__ == "__main__":
    main()
