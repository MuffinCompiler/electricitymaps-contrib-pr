#!/usr/bin/env python3

import json
from datetime import datetime
from logging import Logger, getLogger
from typing import Any, Dict, Optional

import arrow
from pytz import timezone
from requests import Response, Session

from parsers.lib.exceptions import ParserException

NDC_GENERATION = "https://disnews.energy.mn/test/convert.php"
TZ = timezone("Asia/Ulaanbaatar")  # UTC+8

# Query fields to web API fields
JSON_QUERY_TO_SRC = {
    "time": "date",
    "consumptionMW": "syssum",
    "solarMW": "sumnar",
    "windMW": "sums",
    "importMW": "energyimport",  # positive = import
    "temperatureC": "t",  # current temperature
}


def parse_json(web_json: dict) -> Dict[str, Any]:
    """
    Parse the fetched JSON data to our query format according to JSON_QUERY_TO_SRC.
    Example of expected JSON format present at URL:
    {"date":"2023-06-27 18:00:00","syssum":"869.37","sumnar":42.34,"sums":119.79,"energyimport":"49.58","t":"17"}
    """

    # Validate first if keys in fetched dict match expected keys
    if set(JSON_QUERY_TO_SRC.values()) != set(web_json.keys()):
        raise ParserException(
            parser="MN.py",
            message=f"Fetched keys from source {web_json.keys()} do not match expected keys {JSON_QUERY_TO_SRC.values()}.",
        )

    if None in web_json.values():
        raise ParserException(
            parser="MN.py",
            message=f"Fetched values contain null. Fetched data: {web_json}.",
        )

    # Then we can safely parse them
    query_data = dict()
    for query_key, src_key in JSON_QUERY_TO_SRC.items():

        if query_key == "time":
            # convert to datetime
            parsed_time = arrow.get(web_json[src_key], "YYYY-MM-DD HH:mm:ss", tzinfo=TZ)
            query_data[query_key] = parsed_time.datetime
        else:
            # or convert to float, might also be string
            query_data[query_key] = float(web_json[src_key])

    return query_data


def query(session: Session) -> Dict[str, Any]:
    """
    Query the JSON endpoint and parse it.
    """

    target_response: Response = session.get(NDC_GENERATION)

    if not target_response.ok:
        raise ParserException(
            parser="MN.py",
            message=f"Data request did not succeed: {target_response.status_code}",
        )

    # Read as JSON
    response_json = json.loads(target_response.text)
    query_result = parse_json(response_json)

    return query_result


def fetch_production(
    zone_key: str = "MN",
    session: Session = Session(),
    target_datetime: Optional[datetime] = None,
    logger: Logger = getLogger(__name__),
):
    if target_datetime:
        raise NotImplementedError("This parser is not yet able to parse past dates.")

    query_data = query(session)

    # Calculated 'unknown' production from available data (consumption, import, solar, wind).
    # 'unknown' consists of 92.8% coal, 5.8% oil and 1.4% hydro as per 2020; sources: IEA and IRENA statistics.
    query_data["unknownMW"] = round(
        query_data["consumptionMW"]
        - query_data["importMW"]
        - query_data["solarMW"]
        - query_data["windMW"],
        2,
    )

    dataset_production = {
        "unknown": query_data["unknownMW"],
        "solar": query_data["solarMW"],
        "wind": query_data["windMW"],
    }
    data = {
        "zoneKey": zone_key,
        "datetime": query_data["time"],
        "production": dataset_production,
        "source": "https://ndc.energy.mn/",
    }

    return data


def fetch_consumption(
    zone_key: str = "MN",
    session: Session = Session(),
    target_datetime: Optional[datetime] = None,
    logger: Logger = getLogger(__name__),
):
    if target_datetime:
        raise NotImplementedError("This parser is not yet able to parse past dates.")

    query_data = query(session)

    data = {
        "zoneKey": zone_key,
        "datetime": query_data["time"],
        "consumption": query_data["consumptionMW"],
        "source": "https://ndc.energy.mn/",
    }

    return data


if __name__ == "__main__":
    print("fetch_production() ->")
    print(fetch_production())
    print("fetch_consumption() ->")
    print(fetch_consumption())
