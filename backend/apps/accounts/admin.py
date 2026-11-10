from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import PasswordResetToken, User, UserAccessEvent, UserOnboarding


class AccountUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "role", "is_active", "is_staff", "is_superuser")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("role", "is_staff", "is_active", "is_superuser")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role"),
            },
        ),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    list_filter = ("used_at",)
    search_fields = ("user__email",)
    readonly_fields = ("user", "token_hash", "created_at", "expires_at", "used_at")


class ReadOnlyAdmin(admin.ModelAdmin):
    """Status changes must go through business actions, never manual edits."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserOnboarding)
class UserOnboardingAdmin(ReadOnlyAdmin):
    list_display = ("onboarding_code", "login_email", "role", "status", "is_active", "created_at")
    list_filter = ("status", "role", "is_active")
    search_fields = ("onboarding_code", "login_email", "employee__employee_code")
    exclude = ("invite_token_hash",)


@admin.register(UserAccessEvent)
class UserAccessEventAdmin(ReadOnlyAdmin):
    list_display = ("event", "onboarding", "user", "actor", "from_value", "to_value", "created_at")
    list_filter = ("event",)
    search_fields = ("user__email", "onboarding__onboarding_code")
