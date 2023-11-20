from rest_framework import serializers
from django.utils.crypto import get_random_string
from .models import User, Product, Order, OrderItem
from django.template.loader import render_to_string
from .communication import send_mail


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "phone",
            "user_type",
            "date_joined",
            "is_active",
        )
        read_only_fields = ["date_joined"]
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "is_active": {"required": False},
        }

    def create(self, validated_data):
        if not validated_data.get("password"):
            validated_data.update({"password": get_random_string(length=8)})
        user = User.objects.create_user(**validated_data)
        message = render_to_string('email/account creation.txt', {'account': {
            "user": user.username,
            "email": user.email,
            "password": validated_data["password"]
            }})
        send_mail.delay("Your Account Information", message, [user.email])
        return user


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "image"]
        read_only_fields = ["id"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product", "quantity"]


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "products",
            "order_date",
            "total_amount",
            "payment_option",
            "delivery_status",
            "delivery_agent",
        ]
        read_only_fields = ["order_date"]
        extra_kwargs = {
            "delivery_status": {"required": False},
            "user": {"required": False},
            "delivery_agent": {"required": False},
        }


class DetailOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "products",
            "order_date",
            "total_amount",
            "payment_option",
            "delivery_status",
            "delivery_agent",
        ]
        read_only_fields = ["order_date"]
        extra_kwargs = {
            "delivery_status": {"required": False},
            "delivery_agent": {"required": False},
        }


class TaskIdSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
