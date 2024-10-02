import csv
import codecs
import datetime
import pytz
from zoneinfo import ZoneInfo
from taxApp.models import *
from django.db import transaction, IntegrityError

from decimal import *
from pycoingecko import CoinGeckoAPI
import re
from taxApp.utils import getPrice, savePrice

def importBtcMarkets(file, u):
    ff = codecs.iterdecode(file, "unicode_escape")
    reader = csv.DictReader(ff)
    fmtString = "%Y-%m-%dT%H:%M:%S%z"
    f = 1e18
    for row in reader:
        # print(row)
        if row[" Asset"] == "AUD":
            continue
        refId = row["Transaction Id"]
        if row[" Transaction"] == "Buy Order":
            # print(f'Buy {row[" Transaction Date and Timestamp"]} {row[" Transaction"]} {row[" Asset"]} - Volume: {row[" Volume"]} Price: {row[" Price (AUD)"]} Fee: {row[" Fee (AUD)"]}')
            try:
                Buy.objects.get(refId=refId)
                print('already exists')
                continue
            except Buy.DoesNotExist:
                pass
            
            c = Coin.objects.get(symbol__iexact=row[" Asset"])
            b = Buy(
                coin=c,
                units=row[" Volume"],
                unitPrice=row[" Price (AUD)"],
                date=datetime.datetime.strptime(row[" Transaction Date and Timestamp"], fmtString),
                user=u,
                feeAUD=row[" Fee (AUD)"],
                refId=refId,
                note="BTC Markets"                           
            )
            b.save()
            b.refresh_from_db()
            b.createCostBasis()
            print('buy order entered')
        
        elif row[" Transaction"] == "Sell Order":
            # print(f'Buy {row[" Transaction Date and Timestamp"]} {row[" Transaction"]} {row[" Asset"]} - Volume: {row[" Volume"]} Price: {row[" Price (AUD)"]} Fee: {row[" Fee (AUD)"]}')
            try:
                Sale.objects.get(refId=refId)
                print('already exists')
                continue
            except Sale.DoesNotExist:
                pass
            
            c = Coin.objects.get(symbol__iexact=row[" Asset"])
            s = Sale(
                coin=c,
                units=-1 * Decimal(row[" Volume"]),
                unitPrice=row[" Price (AUD)"],
                date=datetime.datetime.strptime(row[" Transaction Date and Timestamp"], fmtString),
                user=u,
                feeAUD=row[" Fee (AUD)"],
                refId=refId,
                note="BTC Markets"                           
            )
            s.save()
            print("sale entered")

        elif row[" Transaction"] == "Withdraw":
            try:
                ExchangeWithdrawal.objects.get(refId=refId)
                print('already exists')
                continue
            except ExchangeWithdrawal.DoesNotExist:
                pass
            c = Coin.objects.get(symbol__iexact=row[" Asset"])
            fee = Decimal(row[" Fee (AUD)"]) / Decimal(row[" Price (AUD)"])
            w = ExchangeWithdrawal(
                coin = c,
                unitsSent = -1 * Decimal(row[" Volume"]),
                date=datetime.datetime.strptime(row[" Transaction Date and Timestamp"], fmtString),
                user=u,
                feeCoin = c,
                feeAUD = row[" Fee (AUD)"],
                fee = fee,
                refId=refId,
            )
            w.save()
            spend = Spend(
                coin=c,
                units=fee,
                unitPrice=row[" Price (AUD)"],
                date=datetime.datetime.strptime(row[" Transaction Date and Timestamp"], fmtString),
                user=u,
                note=f"withdrawal {w.id}",
                description="BTC Markets withdrawal fee",
            )
            spend.save()
            print("withdrawal entered")

def importBinanceTrades(file, user):
    ff = codecs.iterdecode(file, "utf-8-sig")
    reader = csv.DictReader(ff)
    # cg = CoinGeckoAPI()
    pattern = re.compile(r'(\d+\.\d+)(\w+)')
    with transaction.atomic():
        for row in reader:
            date = datetime.datetime.fromisoformat(row['Date(UTC)']).replace(tzinfo=pytz.UTC)
            executed, symbol1 = pattern.match(row['Executed']).groups()
            executed = Decimal(executed)
            amount, symbol2 = pattern.match(row['Amount']).groups()
            amount = Decimal(amount)
            fee, symbolFee = pattern.match(row['Fee']).groups()
            fee = Decimal(fee)

            if not "AUD" in [symbol1, symbol2]:
                c1 = Coin.objects.get(symbol__iexact=symbol1)
                c2 = Coin.objects.get(symbol__iexact=symbol2)
                # print(c1Data['market_data']['current_price']['aud'])
                # print(c2Data['market_data']['current_price']['aud'])
                try:
                    c1AUD = getPrice(c1, date)
                except KeyError:
                    c1AUD = None
                try:
                    c2AUD = getPrice(c2, date)
                except KeyError:
                    c2AUD = c1AUD * executed / amount
                    savePrice(c1, c1AUD, date)

                if not c1AUD:
                    c1AUD = c2AUD * amount / executed
                    savePrice(c2, c2AUD, date)
                # print(f"c1*executed: {c1AUD*executed}")
                # print(f"c2*amount: {c2AUD*amount}")
                if symbolFee == symbol1:
                    feeCoin = c1
                    feeAUD = fee * c1AUD
                elif symbolFee == symbol2:
                    feeCoin = c2
                    feeAUD = fee * c2AUD
                else:
                    feeCoin =  Coin.objects.get(symbol__iexact=symbolFee)
                    feeCoinAUD = getPrice(feeCoin, date)
                    feeAUD = fee * feeCoinAUD

                if row["Side"] == "BUY":
                    buyCoin = c1
                    buyUnits = executed
                    buyPrice = c1AUD
                    sellCoin = c2
                    sellUnits = amount
                    sellPrice = c1AUD * executed / amount
                elif row["Side"] == "SELL":
                    buyCoin = c2
                    buyUnits = amount
                    buyPrice = c1AUD * executed / amount
                    sellCoin = c1
                    sellUnits = executed
                    sellPrice = c1AUD
                else:
                    assert False, f"side is {row['Side']}"

                b = Buy(
                    coin=buyCoin,
                    units=buyUnits,
                    unitPrice=buyPrice,
                    date=date,
                    user=user,
                    feeAUD=feeAUD,
                    fee = fee,
                    feeCoin = feeCoin,
                    note=f"Binance {symbol1} {symbol2}",
                )
                b.save()
                b.refresh_from_db()
                b.createCostBasis()
                print('buy order entered')
                
                s = Sale(
                    coin=sellCoin,
                    units=sellUnits,
                    unitPrice=sellPrice,
                    date=date,
                    user=user,
                    feeAUD=feeAUD,
                    fee = fee,
                    feeCoin = feeCoin,
                    note=f"Binance {symbol1} {symbol2}",
                )
                s.save()
                print("sale entered")

            elif symbol1 == "AUD":
                assert row["Side"] == "SELL", f"symbol1 is AUD but it's not a sale?? {row}"
                c2 = Coin.objects.get(symbol__iexact=symbol2)
                c2AUD = getPrice(c2, date)
                if symbolFee == symbol2:
                    feeCoin = c2
                    feeAUD = fee * c2AUD
                else:
                    feeCoin =  Coin.objects.get(symbol__iexact=symbolFee)
                    feeCoinAUD = getPrice(feeCoin, date)
                    feeAUD = fee * feeCoinAUD

                s = Sale(
                    coin=c2,
                    units=-1 * amount,
                    unitPrice=Decimal(row["Price"]),
                    date=date,
                    user=user,
                    feeAUD=feeAUD,
                    fee = fee,
                    feeCoin = feeCoin,
                    note=f"Binance {symbol1} {symbol2}",
                )
                s.save()
                print("sale entered")
            elif symbol2 == "AUD":
                assert row["Side"] == "BUY", f"symbol2 is AUD but it's not a buy?? {row}"
                c1 = Coin.objects.get(symbol__iexact=symbol1)
                c1AUD = getPrice(c1, date)
                if symbolFee == symbol1:
                    feeCoin = c1
                    feeAUD = fee * c1AUD
                else:
                    feeCoin =  Coin.objects.get(symbol__iexact=symbolFee)
                    feeCoinAUD = getPrice(feeCoin, date)
                    feeAUD = fee * feeCoinAUD

                b = Buy(
                    coin=c1,
                    units=executed,
                    unitPrice=Decimal(row["Price"]),
                    date=date,
                    user=user,
                    feeAUD=feeAUD,
                    fee = fee,
                    feeCoin = feeCoin,
                    note=f"Binance {symbol1} {symbol2}",
                )
                b.save()
                b.refresh_from_db()
                b.createCostBasis()
                print('buy order entered')

def importBinanceAll(file, user):
    ff = codecs.iterdecode(file, "utf-8-sig")
    reader = csv.DictReader(ff)
    with transaction.atomic():
        for row in reader:
            if not row["Operation"] == "Withdraw":
                continue

            date = datetime.datetime.fromisoformat(row['UTC_Time']).replace(tzinfo=pytz.UTC)
            coin = Coin.objects.get(symbol__iexact=row["Coin"])
            
            w = ExchangeWithdrawal(
                coin = coin,
                unitsSent = -1 * Decimal(row["Change"]),
                date=date,
                user=user,
                feeCoin = coin,
                note = "Binance Withdrawal"
            )
            w.save()
            print("withdrawal Processed")

def importSwyftx(file, user):
    ff = codecs.iterdecode(file, "utf-8-sig")
    reader = csv.DictReader(ff)
    with transaction.atomic():
        for row in reader:
            date = datetime.datetime.strptime(
                f"{row['Date']} {row['Time']}",
                "%d/%m/%Y %H:%M:%S"
            ).replace(tzinfo=ZoneInfo('Australia/Sydney'))
            # print(date)
            c = Coin.objects.get(symbol__iexact=row["Asset"])
            refId = row["UUID"]
            if row["Event"] == "buy":
                # continue
                try:
                    Buy.objects.get(refId=refId)
                    print('already exists')
                    continue
                except Buy.DoesNotExist:
                    pass

                b = Buy(
                    coin=c,
                    units=row["Amount"],
                    unitPrice=row["Rate"],
                    date=date.astimezone(ZoneInfo('UTC')),
                    user=user,
                    feeAUD=row["AUD Value Fee"],
                    refId=refId,
                    note="Swyftx"                           
                )
                b.save()
                b.refresh_from_db()
                b.createCostBasis()
                b.savePrice()
                print('buy order entered')

            elif row["Event"] == "sell":
                # continue
                try:
                    Sale.objects.get(refId=refId)
                    print('already exists')
                    continue
                except Sale.DoesNotExist:
                    pass

                s = Sale(
                    coin=c,
                    units=row["Amount"],
                    unitPrice=row["Rate"],
                    date=date.astimezone(ZoneInfo('UTC')),
                    user=user,
                    feeAUD=row["AUD Value Fee"],
                    refId=refId,
                    note="Swyftx"                           
                )
                s.save()
                s.savePrice()
                print('sell order entered')

            elif row["Event"] == "withdraw":
                # [print(a) for a in row['Withdrawal Fee']]
                print(row['Withdrawal Fee'])
                print(Decimal(row['Withdrawal Fee'].strip('"')))
                # print(row["Withdrawn To"].strip())
                # pass
                if row["Transaction ID"].strip().startswith("Internal transfer"):
                    refId = row["Transaction ID"].strip()
                try:
                    ExchangeWithdrawal.objects.get(refId=refId)
                    print('already exists')
                    continue
                except ExchangeWithdrawal.DoesNotExist:
                    pass

                #save the price
                price = Decimal(row["AUD Value"]) / Decimal(row["Amount"])
                try:
                    HistoricalPrice.objects.get(coin=c, date=date)
                except HistoricalPrice.DoesNotExist:
                    h = HistoricalPrice(
                        coin=c,
                        date=date.astimezone(ZoneInfo('UTC')),
                        price=price
                    )
                    h.save()

                fee = Decimal(row['Withdrawal Fee'].strip('"'))

                if fee == 0:
                    fee = None
                    feeAUD = None
                else:
                    feeAUD = fee * price

                if row["Transaction ID"].strip().startswith("0x"):
                    txId = row["Transaction ID"].strip()
                else:
                    txId = None

                w = ExchangeWithdrawal(
                    coin = c,
                    unitsSent = row["Amount"],
                    date=date.astimezone(ZoneInfo('UTC')),
                    user=user,
                    feeCoin = c,
                    feeAUD = feeAUD,
                    fee = fee,
                    refId=refId,
                    txId = txId,
                    note = "swyftx withdrawal"
                )
                w.save()
                w.createFeeSpend()
                w.processed = True
                w.save()
                print("withdrawal entered")


def importSwyftxAUD(file, user):
    ff = codecs.iterdecode(file, "utf-8-sig")
    reader = csv.DictReader(ff)
    # with transaction.atomic():
    for row in reader:
        date = datetime.datetime.strptime(
            f"{row['Date']} {row['Time']}",
            "%d/%m/%Y %H:%M:%S"
        ).replace(tzinfo=ZoneInfo('Australia/Sydney'))

        if row['Event'] == "deposit":
            amount = row['Amount']
        else:
            assert False, 'not a deposit!'

        refId = row["UUID"]

        t = ExchangeAUDTransaction(
            user = user,
            date = date,
            amount = amount,
            note = "Swyftx AUD deposit",
            refId = refId
        )
        try:
            t.save()
        except IntegrityError:
            pass
    swyftxAUDBuysAndSales(user)

def swyftxAUDBuysAndSales(user):

    buys = Buy.objects.filter(user=user, note__startswith = "Swyftx")
    sales = Sale.objects.filter(user=user, note__startswith = "Swyftx")
    # with transaction.atomic():
    for buy in buys:
        t = ExchangeAUDTransaction(
            user = buy.user,
            date = buy.date,
            amount = -1 * (buy.units * buy.unitPrice + buy.feeAUD),
            note = f"Swyftx purchase {buy.coin.symbol} with AUD",
            refId = buy.refId
        )
        try:
            t.save()
        except IntegrityError:
            pass

    for sale in sales:
        t = ExchangeAUDTransaction(
            user = sale.user,
            date = sale.date,
            amount = sale.units * sale.unitPrice - sale.feeAUD,
            note = f"Swyftx sell {sale.coin.symbol} for AUD",
            refId = sale.refId
        )
        try:
            t.save()
        except IntegrityError:
            pass



