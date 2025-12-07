from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile, File
from gnosis.eth.django.models import EthereumAddressV2Field as AddressField, Uint256Field, HexV2Field as HexField
from decimal import *
import json
import datetime
from zoneinfo import ZoneInfo

ABIStorage = FileSystemStorage(location="assets/abis", base_url="/static/abis/")

def getABIPath(instance, filename):
    return f"{instance.address}/{filename}"

f = 1e18
#units stored in ETH not wei

class User(models.Model):
    name = models.CharField(max_length=45)
    django_user = models.OneToOneField(
        DjangoUser, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True,
        related_name='cryptoTaxUser'
    ) 

    class Meta:
        managed = True
        db_table = 'users'

    def __str__(self):
        return self.name

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    address = AddressField()

    class Meta:
        managed = True
        db_table = 'addresses'

class Coin(models.Model):
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=120)
    coingecko_id = models.CharField(max_length=120, blank=True, null=True)
    
    class Meta:
        managed = True
        db_table = 'coins'

    def getBalance(self, user, date="now"):
        if date == "now":
            date = datetime.datetime.now().astimezone(ZoneInfo('UTC'))
        bought = self.buy_set.filter(user=user, date__lte=date).aggregate(
            val=models.functions.Coalesce(
                models.Sum('units'),
                Decimal(0)
            )
        )['val']
        income = self.income_set.filter(user=user, date__lte=date).aggregate(
            val=models.functions.Coalesce(
                models.Sum('units'),
                Decimal(0)
            )
        )['val']
        sold = self.sale_set.filter(user=user, date__lte=date).aggregate(
            val=models.functions.Coalesce(
                models.Sum('units'),
                Decimal(0)
            )
        )['val']
        spent = self.spend_set.filter(user=user, date__lte=date).aggregate(
            val=models.functions.Coalesce(
                models.Sum('units'),
                Decimal(0)
            )
        )['val']
        return bought + income - sold - spent

class Chain(models.Model):
    name = models.CharField(max_length=20)
    symbol = models.CharField(max_length=20)
    endpoint = models.CharField(max_length=120)
    explorer = models.CharField(max_length=120, blank=True, null=True)
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True)
    chain_id = models.IntegerField(blank=True, null=True)
    
    class Meta:
        managed = True
        db_table = 'chains'

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

class Token(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)
    address = AddressField(max_length=128)

    class Meta:
        managed = True
        db_table = 'tokens'
        unique_together = ('chain', 'address')

    def explorerUrl(self):
        return f"https://{self.chain.explorer}/address/{self.address}"

class Transaction(models.Model):
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True)
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    hash = models.CharField(max_length=66)
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)
    date = models.DateTimeField()
    processed = models.BooleanField(default=False)
    value = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    note = models.CharField(max_length=128, blank=True, null=True)
    fromAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="transactions_from", blank=True, null=True)
    toAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="transactions_to", blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'transactions'
        unique_together = ('hash', 'chain')

    def explorerUrl(self):
        return f"https://{self.chain.explorer}/tx/{self.hash}"
    
    def createFeeSpend(self):
        if self.fee and self.feeCoin and self.feeAUD:
            s = Spend(
                coin = self.feeCoin,
                units = self.fee,
                unitPrice = self.feeAUD / self.fee,
                date = self.date,
                user = self.fromAddr.user,
                note = f"transaction {self.id}",
                description = f"transaction fee tx {self.hash}"
            )
            s.save()

class InternalTransaction(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    fromAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="internalTxFrom")
    toAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="internalTxTo")
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=79, decimal_places=18)

    class Meta:
        unique_together = ('transaction', 'fromAddr', 'toAddr', 'coin', 'value')

class TokenTransfer(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    fromAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="tokenTransferFrom")
    toAddr = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="tokenTransferTo")
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    token = models.ForeignKey(Token, on_delete=models.CASCADE, blank=True, null=True)
    value = models.DecimalField(max_digits=79, decimal_places=18)

    class Meta:
        unique_together = ('transaction', 'fromAddr', 'toAddr', 'coin', 'value')

class ExchangeWithdrawal(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    unitsSent = models.DecimalField(max_digits=79, decimal_places=18, )
    unitsReceived = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transactionSend = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='withdrawal_send')
    transactionReceive = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='withdrawal_receive')
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True, related_name='withdrawal_fee')
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    refId = models.CharField(max_length=120, blank=True, null=True)
    note = models.CharField(max_length=120, blank=True, null=True)
    txId = models.CharField(max_length=66, blank=True, null=True)
    processed = models.BooleanField(default=False)

    def createFeeSpend(self):
        if self.fee and self.feeCoin and self.feeAUD:
            s = Spend(
                coin = self.coin,
                units = self.fee,
                unitPrice = self.feeAUD / self.fee,
                date = self.date,
                user = self.user,
                note = f"withdrawal {self.id}",
                description = "withdrawal fee"
            )
            s.save()

    def calculateFee(self):
        from taxApp.utils import getPrice
        if self.unitsSent and self.unitsReceived and not self.feeAUD:
            self.fee = self.unitsSent - self.unitsReceived
            price = getPrice(self.feeCoin, self.date)
            self.feeAUD = self.fee * price
            self.save()
            self.createFeeSpend()
            self.processed = True
            self.save()

    def tryToFindReceiveTransaction(self):
        #TODO: convert to use db instead
        from taxApp.importScripts.onchainTransactions import getTransfersInOut
        timeTo = self.date + datetime.timedelta(hours=1)
        timeFrom = self.date - datetime.timedelta(minutes=20)
        print()
        print(self.id)
        print(timeFrom)
        print(timeTo)
        txs = Transaction.objects.filter(
            date__range=(timeFrom, timeTo)
        ).order_by('date')
        print(f"{self.coin.name} {self.coin}")
        print(txs.values('toAddr'))
        print(self.user.address_set.all())
        print(f"found {txs.count()} txs: {txs.values('id')}")
        for tx in txs:
            print(tx)
            incoming, _ = getTransfersInOut(tx, addresses = self.user.address_set.all())
            print(incoming)
            if incoming:
                for inc in incoming:
                    print(f"{inc['coin'].name} {inc['coin']}")
                    if inc['coin'] == self.coin:
                        self.unitsReceived = inc['amount']
                        self.transactionReceive = tx
                        print(f"found transfer in. sent: {self.unitsSent}, received:{self.unitsReceived}")
                        # print(f"tx send: {self.transactionSend.hash} receive: {self.transactionReceive.hash}")
                        self.save()
                        return

class ExchangeAUDTransaction(models.Model):
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=79, decimal_places=2, )
    note = models.CharField(max_length=120, blank=True, null=True)
    refId = models.CharField(max_length=120, blank=True, null=True, unique=True)

class TokenBridge(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    unitsSent = models.DecimalField(max_digits=79, decimal_places=18, )
    unitsReceived = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transactionSend = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='bridge_send')
    transactionReceive = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='bridge_receive')
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True, related_name='bridge_fee')
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    refId = models.CharField(max_length=120, blank=True, null=True)
    note = models.CharField(max_length=120, blank=True, null=True)
    txId = models.CharField(max_length=66, blank=True, null=True)
    processed = models.BooleanField(default=False)

    def calculateFee(self):
        from taxApp.utils import getPrice
        if self.unitsSent and self.unitsReceived and not self.feeAUD:
            self.fee = self.unitsSent - self.unitsReceived
            price = getPrice(self.feeCoin, self.date)
            self.feeAUD = self.fee * price
            self.save()
            self.createFeeSpend()
            self.processed = True
            self.save()

    def createFeeSpend(self):
        if self.fee and self.feeCoin and self.feeAUD:
            s = Spend(
                coin = self.coin,
                units = self.fee,
                unitPrice = self.feeAUD / self.fee,
                date = self.date,
                user = self.user,
                note = f"TokenBridge {self.id}",
                description = "Bridging fee"
            )
            s.save()
        elif self.feeAUD == Decimal(0):
            print("fee is 0")
        else:
            raise ValueError('fee is unkown, cannot create Spend')

    def tryToFindReceiveTransaction(self):
        #TODO: convert to use db instead
        from taxApp.importScripts.onchainTransactions import getTransfersInOut
        timeTo = self.date + datetime.timedelta(hours=1)
        # print(self.date)
        # print(timeTo)
        txs = Transaction.objects.filter(
            date__gt=self.date,
            date__lte=timeTo,
        ).order_by('date')
        # print()
        # print(self.id)
        # print(f"{self.coin.name} {self.coin}")
        # print(txs.values('toAddr'))
        # print(self.user.address_set.all())
        # print(f"found {txs.count()} txs: {txs.values('id')}")
        for tx in txs:
            # print(tx)
            incoming, _ = getTransfersInOut(tx, addresses = self.user.address_set.all())
            # print(incoming)
            if incoming:
                for inc in incoming:
                    # print(f"{inc['coin'].name} {inc['coin']}")
                    if inc['coin'] == self.coin:
                        self.unitsReceived = inc['amount']
                        self.transactionReceive = tx
                        print(f"found transfer in. sent: {self.unitsSent}, received:{self.unitsReceived}")
                        print(f"tx send: {self.transactionSend.hash} receive: {self.transactionReceive.hash}")
                        self.save()
                        return

class Vault(models.Model):
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)
    name = models.CharField(max_length=40, blank=True, null=True)
    address = AddressField()

    class Meta:
        unique_together = ('chain', 'address')

    def explorerUrl(self):
        return f"https://{self.chain.explorer}/address/{self.address}"
    
    def getDeposits(self, date="now"):
        if date == "now":
            date = datetime.datetime.now().astimezone(ZoneInfo('UTC'))
        deposits = self.vaultdeposit_set.filter(transaction__date__lt=date)
        return deposits.aggregate(total=models.functions.Coalesce(models.Sum('amount'), Decimal(0)))['total']
    
    def getWithdrawals(self, date="now"):    
        if date == "now":
            date = datetime.datetime.now().astimezone(ZoneInfo('UTC'))
        withdrawals = self.vaultwithdrawal_set.filter(transaction__date__lt=date)
        return withdrawals.aggregate(total=models.functions.Coalesce(models.Sum('amount'), Decimal(0)))['total']
    
    def getBalance(self, date="now"):
        return self.getDeposits(date) - self.getWithdrawals(date)

class VaultDeposit(models.Model):
    vault = models.ForeignKey(Vault, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=79, decimal_places=18)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('vault', 'transaction')

class VaultWithdrawal(models.Model):
    vault = models.ForeignKey(Vault, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=79, decimal_places=18)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('vault', 'transaction')

class VaultIncome(models.Model):
    vault = models.ForeignKey(Vault, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=79, decimal_places=18)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    income = models.OneToOneField("Income", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        unique_together = ('vault', 'transaction')

    def createIncome(self):
        from taxApp.utils import getPrice
        price = getPrice(self.coin, self.transaction.date)
        i = Income(
            coin = self.coin,
            units = self.amount,
            unitPrice = price,
            date = self.transaction.date,
            user = self.user,
            note = f"Income from {self.vault.name}",
            amount = (self.amount * price) - self.transaction.feeAUD,
            transaction = self.transaction,
        )
        i.save()
        self.income = i
        self.save()
        i.createCostBasis(fee=self.transaction.feeAUD)

class CostBasis(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    remaining = models.DecimalField(max_digits=79, decimal_places=18, )

    class Meta:
        managed = True
        db_table = 'costbases'

    def source(self):
        try:
            return self.buy
        except Buy.DoesNotExist:
            return self.income
        
    def sourceString(self):
        try:
            return f"Purchase {self.buy.id}"
        except Buy.DoesNotExist:
            return f"Income {self.income.id}"

class Buy(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.CharField(max_length=30, blank=True, null=True)
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True, related_name='buy_fee')
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, )
    costBasis = models.OneToOneField(CostBasis, on_delete=models.SET_NULL, blank=True, null=True)
    refId = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'buys'

    def createCostBasis(self):
        c = CostBasis(
            coin = self.coin,
            units = self.units,
            unitPrice = ((self.units * self.unitPrice) + self.feeAUD) / self.units,
            date = self.date,
            user = self.user,
            remaining = self.units,
        )
        c.save()
        self.costBasis = c
        self.save()

    def savePrice(self):
        try:
            HistoricalPrice.objects.get(coin=self.coin, date=self.date)
            return
        except HistoricalPrice.DoesNotExist:
            h = HistoricalPrice(
                coin=self.coin,
                date=self.date,
                price=self.unitPrice
            )
            h.save()

    def fixFee(self):
        if not self.feeCoin:
            return
        from taxApp.utils import getPrice
        feePrice = getPrice(self.feeCoin, self.date)
        feeAUD = feePrice * self.fee
        if abs(feeAUD - self.feeAUD) > Decimal(0.01):
            print(f'fixing {self.note} - {self.fee} {self.feeCoin.name} AUD${self.feeAUD} new fee AUD${feeAUD}')
            self.feeAUD = feeAUD
            self.save()
            self.refresh_from_db()
            self.costBasis.delete()
            self.createCostBasis()

    def total(self):
        return (self.units * self.unitPrice) + self.feeAUD

class Sale(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.CharField(max_length=30, blank=True, null=True)
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True, related_name='sell_fee')
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, )
    refId = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'sales'

    def total(self):
        return (self.units * self.unitPrice) - self.feeAUD

    def savePrice(self):
        try:
            HistoricalPrice.objects.get(coin=self.coin, date=self.date)
            return
        except HistoricalPrice.DoesNotExist:
            h = HistoricalPrice(
                coin=self.coin,
                date=self.date,
                price=self.unitPrice
            )
            h.save()

    def fixFee(self):
        if not self.feeCoin:
            return
        from taxApp.utils import getPrice
        feePrice = getPrice(self.feeCoin, self.date)
        feeAUD = feePrice * self.fee
        if abs(feeAUD - self.feeAUD) > Decimal(0.01):
            print(f'fixing {self.note} - {self.fee} {self.feeCoin.name} AUD${self.feeAUD} new fee AUD${feeAUD}')
            self.feeAUD = feeAUD
            self.save()

class Swap(models.Model):
    buy = models.OneToOneField(Buy, on_delete=models.CASCADE)
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = 'swaps'

class Income(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.CharField(max_length=128, blank=True, null=True)
    amount = models.DecimalField(max_digits=79, decimal_places=2, )
    costBasis = models.OneToOneField(CostBasis, on_delete=models.SET_NULL, blank=True, null=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'incomes'

    def savePrice(self):
        try:
            HistoricalPrice.objects.get(coin=self.coin, date=self.date)
            return
        except HistoricalPrice.DoesNotExist:
            h = HistoricalPrice(
                coin=self.coin,
                date=self.date,
                price=self.unitPrice
            )
            h.save()

    def createCostBasis(self, fee=Decimal(0)):
        c = CostBasis(
            coin = self.coin,
            units = self.units,
            unitPrice = ((self.units * self.unitPrice) + fee) / self.units,
            date = self.date,
            user = self.user,
            remaining = self.units,
        )
        c.save()
        self.costBasis = c
        self.save()

class Spend(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.CharField(max_length=30, blank=True, null=True)
    description = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'spends'

    def savePrice(self):
        try:
            HistoricalPrice.objects.get(coin=self.coin, date=self.date)
            return
        except HistoricalPrice.DoesNotExist:
            h = HistoricalPrice(
                coin=self.coin,
                date=self.date,
                price=self.unitPrice
            )
            h.save()

    def total(self):
        return self.units * self.unitPrice

class CGTEvent(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    costBasis = models.ManyToManyField(CostBasis, blank=True, through="CGTtoCostBasis")
    sale = models.OneToOneField(Sale, on_delete=models.SET_NULL, blank=True, null=True)
    spend = models.OneToOneField(Spend, on_delete=models.SET_NULL, blank=True, null=True)
    gain = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    method = models.CharField(max_length=4, blank=True, null=True)

    def sourceString(self):
        if self.sale:
            return f"Sale {self.sale.id}"
        elif self.spend:
            return f"Disposal {self.spend.id}"
        return "No source recorded!"

class CapitalGain(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.IntegerField()
    gain = models.DecimalField(max_digits=79, decimal_places=2)
    remaining = models.DecimalField(max_digits=79, decimal_places=2, default=Decimal(0))

    class Meta:
        unique_together = ('user', 'year')

class CGTtoCostBasis(models.Model):
    cgtEvent = models.ForeignKey(CGTEvent, on_delete=models.CASCADE)
    costBasis = models.ForeignKey(CostBasis, on_delete=models.CASCADE)
    consumed = models.DecimalField(max_digits=79, decimal_places=18) #CGTEvent.units
    grossGain = models.DecimalField(max_digits=79, decimal_places=2)
    netGain = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    priorLossesApplied = models.ManyToManyField(CapitalGain, through='PriorLossConsumption')
    discountable = models.BooleanField()

class PriorLossConsumption(models.Model):
    cgtToCostBasis = models.ForeignKey(CGTtoCostBasis, on_delete=models.CASCADE)
    capitalGain = models.ForeignKey(CapitalGain, on_delete=models.CASCADE)
    consumed = models.DecimalField(max_digits=79, decimal_places=2)

class HistoricalPrice(models.Model):
    coin =  models.ForeignKey(Coin, on_delete=models.CASCADE)
    date = models.DateTimeField()
    price = models.DecimalField(max_digits=79, decimal_places=18)

class Contract(models.Model):
    address = AddressField()
    abi = models.FileField(
        storage=ABIStorage, 
        upload_to=getABIPath,
    )
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)

    def getABI(self):
        with ABIStorage.open(self.abi.name, mode='r') as f:
            dat = json.load(f)
        try:
            return dat['result']
        except KeyError:
            return dat['abi']
        # return dat['result']
    
    def saveABI(self, datString):
        with open("tmp/tmp.abi", 'w') as f:
            self.abi.save(f"{self.address}.abi", ContentFile(datString), save=False)

    def explorerUrl(self):
        return f"https://{self.chain.explorer}/address/{self.address}"





