from django import forms
from prismadb.models import Keyword, Rationale_list, Tags


class KeywordSelectionForm(forms.Form):
    keyword_name = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super(KeywordSelectionForm, self).__init__(*args, **kwargs)
        CHOICES = [(key.id, key.keyword_list) for key in Keyword.objects.all()]
        self.fields['keyword_name'].choices = CHOICES


class RationaleSelectionForm(forms.Form):
    rationale = forms.ChoiceField(choices=[])

    new_rationale = forms.CharField(
            max_length=500,
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(RationaleSelectionForm, self).__init__(*args, **kwargs)
        CHOICES = [
                (rationale.id, rationale.rationale_argument)
                for rationale in Rationale_list.objects.all()
                ]
        self.fields['rationale'].choices = CHOICES


class TagForm(forms.Form):
    tags = forms.MultipleChoiceField(
            choices=[],
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    new_tag = forms.CharField(
            max_length=200,
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(TagForm, self).__init__(*args, kwargs)
        self.fields['tags'].choices = [
                (tag.id, tag.tag) for tag in Tags.objects.all()
                ]
