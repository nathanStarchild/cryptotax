from taxApp.models import *
from taxApp.utils import getPrice
from django.db.models import Sum, Count, F, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
import csv
from zoneinfo import ZoneInfo
import time

def yesNo(condition):
    return "Yes" if condition else "No"

def checkReady(user, year):
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
    #all transactions processed
    transactions = Transaction.objects.filter(
        fromAddr__user=user, 
        date__range=[startDate, endDate],
        )
    assert not transactions.filter(processed = False).exists(), f"You have unprocessed transactions: {[t.id for t in transactions]}"
    #all vault incomes processed - not really, if the transaction is processed it should be
    #all exchange withdrawals processed
    withdrawals = ExchangeWithdrawal.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        )
    assert not withdrawals.filter(processed = False).exists(), f"You have unprocessed Exchange withdrawals: {[w.id for w in withdrawals]}"
    #all token bridges processed
    bridges = TokenBridge.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        )
    assert not bridges.filter(processed = False).exists(), f"You have unprocessed Token bridges: {[b.id for b in bridges]}"

    sales = Sale.objects.filter(date__range=[startDate, endDate], user=user)
    spends = Spend.objects.filter(date__range=[startDate, endDate], user=user)
    cgtEvent = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user)
    assert sales.count() + spends.count() == cgtEvent.count(), f"Sales + spends does not equal cgtEvents"

def getData(coin, year, user, buffer):
    ####UMMMM shouldn't it bed Sydney time???
    # startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
    # endDate = datetime.datetime(year+1, 6, 30)
    # endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('Australia/Sydney'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('Australia/Sydney'))
    #all transactions processed
    transactions = Transaction.objects.filter(
        Q(tokentransfer__coin = coin) | Q(feeCoin=coin),
        fromAddr__user=user, 
        date__range=[startDate, endDate],
        ).order_by('date')
    assert not transactions.filter(processed = False).exists(), f"You have unprocessed transactions: {[t.id for t in transactions]}"
    #all vault incomes processed - not really, if the transaction is processed it should be
    #all exchange withdrawals processed
    withdrawals = ExchangeWithdrawal.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        coin = coin,
        ).order_by('date')
    assert not withdrawals.filter(processed = False).exists(), f"You have unprocessed Exchange withdrawals: {[w.id for w in withdrawals]}"
    #all token bridges processed
    bridges = TokenBridge.objects.filter(
        user=user, 
        date__range=[startDate, endDate],
        coin = coin,
        ).order_by('date')
    assert not bridges.filter(processed = False).exists(), f"You have unprocessed Token bridges: {[b.id for b in bridges]}"

    sales = Sale.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,).order_by('date')
    spends = Spend.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,).order_by('date')
    cgtEvent = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,).order_by('date')
    assert sales.count() + spends.count() == cgtEvent.count(), f"Sales + spends does not equal cgtEvents"

    buys = Buy.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,).order_by('date')
    income = Income.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,).order_by('date')

    cgtEvents = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,)

    vaults = Vault.objects.filter(vaultdeposit__user=user, vaultdeposit__coin=coin, vaultdeposit__transaction__date__lte=endDate).distinct()
    print(cgtEvents.count())

    openingBalance = coin.getBalance(user, startDate)
    closingBalance = coin.getBalance(user, endDate)
    if not openingBalance and not buys.exists() and not income.exists():
        return
    fmt = "%d/%m/%Y %H:%M %z"
    writer = csv.writer(buffer)
    writer.writerows([
        ["----------", "----------", "----------", "----------", "----------"],
        ['Asset', coin.name],
        ['Symbol', coin.symbol],
        ['Opening Balance', openingBalance],
        ['Closing Balance', closingBalance],
        ['Capital Gain', cgtEvents.aggregate(val=Coalesce(Sum("gain"), Decimal(0)))['val']],
        ['Income (units)', income.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
        ["Income (AUD)", income.aggregate(val=Coalesce(Sum("amount"), Decimal(0)))['val']]
    ])

    writer.writerows([
        [""],
        ['Purchases'],
        ['ID', 'Date', 'Units', 'Price AUD', 'Fee AUD', 'Amount AUD', 'Note', "Refeerence ID"],
        ['Total', "", buys.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
    ])
    if buys.exists():
        writer.writerows([
            [
                d.id,
                d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                d.units,
                f"{d.unitPrice:.2f}",
                f"{d.feeAUD:.2f}",
                f"{d.total():.2f}",
                d.note,
                d.refId,
            ]
            for d in buys
        ])

    writer.writerows([
        [""],
        ['Income'],
        ['ID', 'Date', 'Units', 'Price AUD', 'Amount AUD', 'Note', "Transaction ID", "Link"],
        ['Total', "", income.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val'], "",income.aggregate(val=Coalesce(Sum("amount"), Decimal(0)))['val']],
    ])
    if income.exists():
        writer.writerows([
            [
                d.id,
                d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                d.units,
                f"{d.unitPrice:.2f}",
                f"{d.amount:.2f}",
                d.note,
                d.transaction.hash if d.transaction else '',
                d.transaction.explorerUrl() if d.transaction else '',
            ]
            for d in income
    ])
        
    writer.writerows([
        [""],
        ['Sales'],
        ['ID', 'Date', 'Units', 'Price AUD', 'Fee AUD', 'Amount AUD', 'Note', "Refeerence ID"],
        ['Total', "", sales.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
    ])
    if sales.exists():
        writer.writerows([
            [
                d.id,
                d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                d.units,
                f"{d.unitPrice:.2f}",
                f"{d.feeAUD:.2f}",
                f"{d.total():.2f}",
                d.note,
                d.refId,
            ]
            for d in sales
        ])

    writer.writerows([
        [""],
        ['Disposals (spend)'],
        ['id', 'Date', 'Units', 'Price AUD', 'Amount AUD', 'Note'],
        ['Total', "", spends.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
    ])
    if spends.exists():
        writer.writerows([
            [
                d.id,
                d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                d.units,
                f"{d.unitPrice:.2f}",
                f"{d.total():.2f}",
                d.description,
            ]
            for d in spends
        ])

    writer.writerows([
        [""],
        ['Capital Gains Tax Events'],
        ['Method', cgtEvents.first().method if cgtEvents.exists() else ""],
        ['ID', 'Date', 'Units', 'Price AUD (incl. Fee)', 'Source', 'Cost Basis'],
        ["", "", "", "", "", "Source", "Date", "Units Consumed", "Price AUD (incl. Fee)", "Held >1yr", "Capital Gain"],
        ["", "", "", "", "", "", "", "", "", 'Grand Total', cgtEvents.aggregate(val=Coalesce(Sum("gain"), Decimal(0)))['val']],
    ])
    for d in cgtEvents.order_by('date'):
        order = "-date" if d.method == "LIFO" else "date"
        cbOrder = "-costBasis__date" if d.method == "LIFO" else "costBasis__date"
        writer.writerow([
                d.id,
                d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                d.units,
                f"{d.unitPrice:.2f}",
                d.sourceString(),
                "",
                "",
                "",
                "",
                "Total",
                f"{d.gain:.2f}"
            ],)
        writer.writerows([
            [
                "",
                "",
                "",
                "",
                "",
                dd.costBasis.sourceString(),
                dd.costBasis.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                dd.consumed,
                dd.costBasis.unitPrice,
                yesNo(dd.discounted),
                dd.gain,
            ]
            for dd in d.cgttocostbasis_set.order_by(cbOrder)
        ])

    if vaults.exists():
        writer.writerows([
            [""],
            ["Staking"],
            ["Note: Staking deposits are not treated as a disposal as we have not transfered it to another entity and we remain the beneficial owner of the asset"],
        ])
        for v in vaults:
            opening = v.getBalance(startDate)
            closing = v.getBalance(endDate)
            deposits = v.vaultdeposit_set.filter(user=user, coin=coin, transaction__date__range=[startDate, endDate])
            if not opening and not deposits.exists():
                continue
            withdrawals = v.vaultwithdrawal_set.filter(user=user, coin=coin, transaction__date__range=[startDate, endDate])
            income = v.vaultincome_set.filter(user=user, coin=coin, transaction__date__range=[startDate, endDate])
            writer.writerows([
                [""],
                ["Name", v.name],
                ["Contract Address", v.address],
                ["Opening Balance", opening],
                ["Closing Balance", closing],
                ["ID", "Date", "Units", "Transaction ID", "Link"],
                ["Deposits"],
            ])
            for d in deposits:
                writer.writerow([
                    d.id,
                    d.transaction.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                    d.amount,
                    d.transaction.hash,
                    d.transaction.explorerUrl(),
                ])
            writer.writerows([
                [""],
                ["Withdrawals"]
            ])
            for d in withdrawals:
                writer.writerow([
                    d.id,
                    d.transaction.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                    d.amount,
                    d.transaction.hash,
                    d.transaction.explorerUrl(),
                ])

            writer.writerows([
                [""],
                ["Income"]
            ])
            for d in income:
                writer.writerow([
                    d.id,
                    d.transaction.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
                    d.amount,
                    d.transaction.hash,
                    d.transaction.explorerUrl(),
                ])
    
    writer.writerows([
        [""],
        ["Onchain Transactions"],
        ["ID", "Date", "Network", "Fee", "Fee Coin", "Fee AUD", "Link"],
    ])
    for d in transactions.order_by('chain', 'date'):
        writer.writerow([
            d.hash,
            d.date.astimezone(ZoneInfo('Australia/Sydney')).strftime(fmt),
            d.chain.name,
            d.fee,
            d.feeCoin.symbol,
            d.feeAUD,
            d.explorerUrl(),
        ])

    writer.writerows([
        [""],
        [f"End {coin.name}"],
        [""],
    ])

def totalHoldings(date, user):
    coins = Coin.objects.filter(buy__user=user, buy__date__lte=date).distinct()
    buys = Buy.objects.filter(user=user, date__lte=date, coin=OuterRef('pk')).values('coin').annotate(bought=Sum('units')).order_by().values('bought')
    sales = Sale.objects.filter(user=user, date__lte=date, coin=OuterRef('pk')).values('coin').annotate(sold=Sum('units')).order_by().values('sold')
    incomes = Income.objects.filter(user=user, date__lte=date, coin=OuterRef('pk')).values('coin').annotate(incame=Sum('units')).order_by().values('incame')
    spends = Spend.objects.filter(user=user, date__lte=date, coin=OuterRef('pk')).values('coin').annotate(spent=Sum('units')).order_by().values('spent')
    coins = coins.annotate(
        bought=Coalesce(Subquery(buys), Decimal(0)), 
        sold=Coalesce(Subquery(sales), Decimal(0)),
        incame=Coalesce(Subquery(incomes), Decimal(0)),
        spent=Coalesce(Subquery(spends), Decimal(0))
    )
    coins = coins.annotate(holding=F('bought') + F('incame') - F('sold') - F('spent'))
    data = []
    for c in coins:
        try:
            price = getPrice(c, date)
        except:#TODO get the error
            print("too many requests")
            time.sleep(60)
            print("retrying")
            price = getPrice(c, date)
        dat = {
            'coin': c,
            'holding': c.holding,
            'price': price,
            'value': price * c.holding,
        }
        data.append(dat)
    data.sort(key=lambda d: -d['value'])
    total = sum([d['value'] for d in data])
    return data, total

