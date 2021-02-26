from requests import post
from json import loads

def _mapItemId(item):
    return item["publishedfileid"]

def getWorkshopItems(collectionId):
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
    data = {
        "collectioncount": "1",
        "publishedfileids[0]": collectionId,
    }
    res = post(url, data = data)
    resData = loads(res.text)
    resItems = resData["response"]["collectiondetails"][0]["children"]
    return map(_mapItemId, resItems)
