from django import forms
from django.core.validators import RegexValidator
from django.test import client
from django.utils.translation import gettext_lazy as _

# from nuggetApp.models import User as nuggetUser
from taxApp.models import *
# from .validators import validatePdf, weekStringValidator
import datetime

# imports
class UploadExchangeForm(forms.Form):
    CHOICES = [
        ("BTCMarkets", "BTC Markets"),
        ("binanceTrades", "Binance Trades"),
        ("binanceAll", "Binance All"),
        ("swyftx", "swyftx"),
        ("swyftxAUD", "swyftx AUD transactions"),
    ]
    file = forms.FileField(label="CSV file")
    source = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-select'}), choices=CHOICES, label="Source")

class newAddressForm(forms.ModelForm):

    class Meta:
        model = Address
        fields = "__all__"


class newTokenForm(forms.ModelForm):

    class Meta:
        model = Token
        fields = "__all__"

class TokenForm(forms.Form):
    address = forms.CharField(
        label="Token Address",
        validators=[RegexValidator(
            regex=r'^0x[a-fA-F0-9]{40}$',
            message="Invalid token address format. Must be a 40 character hex string starting with '0x'."
        )]
    )
    chain = forms.ModelChoiceField(
        queryset=Chain.objects.all(),
        label="Chain"
    )
    coin_id = forms.IntegerField(label="Coin", required=False)

class TxForm(forms.Form):
    hash = forms.CharField(label="Transaction Hash",)
    chain = forms.ModelChoiceField(
        queryset=Chain.objects.all(),
    )

class TtxForm(forms.Form):
    tx_hash = forms.CharField(label="Transaction Hash",)
    coin_id = forms.IntegerField(label="Coin")
    token_address = forms.CharField(label="Token Address")
    from_address = forms.CharField(label="From Address")
    to_address = forms.CharField(label="To Address")
    quantity = forms.DecimalField(label="Quantity")

class DateAndCoinForm(forms.Form):
    fromDate = forms.DateField(
        label="From Date",
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
        required=False,
    )
    toDate = forms.DateField(
        label="To Date",
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
        required=False,
    )

    coin = forms.ModelChoiceField(
        queryset=Coin.objects.all(),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        if not self._errors:
            start_date = cleaned_data.get("fromDate")
            end_date = cleaned_data.get("toDate")
            if start_date is None or end_date is None:
                return
            if end_date < start_date:
                raise forms.ValidationError("End date must be greater than start date.")

class DexTradeForm(forms.Form):
    bought_coin = forms.ModelChoiceField(Coin.objects.all(), label="Bought Coin")
    bought_units = forms.DecimalField(label="Bought Units")
    sold_coin = forms.ModelChoiceField(Coin.objects.all(), label="Sold Coin")
    sold_units = forms.DecimalField(label="Sold Units")
    date = forms.DateTimeField(label="Date")
    fee = forms.DecimalField(label="Fee")
    fee_coin = forms.ModelChoiceField(Coin.objects.all(), label="Fee Coin")
    note = forms.CharField(label="Note", required=False)
