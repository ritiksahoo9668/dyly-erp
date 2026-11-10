from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.access_control.services import set_user_access, user_access_snapshot
from apps.common.timing import timed
from apps.master.models import Employee

from .http import audit_ip, client_ip
from .models import User, UserOnboarding
from .onboarding import (
    ActivationTokenExpired,
    ActivationTokenInvalid,
    activate_account,
    change_user_role,
    check_activation_token,
    create_onboarding,
    discard_draft,
    expire_stale_invitations,
    queue_invitation,
    revoke_invitation,
    set_user_active,
    update_draft,
    user_actions,
)
from .onboarding_serializers import (
    ActivateAccountSerializer,
    ActivationTokenSerializer,
    ChangeRoleSerializer,
    ErpUserSerializer,
    OnboardingEmployeeSerializer,
    UserAccessWriteSerializer,
    UserOnboardingDetailSerializer,
    UserOnboardingSerializer,
    UserOnboardingWriteSerializer,
)
from .permissions import CanManageUsers
from .rate_limit import is_rate_limited

Status = UserOnboarding.Status

EMPLOYEE_OPTIONS_LIMIT = 500
INVALID_LINK_MESSAGE = "This invitation link is invalid or has already been used."
EXPIRED_LINK_MESSAGE = (
    "This invitation has expired. Please contact your ERP administrator for a new invitation."
)
RATE_LIMITED_MESSAGE = "Too many attempts. Try again later."


def _digits(value: str | None) -> int | None:
    raw = (value or "").strip()
    return int(raw) if raw.isdigit() else None


def _too_many() -> Response:
    return Response({"detail": RATE_LIMITED_MESSAGE}, status=status.HTTP_429_TOO_MANY_REQUESTS)


def _onboarding_queryset():
    return UserOnboarding.objects.select_related(
        "employee__department",
        "employee__designation",
        "employee__company",
        "employee__unit",
        "user",
        "created_by",
        "updated_by",
    )


def _user_queryset():
    return User.objects.select_related("onboarding__employee__department")


class UserOnboardingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageUsers]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = _onboarding_queryset().filter(is_active=True)
        params = self.request.query_params

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(onboarding_code__icontains=search)
                | Q(login_email__icontains=search)
                | Q(employee__employee_code__icontains=search)
                | Q(employee__full_name__icontains=search)
            )

        status_filter = (params.get("status") or "").strip().upper()
        if status_filter in Status.values:
            qs = qs.filter(status=status_filter)

        role = (params.get("role") or "").strip().upper()
        if role in User.Role.values:
            qs = qs.filter(role=role)

        mail_status = (params.get("mail_status") or "").strip().upper()
        if mail_status in UserOnboarding.MailStatus.values:
            qs = qs.filter(last_mail_status=mail_status)

        for name in ("department", "company", "unit"):
            value = _digits(params.get(name))
            if value is not None:
                qs = qs.filter(**{f"employee__{name}_id": value})

        account = (params.get("account_status") or "").strip().lower()
        if account == "active":
            qs = qs.filter(user__is_active=True)
        elif account == "inactive":
            qs = qs.filter(Q(user__isnull=True) | Q(user__is_active=False))

        return qs.order_by("-created_at", "-id")

    def get_serializer_class(self):
        if self.action == "list":
            return UserOnboardingSerializer
        return UserOnboardingDetailSerializer

    def _detail(self, onboarding: UserOnboarding, *, code: int = status.HTTP_200_OK) -> Response:
        fresh = _onboarding_queryset().get(pk=onboarding.pk)
        data = UserOnboardingDetailSerializer(fresh, context=self.get_serializer_context()).data
        return Response(data, status=code)

    def list(self, request, *args, **kwargs):
        expire_stale_invitations()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        expire_stale_invitations()
        return super().retrieve(request, *args, **kwargs)

    def create(self, request):
        serializer = UserOnboardingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = audit_ip(request)
        send = bool(data.get("send_invite"))
        with timed("onboarding_api", action="create", send_invite=send):
            # The transaction step includes commit and the on-commit broker publish.
            with timed("onboarding_transaction", action="create"):
                with transaction.atomic():
                    with timed("onboarding_db_save", action="create"):
                        onboarding = create_onboarding(
                            employee=data["employee"],
                            login_email=data["login_email"],
                            role=data["role"],
                            actor=request.user,
                            ip=ip,
                            access=data.get("access"),
                        )
                    if send:
                        with timed("invite_queue", onboarding=onboarding.pk):
                            onboarding = queue_invitation(onboarding, actor=request.user, ip=ip)
            with timed("onboarding_response", onboarding=onboarding.pk):
                return self._detail(onboarding, code=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        onboarding = self.get_object()
        serializer = UserOnboardingWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = audit_ip(request)
        send = bool(data.get("send_invite"))
        with timed("onboarding_api", action="update", send_invite=send, onboarding=onboarding.pk):
            with timed("onboarding_transaction", action="update", onboarding=onboarding.pk):
                with transaction.atomic():
                    with timed("onboarding_db_save", action="update", onboarding=onboarding.pk):
                        onboarding = update_draft(
                            onboarding,
                            actor=request.user,
                            ip=ip,
                            employee=data.get("employee"),
                            login_email=data.get("login_email"),
                            role=data.get("role"),
                            access=data.get("access"),
                        )
                    if send:
                        with timed("invite_queue", onboarding=onboarding.pk):
                            onboarding = queue_invitation(onboarding, actor=request.user, ip=ip)
            with timed("onboarding_response", onboarding=onboarding.pk):
                return self._detail(onboarding)

    def destroy(self, request, pk=None):
        discard_draft(self.get_object(), actor=request.user, ip=audit_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="send-invite")
    def send_invite(self, request, pk=None):
        onboarding = self.get_object()
        with timed("onboarding_api", action="send_invite", onboarding=onboarding.pk):
            with timed("invite_queue", onboarding=onboarding.pk):
                onboarding = queue_invitation(onboarding, actor=request.user, ip=audit_ip(request))
            return self._detail(onboarding)

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, pk=None):
        onboarding = self.get_object()
        if is_rate_limited(
            f"onboarding:resend:{request.user.pk}:{onboarding.pk}", limit=5, window_seconds=900
        ):
            return _too_many()
        with timed("onboarding_api", action="resend_invite", onboarding=onboarding.pk):
            with timed("invite_queue", onboarding=onboarding.pk):
                onboarding = queue_invitation(
                    onboarding, actor=request.user, ip=audit_ip(request), resend=True
                )
            return self._detail(onboarding)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        onboarding = revoke_invitation(self.get_object(), actor=request.user, ip=audit_ip(request))
        return self._detail(onboarding)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        expire_stale_invitations()
        onboardings = UserOnboarding.objects.filter(is_active=True)
        return Response(
            {
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "pending_invitations": onboardings.filter(
                    status__in=[Status.INVITE_PENDING, Status.INVITED]
                ).count(),
                "expired_invitations": onboardings.filter(status=Status.EXPIRED).count(),
            }
        )

    @action(detail=False, methods=["get"], url_path="employee-options")
    def employee_options(self, request):
        """Active employees without an ERP user onboarding (selectable in the form)."""
        qs = (
            Employee.objects.filter(is_active=True)
            .exclude(user_onboardings__is_active=True)
            .select_related("department", "designation", "company", "unit")
            .order_by("employee_code")
        )
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(employee_code__icontains=search) | Q(full_name__icontains=search))
        return Response(OnboardingEmployeeSerializer(qs[:EMPLOYEE_OPTIONS_LIMIT], many=True).data)


class UserAdminViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ERP user accounts: listing, activation/deactivation and role changes."""

    permission_classes = [IsAuthenticated, CanManageUsers]
    serializer_class = ErpUserSerializer

    def get_queryset(self):
        qs = _user_queryset()
        params = self.request.query_params

        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(onboarding__employee__employee_code__icontains=search)
                | Q(onboarding__employee__full_name__icontains=search)
            )

        role = (params.get("role") or "").strip().upper()
        if role in User.Role.values:
            qs = qs.filter(role=role)

        active = (params.get("is_active") or "").strip().lower()
        if active in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif active in {"false", "0"}:
            qs = qs.filter(is_active=False)

        return qs.order_by("email", "id")

    def _respond(self, user: User) -> Response:
        fresh = _user_queryset().get(pk=user.pk)
        return Response(ErpUserSerializer(fresh, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = set_user_active(self.get_object(), True, actor=request.user, ip=audit_ip(request))
        return self._respond(user)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = set_user_active(self.get_object(), False, actor=request.user, ip=audit_ip(request))
        return self._respond(user)

    @action(detail=True, methods=["post"], url_path="change-role")
    def change_role(self, request, pk=None):
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = change_user_role(
            self.get_object(),
            serializer.validated_data["role"],
            actor=request.user,
            ip=audit_ip(request),
        )
        return self._respond(user)

    def _access_response(self, user: User) -> Response:
        full_access = user.role == User.Role.SUPERADMIN
        return Response(
            {
                "user_id": user.pk,
                "role": user.role,
                "full_access": full_access,
                "access": {} if full_access else user_access_snapshot(user),
                "editable": "edit_access" in user_actions(user, self.request.user, None),
            }
        )

    @action(detail=True, methods=["get", "put"], url_path="access")
    def access(self, request, pk=None):
        user = self.get_object()
        if request.method == "PUT":
            serializer = UserAccessWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            set_user_access(
                user,
                serializer.validated_data["access"],
                actor=request.user,
                ip=audit_ip(request),
            )
            user.refresh_from_db()
        return self._access_response(user)


class ActivationValidateView(APIView):
    """Public: check an invitation token before showing the set-password form."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if is_rate_limited(
            f"auth:activation-validate:{client_ip(request)}", limit=30, window_seconds=900
        ):
            return _too_many()
        serializer = ActivationTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": "invalid", "detail": INVALID_LINK_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        check = check_activation_token(serializer.validated_data["token"])
        if check.state == "valid":
            onboarding = check.onboarding
            return Response(
                {
                    "status": "valid",
                    "employee_name": onboarding.employee.full_name,
                    "login_email": onboarding.login_email,
                    "expires_at": onboarding.invite_expires_at,
                }
            )
        if check.state == "expired":
            return Response(
                {"status": "expired", "detail": EXPIRED_LINK_MESSAGE}, status=status.HTTP_410_GONE
            )
        return Response(
            {"status": "invalid", "detail": INVALID_LINK_MESSAGE},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ActivateAccountView(APIView):
    """Public: set the password for an invited account and activate it (single use)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if is_rate_limited(f"auth:activation:{client_ip(request)}", limit=10, window_seconds=900):
            return _too_many()
        serializer = ActivateAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            activate_account(
                serializer.validated_data["token"],
                serializer.validated_data["password"],
                ip=audit_ip(request),
            )
        except ActivationTokenExpired:
            return Response(
                {"status": "expired", "detail": EXPIRED_LINK_MESSAGE}, status=status.HTTP_410_GONE
            )
        except ActivationTokenInvalid:
            return Response(
                {"status": "invalid", "detail": INVALID_LINK_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Account activated successfully."})
