from django import forms
from django.apps import apps


class ModelSelectionForm(forms.Form):
    MODEL_CHOICES = []
    models = apps.get_models()
    for model in models:
        table_name = model._meta.db_table
        if table_name.split('_')[0] == 'prismadb':
            MODEL_CHOICES.append(
                    (model._meta.model_name, model._meta.verbose_name)
                    )

    model_name = forms.ChoiceField(choices=MODEL_CHOICES)
    pk = forms.IntegerField()
