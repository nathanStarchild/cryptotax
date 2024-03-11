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