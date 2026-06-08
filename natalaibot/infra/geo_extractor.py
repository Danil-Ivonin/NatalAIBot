from typing import Optional
from timezonefinder import TimezoneFinder

import httpx

from natalaibot.models import GeoPoint


class GeocodingError(Exception):
    pass


async def geocode_address(
    address: str,
    base_url: str,
    api_key: str,
    *,
    language: str = "ru",
) -> Optional[GeoPoint]:
    """
    Получает latitude / longitude по адресу.

    address:
        "Москва, Красная площадь"
        "Saint Petersburg, Nevsky Prospekt"
        "Berlin, Alexanderplatz"

    language:
        "ru" — ответ преимущественно на русском
        "en" — ответ преимущественно на английском

    country_codes:
        ["ru"] — искать преимущественно в России
        ["ru", "by", "kz"] — несколько стран
        None — искать глобально
    """

    address = address.strip()

    if not address:
        raise ValueError("Address must not be empty")

    params = {
        "q": address,
        "format": "json",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": language,
        "key": api_key,
    }

    headers = {"accept": "application/json"}

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        response = await client.get(base_url, params=params)

    if response.status_code != 200:
        raise GeocodingError(f"Geocoding failed: {response.status_code} {response.text}")

    if not response:
        raise GeocodingError(f"Geocoding failed: empty response: {response.text}")

    result = response.json()

    best = result[0]
    latitude = float(best["lat"])
    longitude = float(best["lon"])
    city = best["address"]["city"]
    nation = best["address"]["country_code"].upper()
    timezone = TimezoneFinder().timezone_at(
        lat=latitude,
        lng=longitude,
    )

    if timezone is None:
        raise GeocodingError(f"Could not determine timezone for coordinates: {latitude}, {longitude}")

    return GeoPoint(lat=latitude, lng=longitude, addr=best.get("display_name", address), timezone=timezone, city=city, nation=nation)
