import logging
import re
import smtplib
import time
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework.test import APIClient

from apps.common.mail.constants import ENQUEUE_RETRY_POLICY
from apps.common.models import MailLog
from apps.master.models import Company, Department, Designation, Employee, Unit
from config.celery import app as celery_app

from .models import UserAccessEvent, UserOnboarding
from .onboarding import expire_stale_invitations
from .tasks import send_user_onboarding_email_task

User = get_user_model()

ONBOARDING = "/api/v1/user-onboarding/"
USERS = "/api/v1/users/"
VALIDATE = "/api/v1/auth/activation/validate/"
ACTIVATE = "/api/v1/auth/activation/activate/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
FORGOT = "/api/v1/auth/forgot-password/"
EMPLOYEES = "/api/v1/master/employees/"

FRONTEND = "https://erp.example.com"
STRONG_PASSWORD = "Ledger#Harbor2026"
TOKEN_PATTERN = re.compile(r"/activate-account/([A-Za-z0-9_\-]+)")
CODE_PATTERN = re.compile(r"^ONB-\d{6}$")
SEND_PATH = "apps.common.mail.services.EmailMultiAlternatives.send"
SLOW_SMTP_SECONDS = 2

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "onboarding-tests",
    }
}


def _errors(response):
    return response.data["error"]["detail"]


@override_settings(
    CACHES=LOCMEM_CACHE,
    FRONTEND_URL=FRONTEND,
    USER_INVITE_EXPIRY_HOURS=48,
    DEFAULT_FROM_EMAIL="DYLY ERP <erp@example.com>",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OnboardingTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True

    @classmethod
    def tearDownClass(cls):
        celery_app.conf.task_always_eager = cls._previous_eager
        super().tearDownClass()

    def setUp(self):
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = User.objects.create_user(
            email="super@example.com",
            password="Super#Pass2026",
            role=User.Role.SUPERADMIN,
            first_name="Amit",
            last_name="Gupta",
        )
        cls.admin = User.objects.create_user(
            email="admin@example.com", password="Admin#Pass2026", role=User.Role.ADMIN
        )
        cls.plain = User.objects.create_user(
            email="user@example.com", password="User#Pass2026", role=User.Role.USER
        )
        cls.department = Department.objects.create(name="Purchase")
        cls.designation = Designation.objects.create(name="Manager")
        cls.company = Company.objects.create(name="De-Maithan Ispat Limited")
        cls.unit = Unit.objects.create(name="Jajpur", company=cls.company)
        cls.rajesh = cls.make_employee(
            "Rajesh Kumar",
            "9876500001",
            company_email="rajesh@dmil.com",
            personal_email="rajesh@gmail.com",
        )
        cls.sita = cls.make_employee("Sita Rao", "9876500002", company_email="sita@dmil.com")
        cls.anil = cls.make_employee("Anil Das", "9876500003")

    @classmethod
    def make_employee(cls, name: str, mobile: str, **extra) -> Employee:
        return Employee.objects.create(
            full_name=name,
            department=cls.department,
            designation=cls.designation,
            company=cls.company,
            unit=cls.unit,
            date_of_joining=date(2026, 1, 1),
            location="Jajpur",
            gender="Male",
            mobile_number=mobile,
            **extra,
        )

    def api(self, user=None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def create(self, user, employee, email, role="USER", send=False):
        return self.api(user).post(
            ONBOARDING,
            {"employee_id": employee.pk, "login_email": email, "role": role, "send_invite": send},
            format="json",
        )

    def post_action(self, user, onboarding_id: int, action: str):
        return self.api(user).post(f"{ONBOARDING}{onboarding_id}/{action}/", format="json")

    def last_token(self) -> str:
        match = TOKEN_PATTERN.search(mail.outbox[-1].body)
        self.assertIsNotNone(match, "activation link missing from email")
        return match.group(1)

    def send_invite(self, employee, email, role="USER", actor=None) -> tuple[int, str]:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.create(actor or self.superadmin, employee, email, role, send=True)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"], self.last_token()

    def activate(self, token: str, password: str = STRONG_PASSWORD, confirm: str | None = None):
        return self.api().post(
            ACTIVATE,
            {"token": token, "password": password, "password_confirm": confirm or password},
            format="json",
        )


class RoleSecurityTests(OnboardingTestBase):
    def test_employee_creation_does_not_create_erp_user(self):
        before = User.objects.count()
        response = self.api(self.superadmin).post(
            EMPLOYEES,
            {
                "full_name": "New Joiner",
                "gender": "Male",
                "mobile_number": "9876500099",
                "personal_email": "",
                "date_of_joining": "2026-04-01",
                "location": "Jajpur",
                "department_id": self.department.pk,
                "vertical_id": None,
                "designation_id": self.designation.pk,
                "company_id": self.company.pk,
                "division_id": None,
                "facility_id": None,
                "company_email": "joiner@dmil.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.count(), before)
        self.assertFalse(UserOnboarding.objects.exists())

    def test_me_exposes_assignable_roles(self):
        expectations = {
            self.superadmin: ["SUPERADMIN", "ADMIN", "USER"],
            self.admin: ["USER"],
            self.plain: [],
        }
        for user, roles in expectations.items():
            data = self.api(user).get(ME).data
            self.assertEqual(data["assignable_roles"], roles)
            self.assertEqual(data["can_manage_users"], bool(roles))

    def test_superadmin_can_assign_every_role(self):
        for employee, email, role in (
            (self.rajesh, "rajesh@dmil.com", "SUPERADMIN"),
            (self.sita, "sita@dmil.com", "ADMIN"),
            (self.anil, "anil@dmil.com", "USER"),
        ):
            response = self.create(self.superadmin, employee, email, role)
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["role"], role)

    def test_admin_can_assign_user_only(self):
        self.assertEqual(
            self.create(self.admin, self.rajesh, "r@dmil.com", "ADMIN").status_code, 403
        )
        self.assertEqual(
            self.create(self.admin, self.rajesh, "r@dmil.com", "SUPERADMIN").status_code, 403
        )
        self.assertFalse(UserOnboarding.objects.exists())
        self.assertEqual(
            self.create(self.admin, self.rajesh, "r@dmil.com", "USER").status_code, 201
        )

    def test_admin_cannot_promote_draft_through_patch(self):
        onboarding_id = self.create(self.admin, self.rajesh, "r@dmil.com").data["id"]
        response = self.api(self.admin).patch(
            f"{ONBOARDING}{onboarding_id}/", {"role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserOnboarding.objects.get(pk=onboarding_id).role, "USER")

    def test_admin_cannot_act_on_admin_onboarding(self):
        onboarding_id = self.create(self.superadmin, self.rajesh, "r@dmil.com", "ADMIN").data["id"]
        detail = self.api(self.admin).get(f"{ONBOARDING}{onboarding_id}/").data
        self.assertEqual(detail["allowed_actions"], ["view"])
        self.assertEqual(
            self.post_action(self.admin, onboarding_id, "send-invite").status_code, 403
        )
        self.assertEqual(
            self.api(self.admin).delete(f"{ONBOARDING}{onboarding_id}/").status_code, 403
        )

    def test_admin_cannot_promote_existing_user(self):
        response = self.api(self.admin).post(
            f"{USERS}{self.plain.pk}/change-role/", {"role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.plain.refresh_from_db()
        self.assertEqual(self.plain.role, "USER")

    def test_admin_cannot_deactivate_superadmin(self):
        response = self.api(self.admin).post(f"{USERS}{self.superadmin.pk}/deactivate/")
        self.assertEqual(response.status_code, 403)

    def test_user_role_cannot_use_user_onboarding(self):
        client = self.api(self.plain)
        self.assertEqual(client.get(ONBOARDING).status_code, 403)
        self.assertEqual(client.get(f"{ONBOARDING}stats/").status_code, 403)
        self.assertEqual(client.get(f"{ONBOARDING}employee-options/").status_code, 403)
        self.assertEqual(self.create(self.plain, self.rajesh, "r@dmil.com").status_code, 403)
        self.assertEqual(client.get(USERS).status_code, 403)
        self.assertEqual(client.post(f"{USERS}{self.admin.pk}/deactivate/").status_code, 403)

    def test_anonymous_cannot_use_user_onboarding(self):
        self.assertEqual(self.api().get(ONBOARDING).status_code, 401)

    def test_superadmin_changes_role_with_audit(self):
        response = self.api(self.superadmin).post(
            f"{USERS}{self.plain.pk}/change-role/", {"role": "ADMIN"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        event = UserAccessEvent.objects.get(event="ROLE_CHANGED", user=self.plain)
        self.assertEqual((event.from_value, event.to_value), ("USER", "ADMIN"))
        self.assertEqual(event.actor, self.superadmin)

    def test_deactivated_superadmin_loses_user_administration(self):
        other = User.objects.create_user(
            email="super2@example.com", password="x", role=User.Role.SUPERADMIN
        )
        response = self.api(other).post(f"{USERS}{self.superadmin.pk}/deactivate/")
        self.assertEqual(response.status_code, 200)
        self.superadmin.refresh_from_db()
        self.assertEqual(self.api(self.superadmin).get(ONBOARDING).status_code, 403)


class OnboardingRulesTests(OnboardingTestBase):
    def test_code_is_generated_and_read_only(self):
        first = self.create(self.superadmin, self.rajesh, "r@dmil.com").data
        second = self.create(self.superadmin, self.sita, "s@dmil.com").data
        self.assertRegex(first["onboarding_code"], CODE_PATTERN)
        self.assertNotEqual(first["onboarding_code"], second["onboarding_code"])
        self.api(self.superadmin).patch(
            f"{ONBOARDING}{first['id']}/", {"onboarding_code": "ONB-999999"}, format="json"
        )
        self.assertEqual(
            UserOnboarding.objects.get(pk=first["id"]).onboarding_code, first["onboarding_code"]
        )

    def test_login_email_is_normalized(self):
        data = self.create(self.superadmin, self.rajesh, "  Rajesh.K@DMIL.com ").data
        self.assertEqual(data["login_email"], "rajesh.k@dmil.com")

    def test_duplicate_active_onboarding_for_employee_is_rejected(self):
        self.assertEqual(self.create(self.superadmin, self.rajesh, "a@dmil.com").status_code, 201)
        response = self.create(self.superadmin, self.rajesh, "b@dmil.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("employee_id", _errors(response))

    def test_login_email_must_be_unique(self):
        self.create(self.superadmin, self.rajesh, "shared@dmil.com")
        response = self.create(self.superadmin, self.sita, "SHARED@dmil.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("login_email", _errors(response))
        response = self.create(self.superadmin, self.sita, "admin@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("login_email", _errors(response))

    def test_invalid_email_and_inactive_employee_are_rejected(self):
        self.assertEqual(self.create(self.superadmin, self.rajesh, "not-an-email").status_code, 400)
        self.anil.is_active = False
        self.anil.save()
        response = self.create(self.superadmin, self.anil, "anil@dmil.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("employee_id", _errors(response))

    def test_status_cannot_be_set_manually(self):
        onboarding_id = self.create(self.superadmin, self.rajesh, "r@dmil.com").data["id"]
        self.api(self.superadmin).patch(
            f"{ONBOARDING}{onboarding_id}/", {"status": "ACTIVATED"}, format="json"
        )
        self.assertEqual(UserOnboarding.objects.get(pk=onboarding_id).status, "DRAFT")
        put = self.api(self.superadmin).put(
            f"{ONBOARDING}{onboarding_id}/", {"status": "ACTIVATED"}, format="json"
        )
        self.assertEqual(put.status_code, 405)

    def test_save_draft_sends_no_mail_and_creates_no_user(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.create(self.superadmin, self.rajesh, "r@dmil.com")
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])
        self.assertFalse(MailLog.objects.exists())
        self.assertFalse(User.objects.filter(email="r@dmil.com").exists())

    def test_edit_draft_then_locked_after_send(self):
        onboarding_id = self.create(self.superadmin, self.rajesh, "r@dmil.com").data["id"]
        response = self.api(self.superadmin).patch(
            f"{ONBOARDING}{onboarding_id}/",
            {"login_email": "rajesh@dmil.com", "role": "ADMIN"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            (response.data["login_email"], response.data["role"]), ("rajesh@dmil.com", "ADMIN")
        )
        self.assertEqual(mail.outbox, [])
        with self.captureOnCommitCallbacks(execute=True):
            self.post_action(self.superadmin, onboarding_id, "send-invite")
        response = self.api(self.superadmin).patch(
            f"{ONBOARDING}{onboarding_id}/", {"login_email": "x@dmil.com"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_discard_draft_hides_it_and_frees_employee(self):
        onboarding_id = self.create(self.superadmin, self.rajesh, "r@dmil.com").data["id"]
        self.assertEqual(
            self.api(self.superadmin).delete(f"{ONBOARDING}{onboarding_id}/").status_code, 204
        )
        self.assertFalse(UserOnboarding.objects.get(pk=onboarding_id).is_active)
        self.assertEqual(self.api(self.superadmin).get(ONBOARDING).data["count"], 0)
        self.assertEqual(self.create(self.superadmin, self.rajesh, "r@dmil.com").status_code, 201)

    def test_employee_options_exclude_onboarded_employees(self):
        self.create(self.superadmin, self.rajesh, "r@dmil.com")
        data = self.api(self.superadmin).get(f"{ONBOARDING}employee-options/").data
        codes = {row["employee_code"] for row in data}
        self.assertNotIn(self.rajesh.employee_code, codes)
        self.assertIn(self.sita.employee_code, codes)
        row = next(r for r in data if r["id"] == self.sita.pk)
        self.assertEqual(row["company_email"], "sita@dmil.com")
        self.assertEqual(row["unit"]["name"], "Jajpur")

    def test_list_filters(self):
        self.create(self.superadmin, self.rajesh, "r@dmil.com", "ADMIN")
        self.create(self.superadmin, self.sita, "s@dmil.com", "USER")
        client = self.api(self.superadmin)
        self.assertEqual(client.get(ONBOARDING, {"role": "ADMIN"}).data["count"], 1)
        self.assertEqual(client.get(ONBOARDING, {"search": "sita"}).data["count"], 1)
        self.assertEqual(
            client.get(ONBOARDING, {"department": self.department.pk}).data["count"], 2
        )
        self.assertEqual(client.get(ONBOARDING, {"status": "INVITED"}).data["count"], 0)


class InvitationFlowTests(OnboardingTestBase):
    def test_save_and_send_queues_mail_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", send=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "INVITE_PENDING")
        self.assertEqual(response.data["last_mail_status"], "QUEUED")
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(mail.outbox, [])
        log = MailLog.objects.get()
        self.assertEqual((log.status, log.recipient), ("QUEUED", "rajesh@dmil.com"))
        self.assertTrue(log.celery_task_id)

    def test_invitation_email_is_sent_through_celery(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.status, "INVITED")
        self.assertEqual(onboarding.last_mail_status, "SENT")
        self.assertEqual(onboarding.invite_send_count, 1)
        self.assertIsNotNone(onboarding.invite_sent_at)
        self.assertNotEqual(onboarding.invite_token_hash, token)

        message = mail.outbox[0]
        self.assertEqual(message.to, ["rajesh@dmil.com"])
        self.assertEqual(message.subject, "Welcome to DYLY ERP – Activate Your Account")
        self.assertEqual(message.from_email, "DYLY ERP <erp@example.com>")
        self.assertIn(f"{FRONTEND}/activate-account/{token}", message.body)
        self.assertIn("Rajesh Kumar", message.body)
        html = message.alternatives[0][0]
        self.assertIn("Activate Account", html)

        user = onboarding.user
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.role, "USER")
        self.assertEqual(MailLog.objects.get().status, "SENT")

    def test_invite_expiry_is_configurable(self):
        with override_settings(USER_INVITE_EXPIRY_HOURS=5):
            onboarding_id, _ = self.send_invite(self.rajesh, "rajesh@dmil.com")
        expires = UserOnboarding.objects.get(pk=onboarding_id).invite_expires_at
        self.assertAlmostEqual((expires - timezone.now()).total_seconds(), 5 * 3600, delta=60)

    def test_activation_sets_password_and_allows_login(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        check = self.api().post(VALIDATE, {"token": token}, format="json")
        self.assertEqual(check.status_code, 200)
        self.assertEqual(check.data["employee_name"], "Rajesh Kumar")
        self.assertNotIn("role", check.data)

        response = self.activate(token)
        self.assertEqual(response.status_code, 200, response.data)
        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.status, "ACTIVATED")
        self.assertIsNotNone(onboarding.activated_at)
        self.assertTrue(onboarding.user.is_active)
        self.assertTrue(onboarding.user.password.startswith("pbkdf2_"))

        login = self.api().post(
            LOGIN, {"email": "rajesh@dmil.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(login.status_code, 200)

    def test_token_is_single_use(self):
        _, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        self.assertEqual(self.activate(token).status_code, 200)
        self.assertEqual(self.activate(token, "Another#Pass2026").status_code, 400)
        self.assertEqual(
            self.api().post(VALIDATE, {"token": token}, format="json").status_code, 400
        )

    def test_password_policy_is_enforced(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        weak = self.activate(token, "12345678")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", _errors(weak))
        mismatch = self.activate(token, STRONG_PASSWORD, "Different#Pass2026")
        self.assertEqual(mismatch.status_code, 400)
        self.assertFalse(UserOnboarding.objects.get(pk=onboarding_id).user.is_active)
        self.assertEqual(self.activate(token).status_code, 200)

    def test_expired_invitation_cannot_activate(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        UserOnboarding.objects.filter(pk=onboarding_id).update(
            invite_expires_at=timezone.now() - timedelta(minutes=1)
        )
        check = self.api().post(VALIDATE, {"token": token}, format="json")
        self.assertEqual(check.status_code, 410)
        self.assertIn("expired", check.data["detail"])
        self.assertEqual(self.activate(token).status_code, 410)
        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.status, "EXPIRED")
        self.assertFalse(onboarding.user.is_active)

    def test_scheduled_expiry_marks_invitations_expired(self):
        onboarding_id, _ = self.send_invite(self.rajesh, "rajesh@dmil.com")
        UserOnboarding.objects.filter(pk=onboarding_id).update(
            invite_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(expire_stale_invitations(), 1)
        self.assertEqual(UserOnboarding.objects.get(pk=onboarding_id).status, "EXPIRED")
        stats = self.api(self.superadmin).get(f"{ONBOARDING}stats/").data
        self.assertEqual(stats["expired_invitations"], 1)

    def test_revoked_invitation_cannot_activate(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        response = self.post_action(self.superadmin, onboarding_id, "revoke")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "REVOKED")
        self.assertIsNotNone(response.data["revoked_at"])
        self.assertEqual(self.activate(token).status_code, 400)
        self.assertFalse(UserOnboarding.objects.get(pk=onboarding_id).user.is_active)

    def test_resend_invalidates_old_token_without_duplicates(self):
        onboarding_id, old_token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        users_before = User.objects.count()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_action(self.superadmin, onboarding_id, "resend-invite")
        self.assertEqual(response.status_code, 200, response.data)
        new_token = self.last_token()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(User.objects.count(), users_before)
        self.assertEqual(UserOnboarding.objects.count(), 1)
        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.invite_send_count, 2)
        self.assertIsNotNone(onboarding.last_invite_sent_at)
        self.assertEqual(self.activate(old_token).status_code, 400)
        self.assertEqual(self.activate(new_token).status_code, 200)

    def test_resend_after_expiry_or_revoke_issues_new_token(self):
        onboarding_id, _ = self.send_invite(self.rajesh, "rajesh@dmil.com")
        self.post_action(self.superadmin, onboarding_id, "revoke")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_action(self.superadmin, onboarding_id, "resend-invite")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserOnboarding.objects.get(pk=onboarding_id).status, "INVITED")
        self.assertEqual(self.activate(self.last_token()).status_code, 200)

    def test_actions_depend_on_state(self):
        onboarding_id = self.create(self.superadmin, self.rajesh, "r@dmil.com").data["id"]
        self.assertEqual(
            self.post_action(self.superadmin, onboarding_id, "resend-invite").status_code, 409
        )
        self.assertEqual(
            self.post_action(self.superadmin, onboarding_id, "revoke").status_code, 409
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.post_action(self.superadmin, onboarding_id, "send-invite")
        self.assertEqual(
            self.post_action(self.superadmin, onboarding_id, "send-invite").status_code, 409
        )
        self.activate(self.last_token())
        detail = self.api(self.superadmin).get(f"{ONBOARDING}{onboarding_id}/").data
        self.assertEqual(detail["allowed_actions"], ["view", "deactivate_user", "edit_access"])
        self.assertEqual(
            self.post_action(self.superadmin, onboarding_id, "revoke").status_code, 409
        )
        events = [event["event"] for event in detail["events"]]
        for expected in ("ONBOARDING_CREATED", "INVITE_QUEUED", "INVITE_SENT", "ACCOUNT_ACTIVATED"):
            self.assertIn(expected, events)


class MailFailureTests(OnboardingTestBase):
    def test_transient_smtp_failure_retries_then_keeps_onboarding_retryable(self):
        with mock.patch(SEND_PATH, side_effect=smtplib.SMTPServerDisconnected("down")):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", send=True)
            onboarding_id = response.data["id"]
        log = MailLog.objects.get()
        self.assertEqual(log.status, "FAILED")
        self.assertEqual(log.attempts, send_user_onboarding_email_task.max_retries + 1)
        self.assertIn("SMTPServerDisconnected", log.failure_reason)

        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.status, "INVITE_PENDING")
        self.assertEqual(onboarding.last_mail_status, "FAILED")
        self.assertEqual(onboarding.invite_token_hash, "")
        detail = self.api(self.superadmin).get(f"{ONBOARDING}{onboarding_id}/").data
        self.assertIn("resend_invite", detail["allowed_actions"])

        with self.captureOnCommitCallbacks(execute=True):
            retry = self.post_action(self.superadmin, onboarding_id, "resend-invite")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(UserOnboarding.objects.get(pk=onboarding_id).status, "INVITED")
        self.assertEqual(len(mail.outbox), 1)

    def test_permanent_smtp_failure_is_not_retried(self):
        error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
        with mock.patch(SEND_PATH, side_effect=error):
            with self.captureOnCommitCallbacks(execute=True):
                self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", send=True)
        log = MailLog.objects.get()
        self.assertEqual((log.status, log.attempts), ("FAILED", 1))
        self.assertEqual(UserOnboarding.objects.get().status, "INVITE_PENDING")

    def test_unreachable_broker_does_not_fail_committed_request(self):
        with mock.patch.object(
            send_user_onboarding_email_task,
            "apply_async",
            side_effect=OperationalError("no broker"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", send=True)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MailLog.objects.get().status, "FAILED")
        self.assertEqual(UserOnboarding.objects.get().last_mail_status, "FAILED")


def _slow_smtp(*_args, **_kwargs):
    time.sleep(SLOW_SMTP_SECONDS)
    return 1


class AsyncDeliveryTests(OnboardingTestBase):
    """The HTTP request only saves and queues; SMTP happens in the Celery worker."""

    def create_queued_only(self, **kwargs):
        """Run the request and its on-commit hooks with the broker publish captured."""
        with (
            mock.patch.object(send_user_onboarding_email_task, "apply_async") as publish,
            mock.patch(SEND_PATH, side_effect=_slow_smtp) as smtp_send,
        ):
            started = time.perf_counter()
            with self.captureOnCommitCallbacks(execute=True):
                response = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", **kwargs)
            elapsed = time.perf_counter() - started
        return response, elapsed, publish, smtp_send

    def test_request_returns_without_waiting_for_slow_smtp(self):
        response, elapsed, publish, smtp_send = self.create_queued_only(send=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertLess(elapsed, SLOW_SMTP_SECONDS)
        smtp_send.assert_not_called()
        publish.assert_called_once()
        self.assertEqual(response.data["status"], "INVITE_PENDING")
        self.assertEqual(response.data["last_mail_status"], "QUEUED")
        self.assertEqual(MailLog.objects.get().status, "QUEUED")

    def test_publish_is_bounded_and_carries_no_token(self):
        _, _, publish, _ = self.create_queued_only(send=True)
        kwargs = publish.call_args.kwargs
        self.assertIs(kwargs["retry"], True)
        self.assertEqual(kwargs["retry_policy"], ENQUEUE_RETRY_POLICY)
        log = MailLog.objects.get()
        onboarding = UserOnboarding.objects.get()
        self.assertEqual(kwargs["task_id"], log.celery_task_id)
        self.assertEqual(kwargs["args"], [log.pk, onboarding.pk, onboarding.invite_version])
        self.assertEqual(onboarding.invite_token_hash, "")

    def test_mail_tasks_use_the_mail_queue(self):
        # A worker started without -Q consumes every declared queue, including mail.
        self.assertLessEqual({"celery", "mail"}, set(celery_app.amqp.queues))
        router = celery_app.amqp.router
        for name in (
            "accounts.send_user_onboarding_email",
            "accounts.send_password_reset_email",
            "common.mail.send_generic_notification_email",
        ):
            self.assertEqual(router.route({}, name)["queue"].name, "mail", name)
        self.assertNotEqual(router.route({}, "master.process_import_job")["queue"].name, "mail")

    def test_slow_smtp_in_worker_still_delivers_and_updates_status(self):
        with mock.patch(SEND_PATH, side_effect=_slow_smtp):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com", send=True)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MailLog.objects.get().status, "SENT")
        self.assertEqual(UserOnboarding.objects.get().status, "INVITED")

    def test_edit_and_send_is_one_request_without_duplicates(self):
        draft_id = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com").data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api(self.superadmin).patch(
                f"{ONBOARDING}{draft_id}/",
                {"login_email": "rajesh@gmail.com", "send_invite": True},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        onboarding = UserOnboarding.objects.get(pk=draft_id)
        self.assertEqual(
            (onboarding.status, onboarding.login_email), ("INVITED", "rajesh@gmail.com")
        )
        self.assertEqual(len(mail.outbox), 1)

        again = self.post_action(self.superadmin, draft_id, "send-invite")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(User.objects.filter(email="rajesh@gmail.com").count(), 1)
        self.assertEqual(MailLog.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_patch_without_send_invite_keeps_draft(self):
        draft_id = self.create(self.superadmin, self.rajesh, "rajesh@dmil.com").data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api(self.superadmin).patch(
                f"{ONBOARDING}{draft_id}/", {"role": "USER"}, format="json"
            )
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertFalse(MailLog.objects.exists())

    def test_timing_steps_are_logged_without_secrets(self):
        with self.assertLogs("erp.timing", level="INFO") as captured:
            _, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        output = "\n".join(captured.output)
        for step in (
            "onboarding_db_save",
            "invite_queue",
            "onboarding_transaction",
            "mail_enqueue",
            "mail_queue_wait",
            "invite_token",
            "mail_render",
            "smtp_connect",
            "smtp_send",
            "invite_deliver_total",
        ):
            self.assertIn(f"step={step} ", output, step)
        self.assertNotIn(token, output)
        self.assertNotIn("rajesh@dmil.com", output)


class SecurityTests(OnboardingTestBase):
    def test_token_and_password_never_logged_or_stored(self):
        with self.assertLogs(level=logging.DEBUG) as captured:
            logging.getLogger("erp").info("start capture")
            _, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
            self.activate(token)
        output = "\n".join(captured.output)
        self.assertNotIn(token, output)
        self.assertNotIn(STRONG_PASSWORD, output)

        for log in MailLog.objects.all():
            for value in (log.subject, log.failure_reason, log.recipient, log.related_object_id):
                self.assertNotIn(token, value)
        for event in UserAccessEvent.objects.all():
            self.assertNotIn(token, event.from_value + event.to_value)
        self.assertFalse(UserOnboarding.objects.filter(invite_token_hash=token).exists())

    def test_password_is_never_emailed(self):
        _, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        self.activate(token)
        for message in mail.outbox:
            self.assertNotIn(STRONG_PASSWORD, message.body)
            self.assertNotIn("password:", message.body.lower())

    def test_public_errors_are_generic(self):
        response = self.api().post(VALIDATE, {"token": "unknown-token"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"status", "detail"})
        self.assertNotIn("@", response.data["detail"])

    def test_deactivated_user_cannot_login_and_employee_is_unaffected(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        self.activate(token)
        user = UserOnboarding.objects.get(pk=onboarding_id).user
        login = self.api().post(
            LOGIN, {"email": "rajesh@dmil.com", "password": STRONG_PASSWORD}, format="json"
        )
        access = login.data["access"]

        response = self.api(self.superadmin).post(f"{USERS}{user.pk}/deactivate/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])

        denied = self.api().post(
            LOGIN, {"email": "rajesh@dmil.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(denied.status_code, 401)
        stale = APIClient()
        stale.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(stale.get(ME).status_code, 401)

        self.rajesh.refresh_from_db()
        self.assertTrue(self.rajesh.is_active)
        onboarding = UserOnboarding.objects.get(pk=onboarding_id)
        self.assertEqual(onboarding.status, "ACTIVATED")
        self.assertTrue(
            UserAccessEvent.objects.filter(event="USER_DEACTIVATED", user=user).exists()
        )

        self.assertEqual(
            self.api(self.superadmin).post(f"{USERS}{user.pk}/activate/").status_code, 200
        )
        allowed = self.api().post(
            LOGIN, {"email": "rajesh@dmil.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(allowed.status_code, 200)

    def test_invited_user_cannot_be_force_activated(self):
        onboarding_id, _ = self.send_invite(self.rajesh, "rajesh@dmil.com")
        user = UserOnboarding.objects.get(pk=onboarding_id).user
        self.assertEqual(
            self.api(self.superadmin).post(f"{USERS}{user.pk}/activate/").status_code, 409
        )

    def test_cannot_change_own_status_or_role(self):
        client = self.api(self.superadmin)
        self.assertEqual(client.post(f"{USERS}{self.superadmin.pk}/deactivate/").status_code, 409)
        response = client.post(
            f"{USERS}{self.superadmin.pk}/change-role/", {"role": "USER"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_user_list_shows_employee_link(self):
        onboarding_id, token = self.send_invite(self.rajesh, "rajesh@dmil.com")
        self.activate(token)
        data = self.api(self.superadmin).get(USERS, {"search": "rajesh"}).data
        self.assertEqual(data["count"], 1)
        row = data["results"][0]
        self.assertEqual(row["employee"]["employee_code"], self.rajesh.employee_code)
        self.assertEqual(row["onboarding"]["status"], "ACTIVATED")
        self.assertEqual(row["allowed_actions"], ["change_role", "edit_access", "deactivate"])


class ForgotPasswordMailTests(OnboardingTestBase):
    def test_reset_link_is_emailed_not_returned(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api().post(FORGOT, {"email": "user@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("reset_url", response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"{FRONTEND}/reset-password?token=", mail.outbox[0].body)
        self.assertEqual(MailLog.objects.get().status, "SENT")

    def test_unknown_email_gets_same_response_and_no_mail(self):
        with self.captureOnCommitCallbacks(execute=True):
            known = self.api().post(FORGOT, {"email": "user@example.com"}, format="json")
            unknown = self.api().post(FORGOT, {"email": "nobody@example.com"}, format="json")
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
