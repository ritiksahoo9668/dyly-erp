from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.access_control.registry import registry_payload
from apps.common.mail.constants import SUBJECTS, MailType
from apps.common.mail.services import create_mail_log, enqueue_on_commit

from .http import client_ip as _client_ip
from .rate_limit import is_rate_limited
from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from .tasks import send_password_reset_email_task
from .tokens import get_valid_reset_token

User = get_user_model()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]
        ip = _client_ip(request)
        rate_key = f"auth:login:{ip}:{email}"

        if is_rate_limited(rate_key, limit=10, window_seconds=900):
            return Response(
                {"detail": "Too many login attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, username=email, password=password)
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class AccessRegistryView(APIView):
    """Module / Submodule / Action definitions for the permission matrix and navigation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"modules": registry_payload()})


class ForgotPasswordView(APIView):
    """Queues a password-reset email. The response never reveals whether the account exists."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        ip = _client_ip(request)
        rate_key = f"auth:forgot:{ip}:{email}"

        if is_rate_limited(rate_key, limit=5, window_seconds=900):
            return Response(
                {"detail": "Too many reset requests. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        payload = {
            "detail": "If an account exists for this email, a password reset link has been sent.",
        }

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            with transaction.atomic():
                mail_log = create_mail_log(
                    mail_type=MailType.PASSWORD_RESET,
                    recipient=user.email,
                    subject=SUBJECTS[MailType.PASSWORD_RESET],
                    related_object=user,
                )
                enqueue_on_commit(send_password_reset_email_task, mail_log, user.pk)
        return Response(payload)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = _client_ip(request)
        rate_key = f"auth:reset:{ip}"
        if is_rate_limited(rate_key, limit=10, window_seconds=900):
            return Response(
                {"detail": "Too many reset attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        record = get_valid_reset_token(serializer.validated_data["token"])
        if record is None:
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = record.user
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])

        return Response({"detail": "Password updated successfully."})
