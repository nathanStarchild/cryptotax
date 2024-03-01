from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile, File
from gnosis.eth.django.models import EthereumAddressV2Field as AddressField, Uint256Field, HexV2Field as HexField
from decimal import *
import json


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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = AddressField()

    class Meta:
        managed = True
        db_table = 'addresses'

class Coin(models.Model):
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=120)
    coingecko_id = models.CharField(max_length=120)
    
    class Meta:
        managed = True
        db_table = 'coins'

class Chain(models.Model):
    name = models.CharField(max_length=20)
    symbol = models.CharField(max_length=20)
    endpoint = models.CharField(max_length=120)
    explorer = models.CharField(max_length=120, blank=True, null=True)
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True)
    
    class Meta:
        managed = True
        db_table = 'chains'

class Token(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)
    address = AddressField(max_length=128)

    class Meta:
        managed = True
        db_table = 'tokens'

class Transaction(models.Model):
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True)
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    txHash = models.CharField(max_length=66)
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE)
    date = models.DateTimeField()
    processed = models.BooleanField(default=False)

    class Meta:
        managed = True
        db_table = 'transactions'
        unique_together = ('address', 'txHash', 'chain')

    def explorerUrl(self):
        return f"https://{self.chain.explorer}/tx/{self.txHash}"
    
    def createFeeSpend(self):
        if self.fee and self.feeCoin and self.feeAUD:
            s = Spend(
                coin = self.feeCoin,
                units = self.fee,
                unitPrice = self.feeAUD / self.fee,
                date = self.date,
                user = self.address.user,
                note = f"transaction {self.id}",
                description = f"transaction fee tx {self.txHash}"
            )
            s.save()

class ExchangeWithdrawal(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    unitsSent = models.DecimalField(max_digits=79, decimal_places=18, )
    unitsReceived = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, blank=True, null=True)
    feeCoin = models.ForeignKey(Coin, on_delete=models.CASCADE, blank=True, null=True, related_name='withdrawal_fee')
    fee = models.DecimalField(max_digits=79, decimal_places=18, blank=True, null=True)
    feeAUD = models.DecimalField(max_digits=79, decimal_places=2, blank=True, null=True)
    refId = models.CharField(max_length=120, blank=True, null=True)
    note = models.CharField(max_length=120, blank=True, null=True)
    txId = models.CharField(max_length=66, blank=True, null=True)

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
    note = models.CharField(max_length=30, blank=True, null=True)
    amount = models.DecimalField(max_digits=79, decimal_places=2, )
    costBasis = models.OneToOneField(CostBasis, on_delete=models.CASCADE, blank=True, null=True)

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

class CGTEvent(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    units = models.DecimalField(max_digits=79, decimal_places=18, )
    unitPrice = models.DecimalField(max_digits=79, decimal_places=18, )
    date = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    costBasis = models.ForeignKey(CostBasis, on_delete=models.CASCADE)
    consumed = models.DecimalField(max_digits=79, decimal_places=18, )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, blank=True, null=True)
    spend = models.ForeignKey(Spend, on_delete=models.CASCADE, blank=True, null=True)
    discounted = models.BooleanField()
    gain = models.DecimalField(max_digits=79, decimal_places=2, )

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
        return dat['result']
    
    def saveABI(self, datString):
        with open("tmp/tmp.abi", 'w') as f:
            self.abi.save(f"{self.address}.abi", ContentFile(datString), save=False)





