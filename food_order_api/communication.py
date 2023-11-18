from django.conf import settings
from django.core.mail import send_mail as dj_send_email
from celery import shared_task


@shared_task
def send_mail(subject, message, recipient_list, **kwargs):
    dj_send_email(
        subject,
        message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=recipient_list,
        **kwargs
    )
