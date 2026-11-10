from django.urls import path

from .onboarding_views import ActivateAccountView, ActivationValidateView
from .views import AccessRegistryView, ForgotPasswordView, LoginView, MeView, ResetPasswordView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("access-registry/", AccessRegistryView.as_view(), name="auth-access-registry"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path(
        "activation/validate/",
        ActivationValidateView.as_view(),
        name="auth-activation-validate",
    ),
    path("activation/activate/", ActivateAccountView.as_view(), name="auth-activation-activate"),
]
