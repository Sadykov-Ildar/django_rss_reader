from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("log-in/", views.LogInView.as_view(), name="log_in"),
    path("log-out/", views.LogOutView.as_view(), name="log_out"),
    path(
        "sign-up/",
        views.SignUpView.as_view(template_name="accounts/sign_up.html"),
        name="sign_up",
    ),
    path("delete-account/", views.DeleteAccountView.as_view(), name="delete_account"),
    path(
        "delete-account-confirm/",
        views.DeleteAccountConfirmView.as_view(),
        name="delete_account_confirm",
    ),
    path("view-profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "change-profile/<int:pk>",
        views.ChangeProfileView.as_view(),
        name="change_profile",
    ),
    path(
        "change-password/", views.PasswordChangeView.as_view(), name="change_password"
    ),
]
