from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
        )
        field_classes = {"username": UsernameField}
