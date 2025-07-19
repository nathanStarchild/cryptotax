from taxApp.models import *
from taxApp.utils import getPrice
from django.db.models import Sum, Count, F, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
import csv
from zoneinfo import ZoneInfo
import time
from io import StringIO

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

def getData(coin, year, user, buffer, headlineOnly=False):
    ####UMMMM shouldn't it bed Sydney time???
    # startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('UTC'))
    # endDate = datetime.datetime(year+1, 6, 30)
    # endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('UTC'))
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('Australia/Sydney'))
    endDate = datetime.datetime(year+1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('Australia/Sydney'))
    openingPrice = getPrice(coin, startDate)
    closingPrice = getPrice(coin, endDate)
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

    buys = buys.annotate(value=F('feeAUD') + (F('units') * F('unitPrice')))
    sales = sales.annotate(value=(F('units') * F('unitPrice')) - F('feeAUD'))
    spends = spends.annotate(value=F('units') * F('unitPrice'))

    cgtEvents = CGTEvent.objects.filter(date__range=[startDate, endDate], user=user, coin = coin,)
    capitalGain1yrPlus = 0
    captialGain1yrMinus = 0
    captialLoss = 0
    for evt in cgtEvents:
        for cb in evt.cgttocostbasis_set.all():
            if cb.grossGain < 0:
                captialLoss += cb.grossGain
            elif cb.discountable:
                capitalGain1yrPlus += cb.grossGain
            else:
                captialGain1yrMinus += cb.grossGain

    costBasesRemaining = CostBasis.objects.filter(user=user, coin=coin, remaining__gt=0, date__lte=endDate)
    costBasesRemaining = costBasesRemaining.annotate(value=F('remaining') * F('unitPrice'))
    remainingCost = costBasesRemaining.aggregate(val=Coalesce(Sum("value"), Decimal(0)))['val']

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
        ['Units Purchased', buys.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
        ['Income (units)', income.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
        ['Units Sold', -1 * sales.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
        ['Units Spent', -1 * spends.aggregate(val=Coalesce(Sum("units"), Decimal(0)))['val']],
        ['Closing Balance', closingBalance],
        ['Opening Value', openingBalance * openingPrice],
        ['Value of Purchases', buys.aggregate(val=Coalesce(Sum("value"), Decimal(0)))['val']],
        ["Income (AUD)", income.aggregate(val=Coalesce(Sum("amount"), Decimal(0)))['val']],
        ['Value of Sales', -1 * sales.aggregate(val=Coalesce(Sum("value"), Decimal(0)))['val']],
        ['Value of Spends', -1 * spends.aggregate(val=Coalesce(Sum("value"), Decimal(0)))['val']],
        ['Closing Value', closingBalance * closingPrice],
        ['Cost basis of units held', remainingCost],
        ['Unrealised Profit/Loss', closingBalance * closingPrice - remainingCost],
        ['Capital Loss', captialLoss],
        ['Capital Gain (held > 1 yr)', capitalGain1yrPlus],
        ['Capital Gain (held < 1 yr)', captialGain1yrMinus],
    ])

    if headlineOnly:
        return

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
                yesNo(dd.discountable),
                dd.grossGain,
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

def totalHoldings(date: datetime.date, user: User) -> tuple[list[dict], Decimal]:
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

def headlineReport(user, year):
    startDate = datetime.datetime(year, 7, 1, tzinfo=ZoneInfo('Australia/Sydney'))
    endDate = datetime.datetime(year + 1, 6, 30)
    endDate = datetime.datetime.combine(endDate, datetime.time.max, tzinfo=ZoneInfo('Australia/Sydney'))
    earliestDate = Buy.objects.filter(user=user).order_by("date").first().date
    dates = [endDate.replace(year=endDate.year - i) for i in [0, 1, 2]]

    # create a file-like buffer to store the file
    buffer = StringIO()
    writer = csv.writer(buffer)

    data = {}
    coins = set()
    for d in dates:
        holdings, total = totalHoldings(d, user)
        data[d] = {
            'holdings': {
                h['coin']: {
                    'units': h['holding'],
                    'value': h['value'],
                }
                for h in holdings
            },
            'total': total,
            ##################
            # Not for personal
            'audBalance': ExchangeAUDTransaction.objects.filter(
                    user=user,
                    date__lte=d,
                ).aggregate(t=Sum('amount'))['t'],
            # end not for personal
            #########################
        }
        for h in holdings:
            coins.add(h['coin'])

        capitalGain1yrPlus = 0
        captialGain1yrMinus = 0
        captialLoss = 0
        startDate = d.replace(year=d.year-1)
        CGTevents = CGTEvent.objects.filter(user=user, date__gte=startDate, date__lte=d)
        for evt in CGTevents:
            for cb in evt.cgttocostbasis_set.all():
                if cb.grossGain < 0:
                    captialLoss += cb.grossGain
                elif cb.discountable:
                    capitalGain1yrPlus += cb.grossGain
                else:
                    captialGain1yrMinus += cb.grossGain
        data[d]['cgt'] = {
            'loss': captialLoss,
            'gain1yrPlus': capitalGain1yrPlus,
            'gain1yrMinus': captialGain1yrMinus,
        }
        income = Income.objects.filter(user=user, date__gte=startDate, date__lte=d).aggregate(
            t=Coalesce(Sum('amount'), Decimal(0)))['t']
        data[d]['income'] = income

        buys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=d).annotate(
            cost=F('feeAUD') + F('units') * F('unitPrice')
        ).aggregate(total=Sum('cost'))['total']
        sales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=d).annotate(
            cost=F('units') * F('unitPrice') - F('feeAUD')
        ).aggregate(total=Sum('cost'))['total']
        spends = Spend.objects.filter(user=user, date__gte=startDate, date__lte=d).annotate(
            cost=F('units') * F('unitPrice')
        ).aggregate(total=Sum('cost'))['total']
        data[d]['buys'] = buys
        data[d]['sales'] = sales
        data[d]['spends'] = spends

        ################
        # for personal
        # CGTevents = CGTEvent.objects.filter(user=user, date__gte=startDate, date__lte=endDate)
        #
        # currYearGains = CGTtoCostBasis.objects.filter(
        #     cgtEvent__in = CGTevents,
        #     grossGain__gte = Decimal(0)
        # )
        # totalGrossGains = currYearGains.aggregate(t=Coalesce(Sum('grossGain'), Decimal(0)))['t']
        # totalNetGains = currYearGains.aggregate(t=Coalesce(Sum('netGain'), Decimal(0)))['t']
        # assert totalGrossGains >= totalNetGains, "something fishy, gross gains less than net gains"
        # currYearLosses = CGTtoCostBasis.objects.filter(
        #     cgtEvent__in = CGTevents,
        #     grossGain__lt = Decimal(0)
        # )
        # totalGrossLosses = currYearLosses.aggregate(t=Coalesce(Sum('grossGain'), Decimal(0)))['t']
        # totalNetLosses = currYearLosses.aggregate(t=Coalesce(Sum('netGain'), Decimal(0)))['t']
        # assert totalGrossLosses <= totalNetLosses, "something fishy, gross losses greater than net losses"

        # end for personal
        #####################3

        ################
        # for stardust
        # fees
        swyftxBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=d, note__startswith="Swyftx")
        binanceBuys = Buy.objects.filter(user=user, date__gte=startDate, date__lte=d, note__startswith="Binance")
        swyftxSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=d, note__startswith="Swyftx")
        binanceSales = Sale.objects.filter(user=user, date__gte=startDate, date__lte=d, note__startswith="Binance")

        swyftxSalesDistinct = []
        binanceSalesDistinct = []

        for s in swyftxSales:
            if not swyftxBuys.filter(date=s.date).exists():
                swyftxSalesDistinct.append(s.id)

        for s in binanceSales:
            if not binanceBuys.filter(date=s.date).exists():
                binanceSalesDistinct.append(s.id)

        swyftxSales = swyftxSales.filter(pk__in=swyftxSalesDistinct)
        binanceSales = binanceSales.filter(pk__in=binanceSalesDistinct)

        swyftxBuys = swyftxBuys.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']
        binanceBuys = binanceBuys.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']
        swyftxSales = swyftxSales.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']
        binanceSales = binanceSales.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0.0)))['t']

        withdrawals = ExchangeWithdrawal.objects.filter(user=user, date__gte=startDate, date__lte=d)
        withdrawals = withdrawals.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0)))['t']

        transactionFees = Transaction.objects.filter(fromAddr__user=user, date__gte=startDate, date__lte=d)
        transactionFees = transactionFees.aggregate(t=Coalesce(Sum('feeAUD'), Decimal(0)))['t']

        data[d]['fees'] = {
            'totalFees': swyftxBuys + binanceBuys + swyftxSales + binanceSales + withdrawals + transactionFees,
            'brokerageFees': swyftxBuys + binanceBuys + swyftxSales + binanceSales,
            'withdrawalFees': withdrawals,
            'transactionFees': transactionFees,
        }

        # AUD transactions
        audTransactions = ExchangeAUDTransaction.objects.filter(
            user=user,
            date__gte=startDate,
            date__lte=d
        )

        audDeposits = audTransactions.filter(
                note__icontains="deposit"
            ).aggregate(
                t=Coalesce(Sum('amount'), Decimal(0.0))
            )['t']
        audWithdrawals = audTransactions.filter(
                note__icontains="withdrawal"
            ).aggregate(
                t=Coalesce(Sum('amount'), Decimal(0.0))
            )['t']
        audPurchases = audTransactions.filter(
                note__icontains="purchase"
            ).aggregate(
                t=Coalesce(Sum('amount'), Decimal(0.0))
            )['t']
        audSales = audTransactions.filter(
                note__icontains="sell"
            ).aggregate(
                t=Coalesce(Sum('amount'), Decimal(0.0))
            )['t']

        data[d]['aud'] = {
            'deposits': audDeposits,
            'withdrawals': audWithdrawals,
            'purchases': audPurchases,
            'sales': audSales,
        }

        # End for stardust
        ######################



    writer.writerows([
        ["Financial Year Summary"],
        # [f"{startDate.strftime('%d/%m/%Y')} - {endDate.strftime('%d/%m/%Y')}"],
        [""],
        ["Portfolio Valuation"] + [f"FY{d.strftime('%Y')}" for d in dates],
        ["Total Crypto Assets"] + [f"{data[d]['total']:.2f}" for d in dates],
        ########################
        # Not for personal
        ["Total AUD Balance"] + [f"{data[d]['audBalance']:.2f}" for d in dates],
        ["Total"] + [f"{data[d]['total'] + data[d]['audBalance']:.2f}" for d in dates],
        # end not for personal
        ##########################3
    ])

    writer.writerows([
        [""],
        ["Total Purchases"] + [f"{data[d]['buys']:.2f}" for d in dates],
        ["Total Sales"] + [f"{data[d]['sales']:.2f}" for d in dates],
        ['Total Income'] + [f"{data[d]['income']:.2f}" for d in dates],
        ["Total Spends"] + [f"{data[d]['spends']:.2f}" for d in dates],
    ])

    ##################
    # for Stardust
    writer.writerows([
        [""],
        ["Total Capital Gains"],
        ["Assets held more than 1 year"] + [f"{data[d]['cgt']['gain1yrPlus']:.2f}" for d in dates],
        ["Assets held less than 1 year"] + [f"{data[d]['cgt']['gain1yrMinus']:.2f}" for d in dates],
        [""],
        ["Total Capital Losses"] + [f"{data[d]['cgt']['loss']:.2f}" for d in dates],
    ])

    # end for stardust
    #####################3

    #####################
    # for personal

    # writer.writerows([
    #     [""],
    #     ["Total Gross Capital Gains", f"{totalGrossGains:.2f}"],
    #     ["Total Gross Capital Losses", f"{totalGrossLosses:.2f}"],
    #     ["After applying losses carried forward and CGT discount where applicable"],
    #     ["Total Net Capital Gain", f"{totalNetGains:.2f}"],
    #     ["Total Net Capital Loss", f"{totalNetLosses:.2f}"],
    # ])

    # end for personal
    #####################


    costs = CostBasis.objects.filter(user=user, date__lte=endDate)
    totalCost = 0
    # NOTE: This only works because we know CGT has only been calculated until the end date. This won't work if it's not the most recent
    costOfRemaining = 0
    for cb in costs:
        if cb.sourceString().startswith("Purchase"):
            totalCost += cb.units * cb.unitPrice
            costOfRemaining += cb.remaining * cb.unitPrice

    costRemaining = costs.filter(remaining__gte=0).aggregate(t=Sum((F('remaining') * F('unitPrice'))))['t']
    costs = costs.annotate(sold=F('units') - F('remaining'))
    costSold = costs.filter(remaining__gte=0).aggregate(t=Sum((F('sold') * F('unitPrice'))))['t']

    proceeds = Sale.objects.filter(user=user, date__lte=endDate).aggregate(
        proceeds=Sum((F("units") * F("unitPrice")) - F("feeAUD")))['proceeds']

    writer.writerows([
        [""],
        ['Cost and Proceeds'],
        ['Total Cost of Purchases', f'{totalCost:.2f}'],
        ['Total Proceeds of Sales', f'{proceeds:.2f}'],
        [f"Cost of Cryptos held at {endDate.strftime('%d/%m/%Y')}", f'{costOfRemaining:.2f}'],
        ['costRemaining', f'{costRemaining:.2f}'],
        ['costSold', f'{costSold:.2f}'],
    ])


    ##################
    # for stardust

    # Fees
    writer.writerows([
        [""],
        ["Fees"] + [f"{data[d]['fees']['totalFees']:.2f}" for d in dates],
        ["Centralised Exchange Brokerage Fees"] + [f"{data[d]['fees']['brokerageFees']:.2f}" for d in dates],
        ["Centralised Exchange Withdrawal Fees"] + [f"{data[d]['fees']['withdrawalFees']:.2f}" for d in dates],
        ["Onchain Transaction Fees"] + [f"{data[d]['fees']['transactionFees']:.2f}" for d in dates],
    ])

    # AUD transactions
    writer.writerows([
        [""],
        ["AUD Transactions"],
        ["Deposits"] + [f"{data[d]['aud']['deposits']:.2f}" for d in dates],
        ["Withdrawals"] + [f"{data[d]['aud']['withdrawals']:.2f}" for d in dates],
        ["Crypto Purchases (incl Fees)"] + [f"{data[d]['aud']['purchases']:.2f}" for d in dates],
        ["Crypto Sales (incl Fees)"] + [f"{data[d]['aud']['sales']:.2f}" for d in dates],

    ])

    # end for stardust
    ##########################





    writer.writerows([
        [""],
        [f"Allocation as at"],
        ["Asset"] + ["Units", "Value AUD", "%"]*len(dates),
    ])

    for coin in sorted(coins, key=lambda c: c.symbol):
        row = [coin.symbol]
        for d in dates:
            try:
                row += [
                    f"{data[d]['holdings'][coin]['units']:.4f}",
                    f"{data[d]['holdings'][coin]['value']:.2f}",
                    f"{(100 * data[d]['holdings'][coin]['value'] / data[d]['total']):.2f}",
                ]
            except KeyError:
                row += ["0", "0", "0"]
        writer.writerow(row)

    # r = ["Total Crypto Assets"]
    # holdings, total = totalHoldings(endDate, user)
    # r.append(f"${total:.2f}")
    # writer.writerow(["Total Crypto Assets", f"${total:.2f}"])
    # for d in prevYearsDate:
    #     if d < earliestDate:
    #         r.append("$0.00")
    #     else:
    #         _, t = totalHoldings(d, user)
    #         r.append(f"${t:.2f}")

    return buffer

