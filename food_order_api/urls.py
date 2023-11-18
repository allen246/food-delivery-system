from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    UserCreateView,
    UserListView,
    UserDetailView,
    ProductAPIView,
    OrderItemDetailView,
    OrderListCreateView,
    OTPVerifyView,
    ProductBulkCreateView,
    CheckProgressView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", ProductAPIView, basename="products")

urlpatterns = [
    # path("api-token-auth/", obtain_auth_token, name="api_token_auth"),
    path("users/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("users/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("user/", UserCreateView.as_view(), name="user"),
    path("users/", UserListView.as_view(), name="user"),
    path("users/<str:pk>/", UserDetailView.as_view(), name="user-detail"),
    path(
        "products/",
        include(router.urls),
    ),
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<str:pk>/", OrderItemDetailView.as_view(), name="order-detail"),
    path(
        "orders/<str:order_id>/verify-otp/", OTPVerifyView.as_view(), name="otp-verify"
    ),
    path("orders/bulk_create/", ProductBulkCreateView.as_view(), name="bulk_create"),
    path(
        "orders/check_progress/<str:task_id>/",
        CheckProgressView.as_view(),
        name="check_progress",
    ),
]
