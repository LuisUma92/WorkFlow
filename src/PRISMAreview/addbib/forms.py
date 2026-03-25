from django import forms
from prismadb.models import Bib_entries, Keyword, Referenced_databases


class UploadFileForm(forms.Form):
    file = forms.FileField()
    existing_keyword = forms.ModelChoiceField(
        queryset=Keyword.objects.all(),
        required=False,
        empty_label="Select an existing keyword",
        widget=forms.Select(attrs={'class': 'form-control'}),
        to_field_name='keyword_list'
    )
    new_keyword = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder':
            'Or add a new keyword'})
    )
    database_name = forms.ModelChoiceField(
        queryset=Referenced_databases.objects.all(),
        required=True,
        empty_label='Select an existing database',
        widget=forms.Select(attrs={'class': 'form-control'}),
        to_field_name='name'
        )

    def clean(self):
        cleaned_data = super().clean()
        database = cleaned_data.get('database_name')
        existing_keyword = cleaned_data.get('existing_keyword')
        new_keyword = cleaned_data.get('new_keyword')

        if not existing_keyword and not new_keyword:
            msn = 'You must select an existing keyword or enter a new one.'
            raise forms.ValidationError(msn)
        if existing_keyword and new_keyword:
            msn = 'Please select an existing keyword'
            msn += ' or enter a new one, not both.'
            raise forms.ValidationError(msn)
        if not database:
            msn = 'You must select a database'
            raise forms.ValidationError(msn)

        return cleaned_data

    def get_database(self):
        cleaned_data = super().clean()
        database = cleaned_data.get('database_name')
        return database.__str__()

    def save_keyword(self):
        cleaned_data = super().clean()
        existing_keyword = cleaned_data.get('existing_keyword')
        new_keyword = cleaned_data.get('new_keyword')
        if new_keyword:
            keyword, = Keyword.objects.get_or_create(
                    keyword_list=new_keyword
                    )
            return keyword.__str__()

        return existing_keyword.__str__()


class BibEntryForm(forms.ModelForm):
    class Meta:
        model = Bib_entries
        fields = '__all__'
