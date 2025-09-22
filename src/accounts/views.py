# Create your views here.

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import (
    LoginView as BaseLoginView,
    LogoutView as BaseLogoutView,
    PasswordChangeView as BasePasswordChangeView,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from accounts.forms import SignUpForm


class LogInView(BaseLoginView):
    template_name = "accounts/log_in.html"


class LogOutView(BaseLogoutView): ...


@method_decorator(login_not_required, name="dispatch")
class SignUpView(FormView):
    template_name = "accounts/sign_up.html"
    form_class = SignUpForm

    def dispatch(self, request, *args, **kwargs):
        # Redirect to the index page if the user already authenticated
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        request = self.request
        user = form.save()

        raw_password = form.cleaned_data["password1"]
        user = authenticate(username=user.username, password=raw_password)
        login(request, user)

        return redirect("index")


class DeleteAccountView(View):
    def get(self, request, *args, **kwargs):
        return redirect("index")

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGOUT_REDIRECT_URL)
        user = request.user
        logout(request)
        get_user_model().objects.filter(pk=user.pk).delete()

        return redirect(settings.LOGOUT_REDIRECT_URL)


class DeleteAccountConfirmView(TemplateView):
    template_name = "accounts/delete_account_confirm.html"


class ProfileView(TemplateView):
    template_name = "accounts/profile.html"


class PasswordChangeView(BasePasswordChangeView):
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("accounts:profile")


class ChangeProfileView(UpdateView):
    template_name = "accounts/change_profile.html"
    success_url = reverse_lazy("accounts:profile")
    model = get_user_model()
    fields = [
        "username",
        "email",
        "first_name",
        "last_name",
    ]
