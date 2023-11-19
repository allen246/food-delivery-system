from .utils import generate_uuid_with_prefix
from django.db import models
from .communication import send_mail
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.crypto import get_random_string
from django.db.models.signals import post_save, post_init


class UserManager(BaseUserManager):
    def create_user(
        self,
        username,
        email,
        phone,
        user_type,
        password,
        is_staff=False,
        is_superuser=False,
    ):
        if not email:
            raise ValueError("User must have an email")
        if not username:
            raise ValueError("User must have an username")
        if not user_type:
            raise ValueError("User must have an user_type")

        user = self.model(email=self.normalize_email(email))
        user.username = username
        user.phone = phone
        user.user_type = user_type
        user.set_password(password)
        user.is_active = True
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        return user

    def create_superuser(self, username, email, phone, password, user_type="admin"):
        user = self.create_user(
            username=username,
            email=email,
            phone=phone,
            user_type=user_type,
            password=password,
            is_staff=True,
            is_superuser=True,
        )
        return user


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("admin", "Admin"),
        ("delivery_agent", "Delivery Agent"),
        ("user", "User"),
    )

    id = models.CharField(primary_key=True, max_length=60, unique=True, editable=False)
    phone = models.CharField(max_length=60, blank=True, null=True)
    user_type = models.CharField(
        max_length=60, choices=USER_TYPE_CHOICES, default="user"
    )
    email = models.EmailField(unique=True)
    objects = UserManager()

    @property
    def is_admin(self):
        return self.user_type == "admin"

    @property
    def is_delivery_agent(self):
        return self.user_type == "delivery_agent"

    @property
    def is_user(self):
        return self.user_type == "user"

    def save(self, *args, **kwargs):
        if not self.id:
            # Generate and set the UUID with a prefix only if the ID is not already set
            self.id = generate_uuid_with_prefix("usr")
        super().save(*args, **kwargs)


class Product(models.Model):
    id = models.CharField(primary_key=True, max_length=60, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.URLField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            # Generate and set the UUID with a prefix only if the ID is not already set
            self.id = generate_uuid_with_prefix("pro")
        super().save(*args, **kwargs)


class Order(models.Model):
    DELIVERY_STATUS = (
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("delivered", "Delivery"),
        ("canceled", "Cancelled"),
    )
    id = models.CharField(primary_key=True, max_length=60, unique=True, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="customer_orders"
    )
    products = models.ManyToManyField(
        Product, through="OrderItem", related_name="product_items"
    )
    order_date = models.DateTimeField(auto_now_add=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_status = models.CharField(
        max_length=20, choices=DELIVERY_STATUS, default="pending"
    )
    otp = models.CharField(max_length=8)
    payment_option = models.CharField(max_length=20)
    delivery_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_orders",
    )

    previous_delivery_status = None

    def __str__(self):
        return f"Order {self.id} by {self.user.username} on {self.order_date}"

    def save(self, *args, **kwargs):
        if not self.id:
            # Generate and set the UUID with a prefix only if the ID is not already set
            self.id = generate_uuid_with_prefix("ord")
            self.otp = get_random_string(length=8)
            message = (
                f"Hello { self.user.username },\n\n"
                f"Thank you for placing an order with us! Your order details are as follows:\n\n"
                f"Order ID: { self.id }\n"
                f"Total Amount: ${ self.total_amount }\n\n"
                f"We will send you another email once your order is ready for delivery.\n\n"
                f"To verify your order for Order ID: { self.id }, please use the following OTP:\n\n"
                f"OTP: { self.otp }\n\n"
                f"Please provide this OTP to the delivery agent during the delivery process.\n\n"
                f"Regards,\n"
                f"Swiggy"
            )
            send_mail.delay("Order Confirmation", message, [self.user.email])
        super().save(*args, **kwargs)

    @staticmethod
    def remember_state(sender, instance, **kwargs):
        instance.previous_delivery_status = instance.delivery_status

    @staticmethod
    def post_save(sender, instance, **kwargs):
        if (
            instance.previous_delivery_status != "canceled"
            and instance.delivery_status == "canceled"
        ):
            message = (
                f"Hello {instance.user.username},\n\n"
                f"We regret to inform you that your order with Order ID: {instance.id} has been canceled.\n"
                f"Total Amount: ${instance.total_amount}\n\n"
                f"If you have any concerns or questions, please feel free to contact our customer support.\n\n"
                f"We appreciate your understanding and hope to serve you better in the future.\n\n"
                f"Regards,\n"
                f"Swiggy"
            )
            recipient_emails = [instance.user.email]
            if instance.delivery_agent.email:
                recipient_emails.append(instance.delivery_agent.email)
            send_mail.delay(
                f"Order Cancellation - Order ID: {instance.id}",
                message,
                recipient_emails,
            )


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.id}"


# Signals
post_save.connect(Order.post_save, sender=Order)
post_init.connect(Order.remember_state, sender=Order)
