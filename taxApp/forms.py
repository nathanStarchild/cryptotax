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
