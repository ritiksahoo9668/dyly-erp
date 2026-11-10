from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.common.access_control.constants import Action, Module
from apps.common.access_control.permissions import ModuleAccessPermission, check_document_action
from apps.common.access_control.selectors import get_effective_access
from apps.common.access_control.testing import grant_access

from .models import UserAccessEvent, UserModuleAccess, UserOnboarding, UserSubmoduleAccess
from .test_onboarding import ME, ONBOARDING, USERS, OnboardingTestBase, User

DEPARTMENTS = "/api/v1/master/departments/"
DESIGNATIONS = "/api/v1/master/designations/"
EMPLOYEES = "/api/v1/master/employees/"
REGISTRY = "/api/v1/auth/access-registry/"

RAJESH_ACCESS = {
    "PROCUREMENT": {
        "enabled": True,
        "submodules": {
            "PLANNING": ["VIEW", "CREATE", "EDIT"],
            "INDENT": ["VIEW", "CREATE", "EDIT"],
            "RFQ": ["VIEW", "CREATE"],
            "CS": ["VIEW"],
            "PO": ["VIEW"],
        },
    }
}


class DocumentViewSet(viewsets.ViewSet):
    """Stand-in for a transactional API guarded the way business modules will be."""

    permission_classes = [IsAuthenticated, ModuleAccessPermission]
    access_module = Module.PROCUREMENT
    access_submodule = "INDENT"

    def list(self, request, **kwargs):
        return Response([])

    def create(self, request, **kwargs):
        return Response({}, status=201)

    def partial_update(self, request, pk=None):
        return Response({})

    @action(detail=False, methods=["get"])
    def export(self, request, **kwargs):
        return Response({})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response({})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return Response({})


VIEW_ROUTES = {
    "list": ("get", {"get": "list"}),
    "create": ("post", {"post": "create"}),
    "edit": ("patch", {"patch": "partial_update"}),
    "export": ("get", {"get": "export"}),
    "cancel": ("post", {"post": "cancel"}),
    "approve": ("post", {"post": "approve"}),
}


class AccessTestBase(OnboardingTestBase):
    factory = APIRequestFactory()

    def fresh(self, user) -> User:
        """A new instance, as each real request loads the user again."""
        return User.objects.get(pk=user.pk)

    def put_access(self, actor, target, access):
        return self.api(actor).put(f"{USERS}{target.pk}/access/", {"access": access}, format="json")

    def call(self, user, route: str, submodule: str, module: str = Module.PROCUREMENT) -> int:
        method, actions = VIEW_ROUTES[route]
        view = DocumentViewSet.as_view(actions, access_module=module, access_submodule=submodule)
        request = getattr(self.factory, method)("/doc/1/", {}, format="json")
        force_authenticate(request, user=self.fresh(user))
        return view(request, pk=1).status_code


class GlobalRoleTests(AccessTestBase):
    def test_superadmin_has_full_access_without_rows(self):
        self.assertFalse(UserModuleAccess.objects.filter(user=self.superadmin).exists())
        me = self.api(self.superadmin).get(ME).data
        self.assertEqual(me["access"], {"full_access": True, "modules": {}})
        client = self.api(self.superadmin)
        self.assertEqual(client.get(DEPARTMENTS).status_code, 200)
        self.assertEqual(client.post(DEPARTMENTS, {"name": "Stores"}).status_code, 201)
        for route in VIEW_ROUTES:
            if route != "approve":
                self.assertIn(self.call(self.superadmin, route, "GRN"), {200, 201}, route)

    def test_user_without_access_sees_nothing(self):
        me = self.api(self.plain).get(ME).data
        self.assertEqual(me["access"], {"full_access": False, "modules": {}})
        self.assertEqual(self.api(self.plain).get(DEPARTMENTS).status_code, 403)
        self.assertEqual(self.call(self.plain, "list", "INDENT"), 403)

    def test_admin_access_is_limited_to_assignment(self):
        grant_access(self.admin, Module.MASTER, {"DEPARTMENT": ["VIEW"]})
        client = self.api(self.fresh(self.admin))
        self.assertEqual(client.get(DEPARTMENTS).status_code, 200)
        self.assertEqual(client.get(DESIGNATIONS).status_code, 403)
        self.assertEqual(client.post(DEPARTMENTS, {"name": "Stores"}).status_code, 403)

    def test_unauthenticated_request_rejected(self):
        self.assertEqual(self.api().get(DEPARTMENTS).status_code, 401)
        self.assertEqual(self.api().get(f"{DEPARTMENTS}lookup/").status_code, 401)

    def test_deactivated_user_has_no_access(self):
        grant_access(self.plain, Module.MASTER)
        User.objects.filter(pk=self.plain.pk).update(is_active=False)
        user = self.fresh(self.plain)
        self.assertFalse(get_effective_access(user).has_module(Module.MASTER))
        self.assertEqual(self.api(user).get(DEPARTMENTS).status_code, 403)
        self.assertEqual(self.api(user).get(f"{DEPARTMENTS}lookup/").status_code, 403)


class ActionPermissionTests(AccessTestBase):
    def test_view_only(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["VIEW"]})
        self.assertEqual(self.call(self.plain, "list", "INDENT"), 200)
        for route in ("create", "edit", "export", "cancel"):
            self.assertEqual(self.call(self.plain, route, "INDENT"), 403, route)

    def test_create_without_edit(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["CREATE"]})
        self.assertEqual(self.call(self.plain, "create", "INDENT"), 201)
        self.assertEqual(self.call(self.plain, "list", "INDENT"), 200)
        self.assertEqual(self.call(self.plain, "edit", "INDENT"), 403)

    def test_export_and_cancel_are_separate_permissions(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["EXPORT"]})
        self.assertEqual(self.call(self.plain, "export", "INDENT"), 200)
        self.assertEqual(self.call(self.plain, "cancel", "INDENT"), 403)
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["CANCEL"]})
        self.assertEqual(self.call(self.plain, "cancel", "INDENT"), 200)

    def test_unmapped_actions_such_as_approve_are_denied(self):
        grant_access(self.plain, Module.PROCUREMENT)
        self.assertEqual(self.call(self.plain, "approve", "INDENT"), 403)

    def test_disabled_module_blocks_its_submodules(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["VIEW", "CREATE"]})
        UserModuleAccess.objects.filter(user=self.plain, module_key="PROCUREMENT").update(
            is_enabled=False
        )
        self.assertEqual(self.call(self.plain, "list", "INDENT"), 403)

    def test_disabled_submodule(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["VIEW"], "RFQ": ["VIEW"]})
        UserSubmoduleAccess.objects.filter(user=self.plain, submodule_key="RFQ").update(
            is_enabled=False
        )
        self.assertEqual(self.call(self.plain, "list", "INDENT"), 200)
        self.assertEqual(self.call(self.plain, "list", "RFQ"), 403)

    def test_workflow_action_still_requires_assignment(self):
        grant_access(self.plain, Module.PROCUREMENT)
        for user in (self.fresh(self.plain), self.superadmin):
            with self.assertRaises(PermissionDenied):
                check_document_action(
                    user,
                    module=Module.PROCUREMENT,
                    submodule="INDENT",
                    action=Action.VIEW,
                    workflow_check=lambda: False,
                )
            check_document_action(
                user,
                module=Module.PROCUREMENT,
                submodule="INDENT",
                action=Action.VIEW,
                workflow_check=lambda: True,
            )

    def test_module_access_alone_does_not_grant_document_action(self):
        with self.assertRaises(PermissionDenied):
            check_document_action(
                self.plain,
                module=Module.PROCUREMENT,
                submodule="INDENT",
                action=Action.VIEW,
                workflow_check=lambda: True,
            )


class MasterAccessTests(AccessTestBase):
    def test_lookup_open_to_transaction_user_but_master_restricted(self):
        grant_access(self.plain, Module.PROCUREMENT, {"INDENT": ["VIEW", "CREATE"]})
        client = self.api(self.fresh(self.plain))
        lookup = client.get(f"{DEPARTMENTS}lookup/")
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.data["results"][0]["name"], "Purchase")
        self.assertEqual(client.get(DEPARTMENTS).status_code, 403)
        self.assertEqual(client.post(DEPARTMENTS, {"name": "Stores"}).status_code, 403)
        self.assertEqual(client.get(f"{DEPARTMENTS}template/").status_code, 403)

    def test_employee_lookup_is_slim(self):
        response = self.api(self.plain).get(f"{EMPLOYEES}lookup/", {"search": "rajesh"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data["results"][0]), {"id", "employee_code", "full_name", "is_active"}
        )
        by_mobile = self.api(self.plain).get(f"{EMPLOYEES}lookup/", {"search": "9876500001"})
        self.assertEqual(by_mobile.data["count"], 0)

    def test_create_without_edit_on_master(self):
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["CREATE"]})
        client = self.api(self.fresh(self.plain))
        created = client.post(DEPARTMENTS, {"name": "Stores"})
        self.assertEqual(created.status_code, 201)
        edit = client.patch(f"{DEPARTMENTS}{created.data['id']}/", {"name": "Main Stores"})
        self.assertEqual(edit.status_code, 403)

    def test_edit_does_not_include_activate_deactivate(self):
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["EDIT"]})
        client = self.api(self.fresh(self.plain))
        url = f"{DEPARTMENTS}{self.department.pk}/"
        self.assertEqual(client.patch(url, {"name": "Purchasing"}).status_code, 200)
        self.assertEqual(client.patch(url, {"is_active": False}).status_code, 403)
        self.assertEqual(client.delete(url).status_code, 403)
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["EDIT", "ACTIVATE_DEACTIVATE"]})
        client = self.api(self.fresh(self.plain))
        self.assertEqual(client.patch(url, {"is_active": False}).status_code, 200)

    def test_upload_needs_upload_permission(self):
        template = f"{DEPARTMENTS}template/"
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["VIEW"]})
        self.assertEqual(self.api(self.fresh(self.plain)).get(template).status_code, 403)
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["UPLOAD"]})
        self.assertEqual(self.api(self.fresh(self.plain)).get(template).status_code, 200)

    def test_summary_is_filtered_by_permission(self):
        grant_access(self.plain, Module.MASTER, {"DEPARTMENT": ["VIEW"], "UOM": ["UPLOAD"]})
        data = self.api(self.fresh(self.plain)).get("/api/v1/master/summary/").data
        self.assertEqual(set(data["masters"]), {"department", "uom"})


class AccessAssignmentTests(AccessTestBase):
    def test_registry_has_no_generic_approve(self):
        modules = self.api(self.plain).get(REGISTRY).data["modules"]
        self.assertEqual(
            [m["key"] for m in modules],
            ["DASHBOARD", "PROCUREMENT", "PRODUCTION", "SALES", "HR", "MASTER"],
        )
        actions = {a["key"] for m in modules for s in m["submodules"] for a in s["actions"]}
        self.assertNotIn("APPROVE", actions)

    def test_permission_update_applies_immediately_and_is_audited(self):
        access = {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["CREATE"]}}}
        response = self.put_access(self.superadmin, self.plain, access)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["access"]["MASTER"]["submodules"]["DEPARTMENT"], ["VIEW", "CREATE"]
        )
        self.assertEqual(self.api(self.fresh(self.plain)).get(DEPARTMENTS).status_code, 200)
        event = UserAccessEvent.objects.get(user=self.plain, permission="MASTER.DEPARTMENT.CREATE")
        self.assertEqual(
            (event.event, event.from_value, event.to_value, event.actor_id),
            (UserAccessEvent.Event.ACTION_PERMISSION_CHANGED, "OFF", "ON", self.superadmin.pk),
        )

        self.assertEqual(self.put_access(self.superadmin, self.plain, {}).status_code, 200)
        self.assertEqual(self.api(self.fresh(self.plain)).get(DEPARTMENTS).status_code, 403)
        self.assertTrue(
            UserAccessEvent.objects.filter(
                user=self.plain, event=UserAccessEvent.Event.MODULE_ACCESS_CHANGED, to_value="OFF"
            ).exists()
        )

    def test_invalid_access_rejected(self):
        for access in (
            {"FINANCE": {"enabled": True}},
            {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["APPROVE"]}}},
            {"PROCUREMENT": {"enabled": True, "submodules": {"INDENT": ["UPLOAD"]}}},
            {"MASTER": {"enabled": "yes"}},
            ["MASTER"],
        ):
            self.assertEqual(self.put_access(self.superadmin, self.plain, access).status_code, 400)

    def test_admin_can_only_grant_access_it_holds(self):
        grant_access(self.admin, Module.MASTER, {"DEPARTMENT": ["VIEW", "CREATE"]})
        admin = self.fresh(self.admin)
        allowed = {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["CREATE"]}}}
        self.assertEqual(self.put_access(admin, self.plain, allowed).status_code, 200)
        for denied in (
            {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["EDIT"]}}},
            {"MASTER": {"enabled": True, "submodules": {"DESIGNATION": ["VIEW"]}}},
            {"PROCUREMENT": {"enabled": True}},
        ):
            self.assertEqual(self.put_access(admin, self.plain, denied).status_code, 403)

    def test_admin_cannot_edit_own_admin_or_superadmin_access(self):
        grant_access(self.admin, Module.MASTER)
        admin = self.fresh(self.admin)
        other_admin = User.objects.create_user(
            email="admin2@example.com", password="Admin#Pass2026", role=User.Role.ADMIN
        )
        access = {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["VIEW"]}}}
        self.assertEqual(self.put_access(admin, admin, access).status_code, 403)
        self.assertEqual(self.put_access(admin, other_admin, access).status_code, 403)
        self.assertEqual(self.put_access(admin, self.superadmin, access).status_code, 403)

    def test_superadmin_accounts_have_no_editable_access(self):
        other = User.objects.create_user(
            email="super2@example.com", password="Super#Pass2026", role=User.Role.SUPERADMIN
        )
        access = {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["VIEW"]}}}
        self.assertEqual(self.put_access(self.superadmin, other, access).status_code, 400)
        detail = self.api(self.superadmin).get(f"{USERS}{other.pk}/access/").data
        self.assertEqual((detail["full_access"], detail["editable"]), (True, False))

    def test_user_cannot_modify_permissions(self):
        grant_access(self.plain, Module.MASTER)
        other = User.objects.create_user(email="u2@example.com", password="User#Pass2026")
        access = {"MASTER": {"enabled": True, "submodules": {"DEPARTMENT": ["VIEW"]}}}
        plain = self.fresh(self.plain)
        self.assertEqual(self.put_access(plain, other, access).status_code, 403)
        self.assertEqual(self.put_access(plain, plain, access).status_code, 403)

    def test_admin_cannot_put_ungranted_access_into_onboarding(self):
        grant_access(self.admin, Module.MASTER, {"DEPARTMENT": ["VIEW"]})
        before = UserOnboarding.objects.count()
        response = self.api(self.fresh(self.admin)).post(
            ONBOARDING,
            {
                "employee_id": self.sita.pk,
                "login_email": "sita@dmil.com",
                "role": "USER",
                "access": RAJESH_ACCESS,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserOnboarding.objects.count(), before)

    def test_switching_draft_to_superadmin_clears_module_access(self):
        response = self.api(self.superadmin).post(
            ONBOARDING,
            {
                "employee_id": self.sita.pk,
                "login_email": "sita@dmil.com",
                "role": "USER",
                "access": RAJESH_ACCESS,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn("PROCUREMENT", response.data["access"])
        url = f"{ONBOARDING}{response.data['id']}/"
        updated = self.api(self.superadmin).patch(url, {"role": "SUPERADMIN"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["access"], {})


class RajeshAcceptanceTests(AccessTestBase):
    def onboard_rajesh(self) -> User:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api(self.superadmin).post(
                ONBOARDING,
                {
                    "employee_id": self.rajesh.pk,
                    "login_email": "rajesh@dmil.com",
                    "role": "USER",
                    "send_invite": True,
                    "access": RAJESH_ACCESS,
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.data)
        onboarding = UserOnboarding.objects.get(pk=response.data["id"])
        self.assertIsNotNone(onboarding.user_id)
        self.assertEqual(self.activate(self.last_token()).status_code, 200)
        return self.fresh(onboarding.user)

    def test_access_survives_invite_and_activation(self):
        rajesh = self.onboard_rajesh()
        self.assertTrue(rajesh.is_active)
        access = self.api(rajesh).get(ME).data["access"]
        self.assertFalse(access["full_access"])
        self.assertEqual(list(access["modules"]), ["PROCUREMENT"])
        submodules = access["modules"]["PROCUREMENT"]["submodules"]
        self.assertEqual(list(submodules), ["PLANNING", "INDENT", "RFQ", "CS", "PO"])
        self.assertEqual(submodules["RFQ"]["actions"], ["VIEW", "CREATE"])

    def test_permitted_and_denied_actions(self):
        rajesh = self.onboard_rajesh()
        for sub in ("PLANNING", "INDENT", "RFQ"):
            self.assertEqual(self.call(rajesh, "create", sub), 201, sub)
        for sub in ("CS", "PO"):
            self.assertEqual(self.call(rajesh, "list", sub), 200, sub)
            self.assertEqual(self.call(rajesh, "create", sub), 403, sub)
            self.assertEqual(self.call(rajesh, "edit", sub), 403, sub)
        for sub in ("GATE_ENTRY", "WEIGHBRIDGE", "QC", "GRN"):
            self.assertEqual(self.call(rajesh, "list", sub), 403, sub)
        for module, sub in ((Module.SALES, "INVOICE"), (Module.PRODUCTION, "PLANNING")):
            self.assertEqual(self.call(rajesh, "list", sub, module=module), 403)
        self.assertFalse(get_effective_access(rajesh).has_module(Module.HR))

    def test_approval_still_depends_on_workflow(self):
        rajesh = self.onboard_rajesh()
        with self.assertRaises(PermissionDenied):
            check_document_action(
                rajesh,
                module=Module.PROCUREMENT,
                submodule="INDENT",
                action=Action.VIEW,
                workflow_check=lambda: False,
            )
