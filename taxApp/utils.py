from taxApp.models import *
from decimal import *
from pycoingecko import CoinGeckoAPI
import datetime
import time
import os
import requests
from zoneinfo import ZoneInfo

cg = CoinGeckoAPI(api_key=os.environ.get('COINGECKO_APIKEY'))
# cg = CoinGeckoAPI(api_key='notanapikey')
hyETH = Coin.objects.get(pk=11182)
wstETH = Coin.objects.get(pk=10707)

def getPrice(coin, date):
    now = date == "now"
    if now:
        date = datetime.datetime.now().astimezone(ZoneInfo('UTC'))
    try:
        p = HistoricalPrice.objects.get(coin=coin, date__date=date.date())
        return p.price
    except HistoricalPrice.MultipleObjectsReturned:
        p = getClosestToDate(HistoricalPrice.objects.filter(coin=coin), date)
        return p.price
    except HistoricalPrice.DoesNotExist:
        print("fetching")
        #to limit it to 30 calls/min
        # time.sleep(0.5)
        if now:
            res = cg.get_price(ids=coin.coingecko_id, vs_currencies='aud')
            price = Decimal(res[coin.coingecko_id]['aud'])
        else:
            data = cg.get_coin_history_by_id(id=coin.coingecko_id, date=date.strftime("%d-%m-%Y"), localization=False)
            try:
                price = Decimal(data['market_data']['current_price']['aud'])
            except KeyError:
                print(data)
                if 'id' in data:
                    if coin == hyETH:
                        return getPrice(wstETH, date)
                    return Decimal(0)
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

        
