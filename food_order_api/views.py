from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from .serializers import (
    UserSerializer,
    ProductSerializer,
    OrderSerializer,
    DetailOrderSerializer,
)
from django.utils import timezone
from rest_framework import generics, permissions, status, serializers
from rest_framework import status

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .permissions import UserPermission, DeliveryAgentPermission, AdminPermission
from .models import User as UserModel, Product, Order, OrderItem
from django.db.models import Sum, Count
from .tasks import bulk_create_task
from celery.result import AsyncResult
from django.shortcuts import get_object_or_404


class UserCreateView(generics.CreateAPIView):
    """
    API view for creating a new user profile.

    - Create: POST method to create a new user profile.

    Permissions:
    - Admin users can create users with any user type.
    - Regular users can create users with the 'user' user type.

    Raises:
    - HTTP_201_CREATED: If a new user is successfully created.
    - HTTP_400_BAD_REQUEST: If the data provided for user creation is invalid.

    Returns:
    - Response: A response containing refresh and access tokens upon successful user creation.

    Example:
    ```
    POST /api/users/
    ```
    Example Request:
    ```
    {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
        "user_type": "regular"
    }
    ```
    Example Response:
    ```
    {
        "refresh": "refresh_token_value",
        "access": "access_token_value"
    }
    """
    serializer_class = UserSerializer
    queryset = UserModel.objects.all()

    def post(self, request):
        """
        Create a new user profile and return refresh and access tokens.
        """
        # Check if the user is not authenticated and has no 'is_admin' attribute
        if not all([hasattr(request.user, 'is_admin')]):
            # To prevent anyone from creating an delivery agent as a user
            request.data.update({'user_type': 'user'})
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {"refresh": str(refresh), "access": str(refresh.access_token)},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class UserListView(generics.ListAPIView):
    """
    API view for retrieving a list of user profiles with order details.

    - List: GET method to retrieve a list of user profiles.

    Permissions:
    - Admin users can access this view to retrieve user profiles.

    Raises:
    - HTTP_200_OK: If the list of user profiles is successfully retrieved.

    Returns:
    - Response: A response containing a list of user profiles with associated order details.
    ```
    """
    serializer_class = UserSerializer
    permission_classes = [AdminPermission]

    def get_queryset(self):
        """
        Get the queryset of user profiles based on optional user_type query parameter.
        """
        queryset = UserModel.objects.all()
        user_type = self.request.query_params.get("user_type")
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        return queryset

    def list(self, request):
        """
        Retrieve a list of user profiles with associated order details.
        """
        queryset = self.get_queryset()
        serializer = UserSerializer(queryset, many=True)
        response_data = serializer.data
        for data in response_data:
            data["order_details"] = Order.objects.filter(
                user_id=data.get("id")
            ).aggregate(total_amount=Sum("total_amount"), order_count=Count("id"))
        return Response(response_data)

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and soft deleting user profiles.

    - Retrieve: GET method to retrieve user profile details.
    - Update: PUT method to update user profile details.
    - Soft Delete: DELETE method to deactivate (soft delete) a user profile.

    Permissions:
    - Admin users can perform all actions.
    - Regular users can retrieve and update their own profiles, but cannot delete themselves if they have pending orders.
    - Deletion is not allowed for admin users.

    Soft Deletion:
    - When a user is deleted, their profile is marked as inactive, providing a soft delete behavior.

    Args:
    - pk (int): The primary key of the user profile.

    Raises:
    - PermissionDenied: If a regular user tries to delete another user or delete themselves with pending orders.
    - HTTP_400_BAD_REQUEST: If there are pending orders for the user being deleted.

    Returns:
    - Response: A response indicating the success or failure of the operation.
      - Success (HTTP_204_NO_CONTENT): User profile successfully soft deleted.
      - Failure (HTTP_400_BAD_REQUEST): Details of the error when deletion is not allowed.
    """

    queryset = UserModel.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AdminPermission | UserPermission]
    allowed_methods = ['GET', 'PUT', 'DELETE']

    def destroy(self, request, *args, **kwargs):
        user_id = kwargs.get('pk')
        user = get_object_or_404(UserModel, id=user_id)

        # Check if the user is trying to delete their own profile
        if request.user.is_user and user.id != request.user.id:
            return self.permission_denied(request)

        # Check for pending orders
        pending_orders = Order.objects.filter(user=user_id, delivery_status='pending').exists()
        if request.user.is_user and pending_orders:
            return Response({'error': 'Cannot delete user with pending orders.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the user is an admin
        if request.user.is_admin:
            return Response({'error': 'Cannot delete admin user.'}, status=status.HTTP_400_BAD_REQUEST)

        # Soft delete the user/delivery agent
        user.is_active = False
        user.save()

        return Response({'message': 'User profile soft deleted.'}, status=status.HTTP_204_NO_CONTENT)


from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from .serializers import ProductSerializer
from .permissions import AdminPermission
from rest_framework import serializers

class ProductAPIView(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AdminPermission]

    def create(self, request, *args, **kwargs):
        """
        Create new products.

        Parameters:
        - `name` (str): The name of the product.
        - `price` (float): The price of the product.
        - `description` (str): A brief description of the product.

        Raises:
        - ValidationError: If no properties are found in the request data.

        Returns:
        - Response: A response containing the serialized product data upon successful creation.
        """
        if not request.data:
            raise serializers.ValidationError({"detail": "No properties are found"})
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [AdminPermission | UserPermission]

    def get_serializer_class(self):
        """
        Get the appropriate serializer class based on the request method.

        Returns:
        - DetailOrderSerializer: If the request method is GET.
        - OrderSerializer: If the request method is not GET.
        """
        if self.request.method == "GET":
            return DetailOrderSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """
        Create a new order.

        Parameters:
        - `user` (str): The ID of the user placing the order.
        - `products` (list): A list of dictionaries containing product IDs and quantities.
        - `total_amount` (float): The total amount for the order.
        - `payment_option` (str): The payment option chosen for the order.

        Raises:
        - ValidationError: If the request data is empty or invalid.

        Returns:
        - Response: A response containing the serialized order data upon successful creation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = (
            serializer.validated_data["user"]
            if serializer.validated_data.get("user")
            else self.request.user
        )
        total_amount = serializer.validated_data["total_amount"]
        payment_option = serializer.validated_data["payment_option"]

        order = Order.objects.create(
            user=user, total_amount=total_amount, payment_option=payment_option
        )

        products_data = serializer.validated_data.get("products", [])
        for product_data in products_data:
            product_id = product_data["product"].id
            quantity = product_data["quantity"]
            OrderItem.objects.create(
                order=order, product_id=product_id, quantity=quantity
            )
        headers = self.get_success_headers(serializer.data)

        response_data = serializer.data
        response_data["order_id"] = order.id
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

class OrderItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, or canceling a specific order item.

    - Retrieve: GET method to retrieve detailed information about a specific order item.
    - Update: PATCH method to update the delivery status or assign a delivery agent to an order item.
    - Cancel: PATCH method to cancel an order item (if permitted).

    Permissions:
    - Users must be authenticated to access this view.
    - Users can only cancel their own orders if the order was created within the last thirty minutes.
    - Only delivery agents can update the delivery status.
    - Users cannot cancel orders after the delivery agent has been assigned.

    Raises:
    - HTTP_400_BAD_REQUEST: If the update request is invalid or unauthorized.

    Returns:
    - Response: A response containing the serialized order item data upon successful retrieval or update.
    """
    serializer_class = DetailOrderSerializer
    allowed_methods = ['GET', 'PATCH']
    permission_classes = [permissions.IsAuthenticated]

    def validate_delivery_agent(self, delivery_agent_id):
        """
        Validate the existence of a delivery agent.

        Parameters:
        - `delivery_agent_id` (str): The ID of the delivery agent.

        Raises:
        - ValidationError: If the delivery agent does not exist.

        Returns:
        - UserModel: The validated delivery agent instance.
        """
        try:
            delivery_agent = UserModel.objects.get(
                id=delivery_agent_id, user_type="delivery_agent"
            )
            return delivery_agent
        except UserModel.DoesNotExist:
            raise serializers.ValidationError("User agent does not exist")

    def get_queryset(self):
        """
        Get the queryset for retrieving the order item.

        Returns:
        - QuerySet: The queryset filtered by the order item ID.
        """
        queryset = Order.objects.filter(id=self.kwargs["pk"])
        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve detailed information about a specific order item.

        Returns:
        - Response: A response containing the serialized order item data upon successful retrieval.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Update the delivery status or assign a delivery agent to an order item.

        Parameters:
        - `delivery_status` (str): The new delivery status for the order item.
        - `delivery_agent` (str): The ID of the delivery agent to assign (optional).

        Raises:
        - ValidationError: If the update request is invalid or unauthorized.

        Returns:
        - Response: A response containing the serialized order item data upon successful update.
        """
        instance = self.get_object()

        order_duration = timezone.now() - instance.order_date
        if request.data.get("delivery_status") == "canceled":
            if self.request.user.user_type == "delivery_agent":
                return Response(
                    {"error": "You are not permitted to cancel the order."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

class OTPVerifyView(APIView):
    """
    API view for verifying OTP during order delivery.

    - Verify OTP: POST method to verify the OTP provided during order delivery.

    Permissions:
    - Only delivery agents with the required permission can access this view.

    Raises:
    - HTTP_200_OK: If OTP verification is successful.
    - HTTP_400_BAD_REQUEST: If the OTP is invalid.

    Returns:
    - Response: A response containing a success message or error message based on the OTP verification result.
    """
    permission_classes = [DeliveryAgentPermission]

    def post(self, request, order_id):
        """
        Verify the OTP provided during order delivery.

        Parameters:
        - `order_id` (str): The ID of the order to verify the OTP for.

        Raises:
        - HTTP_200_OK: If OTP verification is successful.
        - HTTP_400_BAD_REQUEST: If the OTP is invalid.

        Returns:
        - Response: A response containing a success message or error message based on the OTP verification result.
        """
        try:
            Order.objects.get(pk=order_id, otp=request.data.get("otp", ""))
            return Response(
                {"message": "OTP verification successful"}, status=status.HTTP_200_OK
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )

class ProductBulkCreateView(generics.CreateAPIView):
    """
    API view for bulk creating products asynchronously using Celery.

    - Bulk Create: POST method to initiate the bulk creation of products.

    Permissions:
    - Only authenticated users can access this view.

    Raises:
    - HTTP_200_OK: If the bulk creation task is successfully initiated.

    Returns:
    - Response: A response containing the task ID for tracking the progress of the bulk creation task.
    """
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Initiate the bulk creation of products asynchronously using Celery.

        Parameters:
        - `request.data` (list): List of product data for bulk creation.

        Raises:
        - HTTP_200_OK: If the bulk creation task is successfully initiated.

        Returns:
        - Response: A response containing the task ID for tracking the progress of the bulk creation task.
        """
        task = bulk_create_task.delay(request.data)
        return Response({"task_id": task.id})

class CheckProgressView(generics.RetrieveAPIView):
    """
    API view for checking the progress of a Celery task.

    - Retrieve: GET method to check the progress of a Celery task.

    Parameters:
    - `task_id` (str): The unique identifier for the Celery task.

    Raises:
    - HTTP_200_OK: If the task is still in progress, returns progress information.
    - HTTP_200_OK: If the task has completed successfully, returns success information.
    - HTTP_500_INTERNAL_SERVER_ERROR: If the task has failed, returns error information.
    - HTTP_500_INTERNAL_SERVER_ERROR: If the task is in an unknown state, returns unknown information.
    """
    def get(self, request, task_id, *args, **kwargs):
        """
        Check the progress of a Celery task.

        Parameters:
        - `task_id` (str): The unique identifier for the Celery task.

        Raises:
        - HTTP_200_OK: If the task is still in progress, returns progress information.
        - HTTP_200_OK: If the task has completed successfully, returns success information.
        - HTTP_500_INTERNAL_SERVER_ERROR: If the task has failed, returns error information.
        - HTTP_500_INTERNAL_SERVER_ERROR: If the task is in an unknown state, returns unknown information.
        """
        # Retrieve the task result using Celery's AsyncResult
        result = AsyncResult(task_id)

        if result.state == "PROGRESS":
            # Task is still in progress, return the progress information
            progress_info = {
                "percent": result.info["percent"],
                "description": result.info["description"],
                "completed": False,
            }
            return Response(progress_info)

        elif result.state == "SUCCESS":
            # Task has completed successfully
            success_info = {
                "percent": 100,
                "description": "Task completed",
                "completed": True,
            }
            return Response(success_info)

        elif result.state == "FAILURE":
            # Task has failed
            error_info = {"error": str(result.result), "completed": True}
            return Response(error_info, status=500)

        else:
            # Task is in an unknown state
            unknown_info = {"error": "Unknown task state", "completed": True}
            return Response(unknown_info, status=500)

