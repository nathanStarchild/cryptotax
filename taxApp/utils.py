from taxApp.models import *
from decimal import *
from pycoingecko import CoinGeckoAPI
import datetime
import time
import os
import requests

cg = CoinGeckoAPI()

def getPrice(coin, date):
    try:
        p = HistoricalPrice.objects.get(coin=coin, date__date=date.date())
        return p.price
    except HistoricalPrice.MultipleObjectsReturned:
        p = getClosestToDate(HistoricalPrice.objects.filter(coin=coin), date)
        return p.price
    except HistoricalPrice.DoesNotExist:
        print("fetching")
        #to limit it to 30 calls/min
        time.sleep(3)
        data = cg.get_coin_history_by_id(id=coin.coingecko_id, date=date.strftime("%d-%m-%Y"), localization=False)
        price = Decimal(data['market_data']['current_price']['aud'])
        savePrice(coin, price, date)
        return price

def getClosestToDate(q, date):
    greater = q.filter(date__gte=date).order_by("date").first()
    less = q.filter(date__lte=date).order_by("-date").first()

    if greater and less:
        return greater if abs(greater.date - date) < abs(less.date - date) else less
    else:
        return greater or less
    
def savePrice(coin, price, date):
    p = HistoricalPrice(
        coin=coin,
        date=date.replace(hour=0, minute=0, second=0),
        price=price
    )
    p.save()

        
