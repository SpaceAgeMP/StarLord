from requests import post
from json import loads
from typing import Iterable

def _mapItemId(item: dict[str, str]):
    return item["publishedfileid"]

def getWorkshopItems(collectionId: str) -> Iterable[str]:
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
    res = post(url, data = {
        "collectioncount": "1",
        "publishedfileids[0]": collectionId,
    })
    resData = loads(res.text)
    resItems = resData["response"]["collectiondetails"][0]["children"]
    return map(_mapItemId, resItems)
