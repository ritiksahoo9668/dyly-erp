from django.urls import path
from rest_framework.routers import DefaultRouter

from .summary_views import MasterSummaryView
from .views import (
    CompanyViewSet,
    DepartmentViewSet,
    DesignationViewSet,
    DivisionViewSet,
    EmployeeViewSet,
    FacilityViewSet,
    ImportJobViewSet,
    MaterialCategoryViewSet,
    MaterialGroupViewSet,
    MaterialSubcategoryViewSet,
    MaterialTypeViewSet,
    MaterialViewSet,
    PlantViewSet,
    PurchasingGroupViewSet,
    QcParameterViewSet,
    StockYardViewSet,
    UnitViewSet,
    UomViewSet,
    VendorViewSet,
    VerticalViewSet,
    WeighBridgeViewSet,
)

router = DefaultRouter()
router.register("divisions", DivisionViewSet, basename="division")
router.register("departments", DepartmentViewSet, basename="department")
router.register("designations", DesignationViewSet, basename="designation")
router.register("facilities", FacilityViewSet, basename="facility")
router.register("companies", CompanyViewSet, basename="company")
router.register("units", UnitViewSet, basename="unit")
router.register("verticals", VerticalViewSet, basename="vertical")
router.register("uoms", UomViewSet, basename="uom")
router.register("material-categories", MaterialCategoryViewSet, basename="material-category")
router.register(
    "material-subcategories",
    MaterialSubcategoryViewSet,
    basename="material-subcategory",
)
router.register("material-groups", MaterialGroupViewSet, basename="material-group")
router.register("material-types", MaterialTypeViewSet, basename="material-type")
router.register("materials", MaterialViewSet, basename="material")
router.register("employees", EmployeeViewSet, basename="employee")
router.register("purchasing-groups", PurchasingGroupViewSet, basename="purchasing-group")
router.register("plants", PlantViewSet, basename="plant")
router.register("stock-yards", StockYardViewSet, basename="stock-yard")
router.register("weighbridges", WeighBridgeViewSet, basename="weighbridge")
router.register("qc-parameters", QcParameterViewSet, basename="qc-parameter")
router.register("vendors", VendorViewSet, basename="vendor")
router.register("import-jobs", ImportJobViewSet, basename="import-job")

urlpatterns = [
    path("summary/", MasterSummaryView.as_view(), name="master-summary"),
    *router.urls,
]
