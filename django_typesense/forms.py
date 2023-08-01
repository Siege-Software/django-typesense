from django import forms
from django.core.exceptions import ValidationError


class SearchForm(forms.Form):
    id = forms.IntegerField(required=True)

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields")
        model = kwargs.pop("model")

        if not all([fields, model]):
            raise ValidationError("Please pass the model and list fields")

        super().__init__(*args, **kwargs)
        for field in fields:
            typesense_field_dict_list = list(
                filter(lambda f: f["name"] == field, model.typesense_fields)
            )

            if not typesense_field_dict_list:
                raise IndexError(
                    f"The field {field} does not exist in your Typesense fields, please add it to the model or remove"
                    f" the field from the admin list fields"
                )

            self.fields[field] = forms.CharField(required=False)
