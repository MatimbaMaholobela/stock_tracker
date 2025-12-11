from django import forms
from .models import Organisation
import pandas as pd
from datetime import datetime

class StockDataUploadForm(forms.Form):

    file = forms.FileField(label='upload file in excel or csv format')
    organisation = forms.ModelChoiceField(
        queryset=Organisation.objects.all(),
        required=False,
        help_text="select existing organisation or leave blank to create from file"
    )
    ticker_column = forms.CharField(
        max_length=100,
        initial='ticker',
        help_text="ticker column name"
    )
    date_column = forms.CharField(
        max_length=100,
        initial='date',
  
    )
    price_column = forms.CharField(
        max_length=100,
        initial='close',
        help_text="closing prices"
    )
    
    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.endswith(('.csv', '.xlsx', '.xls')):
            raise forms.ValidationError('Only CSV and Excel files are allowed.')
        return file