from rest_framework.routers import SimpleRouter

from .onboarding_views import UserAdminViewSet, UserOnboardingViewSet

router = SimpleRouter()
router.register("user-onboarding", UserOnboardingViewSet, basename="user-onboarding")
router.register("users", UserAdminViewSet, basename="erp-user")

urlpatterns = router.urls
