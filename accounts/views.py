from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import BaseParser, JSONParser
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
import uuid
from rest_framework import filters
from django.db import IntegrityError
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.core.mail import send_mail
from rest_framework.authtoken.models import Token as AuthToken
from django.contrib.auth import authenticate
from rest_framework import serializers
from .serializers import AlertSerializer, UserSerializer, LostFoundItemSerializer, TransactionSerializer, SubscriptionUserSerializer
from .models import Alert, UserProfile, LostFoundItem, Transaction
from google.oauth2 import id_token
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework.permissions import IsAuthenticated
import logging
import pytz
from django.utils.timezone import now

WAT = pytz.timezone('Africa/Lagos')
from rest_framework import generics
from .serializers import AccessCodeSerializer
from .models import AccessCode
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
import json
import hashlib
import hmac
from rest_framework.decorators import api_view
from decimal import Decimal

from rest_framework.parsers import FormParser


from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.parsers import MultiPartParser, FormParser  # Add this import

import os
import uuid
from django.utils.deconstruct import deconstructible

class SubscriptionUsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if estate:
            users = User.objects.filter(profile__is_email_verified=True, profile__estate=estate).distinct()
        else:
            users = User.objects.filter(profile__is_email_verified=True).distinct()

        subscription_users = []

        for user in users:
            amount = user.profile.wallet_balance
            payment_date = None
            subscription_type = user.profile.plan.lower() if user.profile.plan else 'free'

            subscription_users.append({
                'user_id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'payment_amount': amount,
                'subscription_type': subscription_type,
                'payment_date': payment_date,
            })

        serializer = SubscriptionUserSerializer(subscription_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# class UploadProfileImageView(APIView):
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]

#     def post(self, request, format=None):
#         import logging
#         logger = logging.getLogger(__name__)
#         logger.info("UploadProfileImageView POST called")
#         logger.info(f"Request user: {request.user}")
#         logger.info(f"Request files: {request.FILES}")

#         file_obj = request.FILES.get('image')
#         if not file_obj:
#             logger.warning("No image file provided in request")
#             return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)

#         # Generate a unique filename with the original extension
#         ext = os.path.splitext(file_obj.name)[1]  # e.g. '.jpg'
#         unique_filename = f"{uuid.uuid4().hex}{ext}"

#         # Save the file to default storage (e.g., media folder) with unique name
#         file_path = default_storage.save(f'profile_images/{unique_filename}', ContentFile(file_obj.read()))
#         image_url = default_storage.url(file_path)

#         # Prepend base URL to image_url if not absolute
#         base_url = get_base_url()
#         if not image_url.startswith('http'):
#             if image_url.startswith('/'):
#                 image_url = base_url + image_url
#             else:
#                 image_url = base_url + '/' + image_url

#         logger.info(f"Image saved at: {file_path}, URL: {image_url}")

#         return Response({'image_url': image_url}, status=status.HTTP_200_OK)
# accounts/views.py

class UploadProfileImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        logger = logging.getLogger(__name__)
        logger.info("UploadProfileImageView POST called")
        logger.info(f"Request user: {request.user}")
        logger.info(f"Request files: {request.FILES}")

        file_obj = request.FILES.get('image')
        if not file_obj:
            return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # keep original extension
        ext = os.path.splitext(file_obj.name)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"

        # IMPORTANT: stream directly; do NOT read() into ContentFile
        # S3 path under your bucket
        object_key = f'profile_images/{unique_filename}'
        saved_path = default_storage.save(object_key, file_obj)

        # django-storages returns a fully-qualified URL when using S3
        image_url = default_storage.url(saved_path)

        logger.info(f"Image saved at key: {saved_path}, URL: {image_url}")
        return Response({'image_url': image_url}, status=status.HTTP_200_OK)

class UserTransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        transactions = Transaction.objects.filter(user=user).order_by('-date')
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

from django.db import transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import random

OTP_LIFETIME_MINUTES = 10


# class SignupView(APIView):
#     """
#     Signup + email‑OTP verification.
#     """
#     def post(self, request):
#         email      = request.data.get('email', '').strip().lower()
#         otp        = request.data.get('otp', '').strip()
#         first_name = request.data.get('first_name', '').strip()
#         last_name  = request.data.get('last_name', '').strip()
#         password   = request.data.get('password', '').strip()

#         if not all([email, first_name, last_name, password]):
#             return Response(
#                 {'error': 'Email, first name, last name, and password are required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             user = User.objects.get(email=email)
#             profile = user.profile

#             # Already verified?  Bail out early.
#             if profile.is_email_verified:
#                 return Response(
#                     # {'message': 'Email already exist. Please sign in.'},
#                     { "message": "Email already registered. Use a different Email address to sign up." },

#                     status=status.HTTP_200_OK
#                 )

#             # --- Verify OTP ---
#             if otp:
#                 if otp != profile.signup_otp:
#                     return Response(
#                         {'status': 'failure', 'message': 'Invalid OTP'},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#                 if profile.signup_otp_expiry < now():
#                     return Response(
#                         {'status': 'failure', 'message': 'OTP expired'},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 profile.is_email_verified = True
#                 profile.signup_otp = None
#                 profile.signup_otp_expiry = None
#                 profile.save(update_fields=[
#                     'is_email_verified', 'signup_otp', 'signup_otp_expiry'
#                 ])
#                 return Response(
#                     {'status': 'success', 'message': 'Email verified successfully'},
#                     status=status.HTTP_200_OK
#                 )

#             # --- Resend OTP (but don’t regenerate if still valid) ---
#             if profile.signup_otp and profile.signup_otp_expiry > now():
#                 otp_code = profile.signup_otp         # reuse existing
#             else:
#                 otp_code = f"{random.randint(100000, 999999)}"
#                 profile.signup_otp = otp_code
#                 profile.signup_otp_expiry = now() + timedelta(minutes=OTP_LIFETIME_MINUTES)
#                 profile.save(update_fields=['signup_otp', 'signup_otp_expiry'])

#             self._send_signup_otp_email(user.first_name, user.email, otp_code)
#             return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)

#         # ----------------------------------------------------------
#         # New user branch
#         # ----------------------------------------------------------
#         except User.DoesNotExist:
#             with transaction.atomic():
#                 from .serializers import UserSerializer
#                 profile_data = request.data.get('profile', {})
#                 role_value = profile_data.get('role', '').strip()
#                 if role_value.lower() == 'security personnel':
#                     role_value = 'Security Personnel'
#                 elif role_value.lower() == 'residence':
#                     role_value = 'Residence'
#                 else:
#                     role_value = ''  # Invalid role will cause serializer validation error

#                 user_data = {
#                     'email': email,
#                     'first_name': first_name,
#                     'last_name': last_name,
#                     'password': password,
#                     'profile': {
#                         'phone_number': profile_data.get('phone_number', ''),
#                         'role': role_value,
#                         'estate': profile_data.get('estate', ''),
#                         'estate_email': profile_data.get('estate_email', ''),
#                         'house_address': profile_data.get('house_address', ''),
#                         'pin': profile_data.get('pin', ''),
#                         'plan': profile_data.get('plan', ''),
#                         'profile_picture': profile_data.get('profile_picture', ''),
#                         'wallet_balance': 0.0,
#                     }
#                 }
#                 serializer = UserSerializer(data=user_data)
#                 if serializer.is_valid():
#                     user = serializer.save()
#                     profile = user.profile

#                     # Set subscription start and expiry dates based on plan after signup
#                     # from django.utils.timezone import now
#                     plan = profile_data.get('plan', '').lower()
#                     profile.subscription_start_date = now()
#                     if plan == 'monthly':
#                         profile.subscription_expiry_date = now() + timedelta(days=30)
#                     elif plan == 'annual':
#                         profile.subscription_expiry_date = now() + timedelta(days=365)
#                     else:
#                         # For free or unknown plans, set expiry 30 days from now
#                         profile.subscription_expiry_date = now() + timedelta(days=30)
#                     profile.save(update_fields=['signup_otp', 'signup_otp_expiry', 'subscription_start_date', 'subscription_expiry_date'])

#                     print(f"Subscription dates set after signup: start={profile.subscription_start_date}, expiry={profile.subscription_expiry_date}, plan={plan}")

#                     otp_code = f"{random.randint(100000, 999999)}"
#                     profile.signup_otp = otp_code
#                     profile.signup_otp_expiry = now() + timedelta(minutes=OTP_LIFETIME_MINUTES)
#                     profile.save(update_fields=['signup_otp', 'signup_otp_expiry'])
#                 else:
#                     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#             self._send_signup_otp_email(first_name, email, otp_code)
#             return Response(
#                 {'message': 'User created and OTP sent successfully'},
#                 status=status.HTTP_201_CREATED
#             )

#     # ------------------------------------------------------------------
#     # Helper: send e‑mail (kept outside the main logic for clarity)
#     # ------------------------------------------------------------------
#     def _send_signup_otp_email(self, first_name, email, otp_code):
#         send_mail(
#             subject='Your Vaultify Signup OTP',
#             message=f"""Dear {first_name},

#                 You’re just one step away from joining your Estate on Vaultify.
#                 please verify your email address. Here’s why it’s important:
#                     •	Account Protection: Verifying your email helps secure your profile and prevent unauthorized access.
#                     •	Stay Informed: Get important announcements, updates, and alerts from your estate without missing a thing.

#                 To complete your sign‑in, please verify your email address using the OTP below:
#                 Your OTP is: {otp_code}

#                 This OTP expires in {OTP_LIFETIME_MINUTES} minutes.

#                 Warm regards,
#                 The Vaultify Team""",
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=[email],
#             fail_silently=False,
#         )
from django.db import transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import random

# ✅ Added imports
from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage
from django.contrib.auth.models import User  # if already imported elsewhere, keep only one

OTP_LIFETIME_MINUTES = 10

class SignupView(APIView):
    """
    Signup + email-OTP verification.
    """
    def post(self, request):
        email      = request.data.get('email', '').strip().lower()
        otp        = request.data.get('otp', '').strip()
        first_name = request.data.get('first_name', '').strip()
        last_name  = request.data.get('last_name', '').strip()
        password   = request.data.get('password', '').strip()

        if not all([email, first_name, last_name, password]):
            return Response(
                {'error': 'Email, first name, last name, and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            profile = user.profile

            # Already verified?  Bail out early.
            if profile.is_email_verified:
                return Response(
                    { "message": "Email already registered. Use a different Email address to sign up." },
                    status=status.HTTP_200_OK
                )

            # --- Verify OTP ---
            if otp:
                if otp != profile.signup_otp:
                    return Response(
                        {'status': 'failure', 'message': 'Invalid OTP'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if profile.signup_otp_expiry < now():
                    return Response(
                        {'status': 'failure', 'message': 'OTP expired'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                profile.is_email_verified = True
                profile.signup_otp = None
                profile.signup_otp_expiry = None
                profile.save(update_fields=[
                    'is_email_verified', 'signup_otp', 'signup_otp_expiry'
                ])
                return Response(
                    {'status': 'success', 'message': 'Email verified successfully'},
                    status=status.HTTP_200_OK
                )

            # --- Resend OTP (but don’t regenerate if still valid) ---
            if profile.signup_otp and profile.signup_otp_expiry > now():
                otp_code = profile.signup_otp         # reuse existing
            else:
                otp_code = f"{random.randint(100000, 999999)}"
                profile.signup_otp = otp_code
                profile.signup_otp_expiry = now() + timedelta(minutes=OTP_LIFETIME_MINUTES)
                profile.save(update_fields=['signup_otp', 'signup_otp_expiry'])

            self._send_signup_otp_email(user.first_name, user.email, otp_code)
            return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)

        # ----------------------------------------------------------
        # New user branch
        # ----------------------------------------------------------
        except User.DoesNotExist:
            with transaction.atomic():
                from .serializers import UserSerializer
                profile_data = request.data.get('profile', {})
                role_value = profile_data.get('role', '').strip()
                if role_value.lower() == 'security personnel':
                    role_value = 'Security Personnel'
                elif role_value.lower() == 'residence':
                    role_value = 'Residence'
                else:
                    role_value = ''  # Invalid role will cause serializer validation error

                user_data = {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'password': password,
                    'profile': {
                        'phone_number': profile_data.get('phone_number', ''),
                        'role': role_value,
                        'estate': profile_data.get('estate', ''),
                        'estate_email': profile_data.get('estate_email', ''),
                        'house_address': profile_data.get('house_address', ''),
                        'apartment_type': profile_data.get('apartment_type', ''),
                        'pin': profile_data.get('pin', ''),
                        'plan': profile_data.get('plan', ''),
                        'profile_picture': profile_data.get('profile_picture', ''),
                        'wallet_balance': 0.0,
                    }
                }
                serializer = UserSerializer(data=user_data)
                if serializer.is_valid():
                    user = serializer.save()
                    profile = user.profile

                    # Set subscription start and expiry dates based on plan after signup
                    plan = profile_data.get('plan', '').lower()
                    profile.subscription_start_date = now()
                    if plan == 'monthly':
                        profile.subscription_expiry_date = now() + timedelta(days=30)
                    elif plan == 'annual':
                        profile.subscription_expiry_date = now() + timedelta(days=365)
                    else:
                        # For free or unknown plans, set expiry 30 days from now
                        profile.subscription_expiry_date = now() + timedelta(days=30)
                    profile.save(update_fields=['signup_otp', 'signup_otp_expiry', 'subscription_start_date', 'subscription_expiry_date'])

                    print(f"Subscription dates set after signup: start={profile.subscription_start_date}, expiry={profile.subscription_expiry_date}, plan={plan}")

                    otp_code = f"{random.randint(100000, 999999)}"
                    profile.signup_otp = otp_code
                    profile.signup_otp_expiry = now() + timedelta(minutes=OTP_LIFETIME_MINUTES)
                    profile.save(update_fields=['signup_otp', 'signup_otp_expiry'])
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            self._send_signup_otp_email(first_name, email, otp_code)
            return Response(
                {'message': 'User created and OTP sent successfully'},
                status=status.HTTP_201_CREATED
            )

    # ------------------------------------------------------------------
    # Helper: send e-mail (HTML + plain text; top image supported)
    # ------------------------------------------------------------------
    def _send_signup_otp_email(self, first_name: str, email: str, otp_code: str):
        subject = "Verify your email • Vaultify"

        # Decide banner content:
        # 1) Prefer hosted image URL, 2) else CID image if file path provided, 3) else text banner.
        logo_url = getattr(settings, "BRANDING_LOGO_URL", None)
        logo_path = getattr(settings, "BRANDING_LOGO_PATH", None)
        use_cid = False
        if logo_url:
            banner_html = f'<img src="{logo_url}" alt="Vaultify" width="100%" style="display:block; max-height:180px; object-fit:cover;">'
        elif logo_path:
            use_cid = True
            banner_html = '<img src="cid:vaultify_logo" alt="Vaultify" width="100%" style="display:block; max-height:180px; object-fit:cover;">'
        else:
            # graceful fallback if no logo configured
            banner_html = """
            <div style="height:140px; background:#0f172a; color:#fff; display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:700;">
              Vaultify
            </div>
            """

        text_body = (
            f"Dear {first_name},\n\n"
            "You’re just one step away from joining your Estate on Vaultify.\n"
            "Please verify your email address using the OTP below.\n\n"
            f"Your OTP: {otp_code}\n\n"
            f"This OTP expires in {OTP_LIFETIME_MINUTES} minutes.\n\n"
            "Why verify?\n"
            " • Account Protection: Secure your profile and prevent unauthorized access.\n"
            " • Stay Informed: Receive important announcements, updates and alerts from your estate.\n\n"
            "Warm regards,\n"
            "The Vaultify Team"
        )

        html_body = f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{subject}</title>
  </head>
  <body style="margin:0; padding:0; background:#f6f9fc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f6f9fc;">
      <tr>
        <td align="center" style="padding: 32px 12px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px; background:#ffffff; border-radius:14px; overflow:hidden; box-shadow:0 6px 24px rgba(18, 38, 63, 0.06);">
            <!-- Top banner -->
            <tr>
              <td align="center" style="background:#0f172a;">
                {banner_html}
              </td>
            </tr>

            <!-- Header -->
            <tr>
              <td style="padding: 28px 28px 0 28px;">
                <h1 style="margin:0; font-size:22px; line-height:28px; color:#0f172a;">
                  Verify your email, {first_name}
                </h1>
                <p style="margin:8px 0 0; font-size:14px; color:#334155;">
                  You’re just one step away from joining your Estate on Vaultify. Please use the one-time passcode (OTP) below to complete verification.
                </p>
              </td>
            </tr>

            <!-- OTP Box -->
            <tr>
              <td style="padding: 20px 28px 0 28px;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px;">
                  <tr>
                    <td align="center" style="padding:20px 16px;">
                      <div style="font-size:12px; color:#64748b; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:8px;">
                        Your OTP
                      </div>
                      <div style="font-weight:700; font-size:28px; letter-spacing:0.32em; color:#0f172a;">
                        {otp_code}
                      </div>
                      <div style="font-size:12px; color:#64748b; margin-top:8px;">
                        Expires in {OTP_LIFETIME_MINUTES} minutes
                      </div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Why verify -->
            <tr>
              <td style="padding: 20px 28px 0 28px;">
                <h3 style="margin:0 0 8px; font-size:16px; color:#0f172a;">Why verify?</h3>
                <ul style="margin:0 0 0 18px; padding:0; color:#334155; font-size:14px; line-height:20px;">
                  <li><strong>Account Protection</strong>: Verifying your email helps secure your profile and prevent unauthorized access.</li>
                  <li><strong>Stay Informed</strong>: Receive announcements, updates, and alerts from your estate without missing a thing.</li>
                </ul>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding: 24px 28px 28px 28px;">
                <p style="margin:0; font-size:14px; color:#334155;">
                  Warm regards,<br/>
                  <strong>The Vaultify Team</strong>
                </p>
                <p style="margin:12px 0 0; font-size:12px; color:#94a3b8;">
                  If you didn’t request this, you can safely ignore this email.
                </p>
              </td>
            </tr>

          </table>
          <div style="margin-top:16px; font-size:11px; color:#94a3b8;">
            © {now().year} Vaultify. All rights reserved.
          </div>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,  # plain text fallback
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[email],
        )
        msg.attach_alternative(html_body, "text/html")

        # Attach CID image if a local path is configured
        if use_cid and logo_path:
            try:
                with open(logo_path, "rb") as f:
                    img = MIMEImage(f.read())
                    img.add_header("Content-ID", "<vaultify_logo>")
                    img.add_header("Content-Disposition", "inline", filename="vaultify-banner.jpg")
                    msg.attach(img)
            except Exception:
                # If embedding fails, send without image
                pass

        msg.send(fail_silently=False)

class PlainTextParser(BaseParser):
    """
    Plain text parser for 'text/plain' content type.
    """
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read().decode('utf-8')

class PlainTextOrFormParser(FormParser):
    """
    Parser to accept both 'text/plain' and 'application/x-www-form-urlencoded' content types.
    """
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None):
        if media_type == 'application/x-www-form-urlencoded':
            return super().parse(stream, media_type, parser_context)
        return stream.read().decode('utf-8')

PAYSTACK_SECRET_KEY = 'sk_live_43fc893ff9d7a6dd07302e43aae78602c0dc62c8'  # Replace with your Paystack secret key

# Helper function to get the base URL for email links
def get_base_url():
    return getattr(settings, 'BASE_URL', 'https://vaultify-43wm.onrender.com')

logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import random
from datetime import timedelta
from django.utils.timezone import now
from django.core.mail import send_mail
from django.conf import settings
import logging
import uuid

logger = logging.getLogger(__name__)

class SignupSendOTPView(APIView):
    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = user.profile

        # Generate 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"
        profile.signup_otp = otp
        profile.signup_otp_expiry = now() + timedelta(minutes=10)
        profile.save()

        # Send OTP email with personalized text
        try:
            send_mail(
                'Your Vaultify Signup OTP',
                f"""Dear {user.first_name},

                    You’re just one step away from joining your Estate on Vaultify. To complete your sign-in, please verify your email address using the OTP below. Here’s why it’s important:
                    \t•\tAccount Protection: Verifying your email helps secure your profile and prevent unauthorized access.
                    \t•\tStay Informed: Get important announcements, updates, and alerts from your estate without missing a thing.

                    Your OTP is: {otp}

                    This OTP expires in 10 minutes.

                    Warm regards,
                    The Vaultify Team.
                    """,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Signup OTP sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send signup OTP: {e}")
            return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'message': 'OTP sent successfully'}, status=status.HTTP_200_OK)
from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import (
    AccessCodeCreateSerializer,AccessCodeSerializers
    AccessCodeRowSerializer,   # if you use the slim list view
)

# CREATE (fast, compact response)
class AccessCodeCreateSlimView(generics.CreateAPIView):
    serializer_class = AccessCodeSerializers
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        data = resp.data
        # return only what the UI needs to proceed
        return Response(
            {'code': data.get('code'), 'status': 'created'},
            status=status.HTTP_201_CREATED
        )

# LIST (select_related to avoid N+1)
class AccessCodeListSlimView(generics.ListAPIView):
    serializer_class = AccessCodeSerializers
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (AccessCode.objects
                .select_related('creator', 'creator__profile')
                .filter(creator=self.request.user)
                .order_by('-created_at'))

from django.db.models import Q
from .serializers import (
    AlertCreateSerializer,
    AlertRowSerializer,   # if you use the slim list view below
)

class AlertCreateSlimView(generics.CreateAPIView):
    serializer_class = AlertCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        estate = getattr(self.request.user.profile, 'estate', None)
        # we don't store estate on model; just attach sender and save
        serializer.save(sender=self.request.user)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        return Response({'id': resp.data.get('id'), 'status': 'created'}, status=status.HTTP_201_CREATED)

class AlertListSlimView(generics.ListAPIView):
    serializer_class = AlertRowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        try:
            user_role = user.profile.role
            estate = user.profile.estate
        except Exception:
            return Alert.objects.none()

        # deleted alerts
        deleted_ids = set(user.deleted_alerts.values_list('alert_id', flat=True))

        qs = (Alert.objects
              .select_related('sender', 'sender__profile')
              .filter(
                  Q(recipients__contains=[user_role]) | Q(recipients__contains=[str(user.id)])
              )
              .order_by('-timestamp'))

        if deleted_ids:
            qs = qs.exclude(id__in=deleted_ids)
        return qs

# CREATE — compact response (no heavy nested serialization)
from .serializers import (
    LostFoundItemRowSerializer   # if you use the slim list view
)

# views.py
import boto3, datetime
from django.conf import settings
from rest_framework.views import APIView

class LostFoundPresignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        filename = request.data.get('filename') or 'upload.jpg'
        content_type = request.data.get('content_type') or 'image/jpeg'
        s3 = boto3.client(
            's3',
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=getattr(settings, 'AWS_S3_CONFIG', None),
        )
        key = f"lostfound_images/{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"
        presigned = s3.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            Fields={"Content-Type": content_type, "acl": "public-read"},
            Conditions=[
                {"Content-Type": content_type},
                {"acl": "public-read"},
                ["content-length-range", 0, 15 * 1024 * 1024],  # 15MB
            ],
            ExpiresIn=600,
        )
        # Client: upload to presigned['url'] with presigned['fields']
        return Response({"upload": presigned, "key": key}, status=200)


# LIST — prefetch sender/profile; search/order as before
class LostFoundItemListSlimView(generics.ListAPIView):
    serializer_class = LostFoundItemRowSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'location', 'contact_info']
    ordering = ['-date_reported']

    def get_queryset(self):
        estate = (self.request.query_params.get('estate')
                  or getattr(self.request.user.profile, 'estate', None))
        if not estate:
            return LostFoundItem.objects.none()
        qs = (LostFoundItem.objects
              .select_related('sender', 'sender__profile')
              .filter(sender__profile__estate__iexact=estate))
        item_type = self.request.query_params.get('item_type')
        if item_type in dict(LostFoundItem.ITEM_TYPES):
            qs = qs.filter(item_type=item_type)
        return qs

class SignupVerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        otp = request.data.get('otp', '').strip()

        if not email or not otp:
            return Response({'error': 'Email and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = user.profile

        if profile.signup_otp != otp:
            return Response({'status': 'failure', 'message': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

        if profile.signup_otp_expiry < now():
            return Response({'status': 'failure', 'message': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark email as verified and clear OTP fields
        profile.is_email_verified = True
        profile.signup_otp = None
        profile.signup_otp_expiry = None
        profile.save()

        logger.info(f"Email verified for user {user.email} via OTP")
        return Response({'status': 'success', 'message': 'Email verified successfully'}, status=status.HTTP_200_OK)
class CheckEmailVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.profile.is_email_verified:
            return Response({'is_email_verified': True}, status=status.HTTP_200_OK)
        else:
            return Response({'is_email_verified': False}, status=status.HTTP_200_OK)

class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email').lower()  # Normalize to lowercase
        password = request.data.get('password')
        print(email)
        user = authenticate(username=email, password=password)
        print(user)
        if user:
            if not user.profile.is_email_verified:
                logger.warning(f"Login failed: Email not verified for {email}")
                return Response({'error': 'Email not verified'}, status=status.HTTP_403_FORBIDDEN)
            token, _ = AuthToken.objects.get_or_create(user=user)
            logger.info(f"User {email} logged in successfully, Role: {user.profile.role}")
            return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_200_OK)
        logger.warning(f"Login failed: Invalid credentials for {email}")
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
from rest_framework.permissions import AllowAny

class UserUpdateView(APIView):
    authentication_classes = []          # bypass any global authenticators (e.g. JWT/Session)
    permission_classes = [AllowAny]      # anyone can call it

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    from datetime import timedelta
    from django.utils.timezone import now
    import random
    def put(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        old_email = user.email
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            new_email = serializer.instance.email

            logger.info(f"User {old_email} updated to {new_email}, Role: {user.profile.role}, Profile Picture: {user.profile.profile_picture}")

            if old_email != new_email:
                user.username = new_email
                user.save(update_fields=['username'])  # ✅ Save the new username

                otp_code = f"{random.randint(100000, 999999)}"
                user.profile.signup_otp = otp_code
                user.profile.signup_otp_expiry = now() + timedelta(minutes=10)
                user.profile.is_email_verified = False
                user.profile.save(update_fields=['signup_otp', 'signup_otp_expiry', 'is_email_verified'])

                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    'Verify Your New Email - OTP',
                    f'Your OTP to verify your new email is: {otp_code}. It expires in 10 minutes.',
                    settings.DEFAULT_FROM_EMAIL,
                    [new_email],
                    fail_silently=False,
                )
                logger.info(f"Verification OTP email sent to {new_email} after email change")

            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.error(f"User update errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AccessCodeCreateView(generics.CreateAPIView):
    serializer_class = AccessCodeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            serializer.save(creator=self.request.user)
        except IntegrityError as e:
            # The perform_create method should not return Response objects.
            # Instead, raise the exception to be handled by the framework.
            raise e

@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    def post(self, request, *args, **kwargs):
        paystack_secret = 'sk_live_43fc893ff9d7a6dd07302e43aae78602c0dc62c8'  # Use your secret key
        signature = request.headers.get('x-paystack-signature')
        payload = request.body

        if not signature:
            return JsonResponse({'error': 'Signature missing'}, status=400)

        computed_signature = hmac.new(
            paystack_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, signature):
            return JsonResponse({'error': 'Invalid signature'}, status=400)

        event = json.loads(payload)

        if event.get('event') == 'charge.success':
            data = event.get('data', {})
            reference = data.get('reference')
            amount = data.get('amount')  # amount in kobo
            customer_email = data.get('customer', {}).get('email')

            try:
                user = User.objects.get(email=customer_email)
                profile = user.profile
                amount_naira = Decimal(amount) / Decimal('100.0')
                profile.wallet_balance += amount_naira
                profile.save()
                logger.info(f"Wallet updated for {customer_email}: +{amount_naira}")
                return JsonResponse({'status': 'success'}, status=200)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=404)

        return JsonResponse({'status': 'ignored'}, status=200)

from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from urllib.parse import urlencode

class VerifyEmailView(APIView):
    def get(self, request, token):
        redirect_url = getattr(settings, 'EMAIL_VERIFICATION_REDIRECT_URL', None)
        try:
            profile = UserProfile.objects.get(email_verification_token=token)
            profile.is_email_verified = True
            profile.email_verification_token = ''
            profile.save()
            logger.info(f"Email verified for user {profile.user.email}")
            if redirect_url:
                params = urlencode({'status': 'success'})
                return redirect(f"{redirect_url}?{params}")
            else:
                return Response({
                    'status': 'success',
                    'message': 'Your email has been verified successfully. You can now log in.'
                }, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            if redirect_url:
                params = urlencode({'status': 'failure'})
                return redirect(f"{redirect_url}?{params}")
            else:
                return Response({
                    'status': 'failure, you might have received another email please verify with that', 
                    'message': 'Invalid token. Please request a new verification email.'
                }, status=status.HTTP_400_BAD_REQUEST)

class ResendVerificationEmailView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            if user.profile.is_email_verified:
                return Response({'error': 'Email already verified'}, status=status.HTTP_400_BAD_REQUEST)
            verification_token = str(uuid.uuid4())
            user.profile.email_verification_token = verification_token
            user.profile.save()
            send_mail(
                'Verify Your Email',
                f'Click the link to verify your email: {get_base_url()}/api/verify-email/{verification_token}/',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Verification email resent to {email}")
            return Response({'message': 'Verification email resent'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class GoogleSignInView(APIView):
    def post(self, request):
        token = request.data.get('id_token')
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)
            email = idinfo['email']
            name = idinfo.get('name', '')
            first_name = name.split(' ')[0] if name else ''
            last_name = ' '.join(name.split(' ')[1:]) if len(name.split(' ')) > 1 else ''
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            if created:
                user.set_password(str(uuid.uuid4()))
                user.save()
                UserProfile.objects.create(user=user, is_email_verified=True)
            if not user.profile.is_email_verified:
                return Response({'error': 'Email not verified'}, status=status.HTTP_403_FORBIDDEN)
            token, _ = AuthToken.objects.get_or_create(user=user)
            logger.info(f"Google sign-in successful for {email}, Role: {user.profile.role}")
            return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_400_BAD_REQUEST)

import random
from datetime import datetime, timedelta
from django.utils.timezone import now

class PasswordResetRequestView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            users = User.objects.filter(email=email)
            if not users.exists():
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            for user in users:
                profile = user.profile
                # Generate 6-digit OTP
                otp = f"{random.randint(100000, 999999)}"
                profile.password_reset_otp = otp
                profile.password_reset_otp_expiry = now() + timedelta(minutes=10)
                profile.save()

                # Send OTP email
                send_mail(
                    'Password Reset OTP',
                    f'Your password reset OTP is: {otp}. It expires in 10 minutes.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                logger.info(f"Password reset OTP sent to {email} for user {user.id}")
            return Response({'message': 'Password reset OTP sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in PasswordResetRequestView: {str(e)}")
            return Response({'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordResetVerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp, new_password]):
            return Response({'error': 'Email, OTP, and new password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            users = User.objects.filter(email=email)
            if not users.exists():
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            if users.count() > 1:
                logger.warning(f"Multiple users found with email {email}. Using the first user for OTP verification.")
            user = users.first()
            profile = user.profile
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if profile.password_reset_otp != otp:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

        if profile.password_reset_otp_expiry < now():
            return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Clear OTP fields
        profile.password_reset_otp = None
        profile.password_reset_otp_expiry = None
        profile.save()

        logger.info(f"Password reset successful for {user.email} via OTP")
        return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)




class DeleteAccountView(APIView):
    authentication_classes = []                 # no JWT/Session auth
    permission_classes = [AllowAny]             # allow anonymous
    parser_classes = [MultiPartParser, FormParser]  # handle file uploads

    def delete(self, request, pk):
        # if request.user.pk != pk:
        #     return Response({'error': 'You can only delete your own account'}, status=status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
            user.delete()
            logger.info(f"Account deleted for {user.email}")
            return Response({'message': 'Account deleted successfully'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# views.py
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

@method_decorator(csrf_exempt, name='dispatch')  # bypass CSRF if SessionAuth is ever applied
class OpenDeleteAccountView(APIView):
    authentication_classes = []     # ignore global authenticators
    permission_classes = [AllowAny] # allow anonymous

    # extra hard override in case a project-level mixin tries to inject perms
    def get_authenticators(self):    # return none → no auth attempted
        return []
    def get_permissions(self):       # force AllowAny at runtime
        return [AllowAny()]

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # optional convenience
    def post(self, request, pk):
        return self.delete(request, pk)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            if request.auth:
                token = AuthToken.objects.get(key=request.auth)
                token.delete()
                logger.info(f"User {request.user.email} logged out successfully")
                return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
            return Response({'error': 'No active session found'}, status=status.HTTP_400_BAD_REQUEST)
        except AuthToken.DoesNotExist:
            return Response({'error': 'Failed to logout: Token not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({'error': 'Failed to logout'}, status=status.HTTP_400_BAD_REQUEST)

class LoginWithIdView(APIView):
    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            if not user.profile.is_email_verified:
                return Response({'error': 'Email not verified'}, status=status.HTTP_403_FORBIDDEN)
            token, _ = AuthToken.objects.get_or_create(user=user)
            logger.info(f"Login with ID successful for {user.email}, Role: {user.profile.role}")
            return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
        
from datetime import timedelta, time

class AccessCodeCreateView(generics.CreateAPIView):
    serializer_class = AccessCodeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            instance = serializer.save(creator=self.request.user)
            logger.info(f"Access code created: {instance.code} by user {self.request.user.email}")
        except Exception as e:
            logger.error(f"Error creating access code: {e}")
            raise e

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AccessCode, UserDeletedAlert, Alert
from .serializers import AccessCodeSerializer, AlertSerializer
from django.utils import timezone
import logging
import pytz
from rest_framework.permissions import IsAuthenticated

WAT = pytz.timezone('Africa/Lagos')
logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class AlertCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        alerts_count = Alert.objects.filter(sender__profile__estate=estate).count()
        return Response({'estate': estate, 'alerts_count': alerts_count}, status=status.HTTP_200_OK)

class LostFoundCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        lostfound_count = LostFoundItem.objects.filter(sender__profile__estate=estate).count()
        return Response({'estate': estate, 'lostfound_count': lostfound_count}, status=status.HTTP_200_OK)

class AccessCodeVerifiedCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        verified_count = AccessCode.objects.filter(creator__profile__estate=estate, current_uses__gt=0).count()
        return Response({'estate': estate, 'verified_count': verified_count}, status=status.HTTP_200_OK)

class AccessCodeUnapprovedCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        unapproved_count = AccessCode.objects.filter(creator__profile__estate=estate, current_uses=0).count()
        return Response({'estate': estate, 'unapproved_count': unapproved_count}, status=status.HTTP_200_OK)

class ResidenceUsersCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        count = User.objects.filter(profile__role='Residence', profile__is_email_verified=True, profile__estate=estate).count()
        return Response({'estate': estate, 'count': count}, status=status.HTTP_200_OK)

class SecurityPersonnelUsersCountByEstateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        count = User.objects.filter(profile__role='Security Personnel', profile__is_email_verified=True, profile__estate=estate).count()
        return Response({'estate': estate, 'count': count}, status=status.HTTP_200_OK)

class LostFoundAndAlertCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Deprecated combined counts endpoint
        return Response({'detail': 'Use separate endpoints for alerts and lostfound counts'}, status=status.HTTP_400_BAD_REQUEST)

class AlertCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        deleted_alert_ids = user.deleted_alerts.values_list('alert_id', flat=True)
        user_role = None
        try:
            user_role = user.profile.role
        except Exception as e:
            # Log error if user profile or role is missing
            logger.error(f"Error getting user role for alert count: {e}")
        if not user_role:
            return Response({'alerts_count': 0}, status=status.HTTP_200_OK)
        alerts_count = Alert.objects.filter(
            recipients__contains=[user_role]
        ).exclude(
            id__in=deleted_alert_ids
        ).count()
        logger.debug(f"User {user.username} with role {user_role} has {alerts_count} alerts")
        return Response({'alerts_count': alerts_count}, status=status.HTTP_200_OK)

class LostFoundCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lostfound_count = LostFoundItem.objects.count()
        logger.debug(f"Total lost and found items count: {lostfound_count}")
        return Response({'lostfound_count': lostfound_count}, status=status.HTTP_200_OK)

class AlertDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        user = request.user
        try:
            alert = Alert.objects.get(id=alert_id)
        except Alert.DoesNotExist:
            return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already deleted
        deleted, created = UserDeletedAlert.objects.get_or_create(user=user, alert=alert)
        if created:
            logger.info(f"User {user.username} deleted alert {alert_id}")
        else:
            logger.info(f"User {user.username} had already deleted alert {alert_id}")

        return Response({'message': 'Alert deleted successfully'}, status=status.HTTP_200_OK)

    def delete(self, request, alert_id):
        user = request.user
        try:
            alert = Alert.objects.get(id=alert_id)
        except Alert.DoesNotExist:
            return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already deleted
        deleted, created = UserDeletedAlert.objects.get_or_create(user=user, alert=alert)
        if created:
            logger.info(f"User {user.username} deleted alert {alert_id} via DELETE")
        else:
            logger.info(f"User {user.username} had already deleted alert {alert_id} via DELETE")

        return Response({'message': 'Alert deleted successfully'}, status=status.HTTP_200_OK)

class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['alert_type', 'urgency_level', 'recipients']

    def get_queryset(self):
        user = self.request.user
        try:
            user_role = user.profile.role
        except Exception:
            user_role = None
        if not user_role:
            return Alert.objects.none()

        # Define opposite role mapping for cross-role alert fetching
        opposite_role_map = {
            'Residence': 'Security Personnel',
            'Security Personnel': 'Residence',
        }

        opposite_role = opposite_role_map.get(user_role)

        # Get alerts deleted by the user
        deleted_alert_ids = user.deleted_alerts.values_list('alert_id', flat=True)

        # Filter alerts where recipients contain user_role and sender's role is opposite_role
        # or alerts sent by the user themselves (optional)
        return Alert.objects.filter(
            recipients__contains=[user_role]
        ).filter(
            Q(sender__profile__role=opposite_role) | Q(sender=user)
        ).exclude(
            id__in=deleted_alert_ids
        ).order_by('-timestamp')
        
        
from accounts.timefmt import to_local_iso

class AccessCodeVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')
        user = request.user
        auth_header = request.headers.get('Authorization', 'No Authorization header')
        logger.debug(f"AccessCodeVerifyView called by user: {user.email}, Authorization: {auth_header}, code: {code}")

        if not code:
            logger.error("No code provided in verification request")
            return Response({"error": "Access code is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            access_code = AccessCode.objects.get(code=code)
        except AccessCode.DoesNotExist:
            logger.warning(f"Access code not found: {code}")
            return Response({"error": "Invalid access code"}, status=status.HTTP_404_NOT_FOUND)

        # Estate-based restriction check
        user_estate = getattr(request.user.profile, 'estate', None)
        access_code_estate = getattr(access_code.creator.profile, 'estate', None)
        if user_estate != access_code_estate:
            logger.warning(f"User {request.user.email} from estate {user_estate} attempted to verify access code from estate {access_code_estate}")
            return Response({"error": "You are not authorized to verify access codes from this estate."}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        if now < access_code.valid_from:
            logger.warning(f"Access code not yet valid: {code}, Now: {now}, Valid from: {to_local_iso(access_code.valid_from)}")
            return Response(
                {"error": f"Access code is not yet valid: {access_code.valid_from}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if now > access_code.valid_to:
            logger.warning(f"Access code expired: {code}, Now: {now}, Valid to: {to_local_iso(access_code.valid_to)}")
            return Response(
                {"error": f"Access code has expired: {to_local_iso(access_code.valid_to)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not access_code.is_active:
            logger.warning(f"Access code is inactive: {code}")
            return Response({"error": "Access code is disabled"}, status=status.HTTP_400_BAD_REQUEST)
        if access_code.current_uses >= access_code.max_uses:
            logger.warning(f"Access code max uses reached: {code}")
            return Response({"error": "Access code has reached its maximum usage limit"}, status=status.HTTP_400_BAD_REQUEST)

        # Update current_uses and deactivate if max_uses reached
        access_code.current_uses += 1
        if access_code.current_uses >= access_code.max_uses:
            access_code.is_active = False
        access_code.save()

        # Optionally send notification if notify_on_use is True
        if access_code.notify_on_use:
            # Implement notification logic (e.g., email or push notification)
            pass

        return Response({
            'visitorName': access_code.visitor_name,
            'visitorEmail': access_code.visitor_email,
            'visitorPhone': access_code.visitor_phone,
            'hostName': access_code.creator.get_full_name() or access_code.creator.email,
            'status': 'valid',
            'accessArea': access_code.gate,
            'code': access_code.code,
            'validFrom': to_local_iso(access_code.valid_from),
            'validTo': to_local_iso(access_code.valid_to),
            'verified_count': access_code.current_uses,
            'unapproved_count': 0 if access_code.current_uses > 0 else 1,
        }, status=status.HTTP_200_OK)

    def get(self, request, code):
        try:
            access_code = AccessCode.objects.get(code=code)
        except AccessCode.DoesNotExist:
            logger.warning(f"Access code not found: {code}")
            return Response({"error": "Invalid access code"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AccessCodeSerializer(access_code)
        response_data = {
            "code": access_code.code,
            "visitorName": access_code.visitor_name,
            "visitorEmail": access_code.visitor_email,
            "visitorPhone": access_code.visitor_phone,
            "hostName": access_code.creator.get_full_name() or access_code.creator.email,
            "status": "Verified" if access_code.current_uses > 0 else "Pending",
            "accessArea": access_code.gate,
            "validFrom": access_code.valid_from.isoformat(),
            "validTo": access_code.valid_to.isoformat(),
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
class AccessCodeVerifiedCountView(APIView):
    def get(self, request):
        verified_count = AccessCode.objects.filter(current_uses__gt=0).count()
        return Response({"verified_count": verified_count}, status=status.HTTP_200_OK)

class AccessCodeUnapprovedCountView(APIView):
    def get(self, request):
        unapproved_count = AccessCode.objects.filter(current_uses=0).count()
        return Response({"unapproved_count": unapproved_count}, status=status.HTTP_200_OK)
    
class AlertCreateView(generics.CreateAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user_estate = getattr(self.request.user.profile, 'estate', None)
        serializer.save(sender=self.request.user, estate=user_estate)

class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['alert_type', 'urgency_level', 'recipients']

    def get_queryset(self):
        from django.db.models import Q

        user = self.request.user
        user_id_str = str(user.id)
        estate = self.request.query_params.get('estate')
        if not estate:
            try:
                estate = getattr(user.profile, 'estate', None)
                user_role = user.profile.role
            except Exception:
                user_role = None
                estate = None
        else:
            try:
                user_role = user.profile.role
            except Exception:
                user_role = None

        if not user_id_str or not user_role or not estate:
            return Alert.objects.none()

        deleted_alert_ids = user.deleted_alerts.values_list('alert_id', flat=True)

        if user_role.lower() == 'security personnel':
            # Return all alerts in the specified estate except those deleted by the user
            return Alert.objects.filter(
                sender__profile__estate=estate
            ).exclude(
                id__in=deleted_alert_ids
            ).order_by('-timestamp')

        # For other roles, filter alerts where recipients contain user ID or user role and estate matches
        return Alert.objects.filter(
            (Q(recipients__contains=[user_id_str]) | Q(recipients__contains=[user_role])) &
            Q(sender__profile__estate=estate)
        ).exclude(
            id__in=deleted_alert_ids
        ).order_by('-timestamp')


class GeneralAlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['alert_type', 'urgency_level', 'recipients']

    def get_queryset(self):
        user = self.request.user
        deleted_alert_ids = user.deleted_alerts.values_list('alert_id', flat=True)
        return Alert.objects.exclude(
            id__in=deleted_alert_ids
        ).order_by('-timestamp')

from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import LostFoundItem
from .serializers import LostFoundItemSerializer

# views.py (replace only the create() in LostFoundItemCreateView)

import os, uuid, requests
from botocore.client import Config as BotoConfig
import boto3
from django.conf import settings

def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=BotoConfig(signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4")),
    )

def _extract_key(v: str) -> str:
    from urllib.parse import urlparse
    v = (v or "").strip()
    if not v:
        return ""
    if v.startswith(("http://", "https://")):
        p = urlparse(v); path = (p.path or "").lstrip("/")
        return path.split("/", 1)[1] if "/" in path else path
    return v

# views.py
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.db import transaction

from .models import LostFoundItem
from .serializers import (
    LostFoundItemCreateSerializer,
    LostFoundItemRowSerializer,
)

class LostFoundItemCreateView(generics.CreateAPIView):
    queryset = LostFoundItem.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = LostFoundItemCreateSerializer   # ← REQUIRED

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if "image_key" in request.FILES:
            return Response({"error": "Send 'image_key' as TEXT (not file)."}, status=400)

        saved_key = ""
        file_obj = request.FILES.get("image")
        if file_obj:
            ext = os.path.splitext(file_obj.name)[1] or ".jpg"
            key = f"lostfound_images/{uuid.uuid4().hex}{ext}"
            content_type = getattr(file_obj, "content_type", "application/octet-stream")

            s3 = _s3_client()
            put_url = s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                    "ACL": "public-read",
                },
                ExpiresIn=600,
            )

            # upload WITHOUT botocore (prevents ConnectionClosedError)
            r = requests.put(
                put_url,
                data=file_obj.file,  # stream
                headers={"Content-Type": content_type, "x-amz-acl": "public-read"},
                timeout=60,
            )
            if r.status_code not in (200, 201, 204):
                return Response(
                    {"error": "S3 upload failed", "status": r.status_code, "detail": r.text[:500]},
                    status=502,
                )
            saved_key = key
            data.pop("image", None)  # don't let DRF try to upload again

        if not saved_key:
            saved_key = _extract_key(data.get("image_key", "")) if isinstance(data.get("image_key", ""), str) else ""
        data.pop("image_key", None)

        ser = self.get_serializer(data=data)
        ser.is_valid(raise_exception=True)
        item = ser.save(sender=request.user)

        if saved_key and not item.image:
            item.image.name = saved_key
            item.save(update_fields=["image"])

        out = LostFoundItemRowSerializer(item, context=self.get_serializer_context()).data
        return Response(out, status=status.HTTP_201_CREATED)

class LostFoundItemListView(generics.ListAPIView):
    serializer_class = LostFoundItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'location', 'contact_info']  # leave text to SearchFilter
    ordering = ['-date_reported']

    def get_queryset(self):
        # Prefer explicit ?estate=..., else use the caller’s estate
        estate = self.request.query_params.get('estate') or getattr(self.request.user.profile, 'estate', None)
        if not estate:
            return LostFoundItem.objects.none()

        qs = (LostFoundItem.objects
              .select_related('sender', 'sender__profile')
              .filter(sender__profile__estate__iexact=estate))

        item_type = self.request.query_params.get('item_type')  # "Lost" or "Found"
        if item_type in dict(LostFoundItem.ITEM_TYPES):
            qs = qs.filter(item_type=item_type)

        return qs

class LostFoundItemListAllView(generics.ListAPIView):
    queryset = LostFoundItem.objects.select_related('sender', 'sender__profile').order_by('-date_reported')
    serializer_class = LostFoundItemSerializer
    permission_classes = [IsAuthenticated]


from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from .serializers import UserSerializer

class LostFoundItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LostFoundItem.objects.all()
    serializer_class = LostFoundItemSerializer
    permission_classes = [IsAuthenticated]
    
class VisitorCheckinListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        estate = self.request.query_params.get('estate')
        if not estate:
            return AccessCode.objects.none()
        return AccessCode.objects.filter(current_uses__gt=0, creator__profile__estate=estate).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        estate = request.query_params.get('estate')
        if not estate:
            return Response({'error': 'Estate parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset()
        serializer = AccessCodeSerializer(queryset, many=True)
        response_data = {
            'count': queryset.count(),
            'visitors': [
                {
                    'visitorName': item['visitor_name'],
                    'accessCode': item['code'],
                    'hostName': item['creator_name'],
                    'checkInTime': item['created_at'],
                    'expectedCheckOutTime': item['valid_to'],
                    'accessArea': item['gate'],
                    'estate': item.get('creator_profile', {}).get('estate', '')  # Add estate field here
                } for item in serializer.data
            ]
        }
        return Response(response_data)
    
    

# New GeneralVisitorCheckinListView without estate filtering
class GeneralVisitorCheckinListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AccessCode.objects.filter(current_uses__gt=0).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = AccessCodeSerializer(queryset, many=True)
        response_data = {
            'count': queryset.count(),
            'visitors': [
                {
                    'visitorName': item['visitor_name'],
                    'accessCode': item['code'],
                    'hostName': item['creator_name'],
                    'checkInTime': item['created_at'],
                    'expectedCheckOutTime': item['valid_to'],
                    'accessArea': item['gate'],
                    'estate': item.get('creator_profile', {}).get('estate', '')  # Add estate field here
                } for item in serializer.data
            ]
        }
        return Response(response_data)

    


class ResidenceUsersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        estate = self.request.query_params.get('estate')
        if not estate:
            user = self.request.user
            estate = getattr(user.profile, 'estate', None)
        if not estate:
            return User.objects.none()
        return User.objects.filter(
            profile__role='Residence',
            profile__is_email_verified=True,
            profile__estate=estate
        )


class ResidenceUsersListAllView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(profile__role='Residence', profile__is_email_verified=True)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import PrivateMessage
from .serializers import PrivateMessageSerializer
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.contrib.auth.models import User
from .models import PrivateMessage
from .serializers import PrivateMessageSerializer

class PrivateMessageListView(generics.ListCreateAPIView):
    serializer_class = PrivateMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        other_user_id = self.request.query_params.get('user_id')
        if not other_user_id:
            return PrivateMessage.objects.none()
        # Get estates of both users
        try:
            user_estate = user.profile.estate
            other_user = User.objects.get(id=other_user_id)
            other_user_estate = other_user.profile.estate
        except Exception:
            return PrivateMessage.objects.none()
        # Only allow messages if both users belong to the same estate
        if user_estate != other_user_estate:
            return PrivateMessage.objects.none()
        return PrivateMessage.objects.filter(
            Q(sender=user, receiver_id=other_user_id) | Q(sender_id=other_user_id, receiver=user)
        ).order_by('timestamp')

    def perform_create(self, serializer):
        receiver = serializer.validated_data.get('receiver')
        if receiver is None:
            raise serializers.ValidationError({"receiver": "This field is required."})
        # Check estate match
        try:
            sender_estate = self.request.user.profile.estate
            receiver_estate = receiver.profile.estate
        except Exception:
            raise serializers.ValidationError({"receiver": "Invalid receiver or estate mismatch."})
        if sender_estate != receiver_estate:
            raise serializers.ValidationError({"receiver": "Receiver must belong to the same estate."})
        serializer.save(sender=self.request.user, receiver=receiver)

class PrivateMessageCreateView(generics.CreateAPIView):
    serializer_class = PrivateMessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        receiver = serializer.validated_data.get('receiver')
        if receiver is None:
            raise serializers.ValidationError({"receiver": "This field is required."})
        # Check estate match
        try:
            sender_estate = self.request.user.profile.estate
            receiver_estate = receiver.profile.estate
        except Exception:
            raise serializers.ValidationError({"receiver": "Invalid receiver or estate mismatch."})
        if sender_estate != receiver_estate:
            raise serializers.ValidationError({"receiver": "Receiver must belong to the same estate."})
        serializer.save(sender=self.request.user, receiver=receiver)

class SecurityPersonnelUsersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        estate = self.request.query_params.get('estate')
        if not estate:
            user = self.request.user
            estate = getattr(user.profile, 'estate', None)
        if not estate:
            return User.objects.none()
        return User.objects.filter(
            profile__role='Security Personnel',  # Verify this role value
            profile__is_email_verified=True,
            profile__estate=estate
        )


class SecurityPersonnelUsersListAllView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(profile__role='Security Personnel', profile__is_email_verified=True)

class ResidenceUsersCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = User.objects.filter(profile__role='Residence', profile__is_email_verified=True).count()
        return Response({'count': count})

class SecurityPersonnelUsersCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = User.objects.filter(profile__role='Security Personnel', profile__is_email_verified=True).count()
        return Response({'count': count})
class AccessCodeByUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve a list of access codes created by the authenticated user.
        Automatically deactivate expired access codes.
        """
        try:
            now = timezone.now()
            # Filter access codes by the authenticated user and order by creation date
            access_codes = AccessCode.objects.filter(creator=request.user).order_by('-created_at')

            # Deactivate expired access codes
            expired_codes = access_codes.filter(valid_to__lt=now, is_active=True)
            expired_codes.update(is_active=False)

            # Refresh the queryset after update
            access_codes = AccessCode.objects.filter(creator=request.user).order_by('-created_at')

            # Prepare response with the authenticated user's details
            user = request.user
            result = {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}".strip()
                },
                'access_codes': AccessCodeSerializer(access_codes, many=True).data
            }
            
            logger.info(f"Retrieved {len(result['access_codes'])} access codes for user {user.email}")
            return Response([result], status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error retrieving access codes for user {request.user.email}: {str(e)}")
            return Response({'error': 'Failed to retrieve access codes'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
          
class AccessCodeDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, code):
        """
        Deactivate an access code by setting is_active to False.
        Only the creator can deactivate their own access code.
        """
        try:
            access_code = AccessCode.objects.get(code=code)
            if access_code.creator != request.user:
                logger.warning(f"User {request.user.email} attempted to deactivate code {code} not owned by them")
                return Response({"error": "You can only deactivate your own access codes"}, status=status.HTTP_403_FORBIDDEN)
            
            access_code.is_active = False
            access_code.save()
            logger.info(f"Access code {code} deactivated by {request.user.email}")
            return Response(AccessCodeSerializer(access_code).data, status=status.HTTP_200_OK)
        
        except AccessCode.DoesNotExist:
            logger.warning(f"Access code not found: {code}")
            return Response({"error": "Access code not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deactivating access code {code}: {str(e)}")
            return Response({"error": "Failed to deactivate access code"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# @method_decorator(csrf_exempt, name='dispatch')


# class VerifyAndCreditView(APIView):
#     def post(self, request):
#         try:
#             reference = request.data.get('reference')
#             user_id = request.data.get('user_id')
#             plan = request.data.get('plan')  
#             if not reference:
#                 return Response(
#                     {'error': 'Transaction reference is required'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#             if not user_id:
#                 return Response(
#                     {'error': 'User ID is required'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#             if not plan:
#                 return Response(
#                     {'error': 'Plan type is required'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             secret_key = 'sk_live_43fc893ff9d7a6dd07302e43aae78602c0dc62c8'
#             headers = {'Authorization': f'Bearer {secret_key}'}
#             paystack_url = f'https://api.paystack.co/transaction/verify/{reference}'
#             response = requests.get(paystack_url, headers=headers)
#             response_data = response.json()
#             print(f'Paystack response: status={response.status_code}, body={response_data}')

#             if response.status_code == 200 and response_data['status']:
#                 transaction_status = response_data['data'].get('status')
#                 if transaction_status == 'success':
#                     amount = Decimal(response_data['data']['amount']) / Decimal('100')
#                     from django.contrib.auth.models import User
#                     from django.utils import timezone
#                     try:
#                         user = User.objects.get(id=user_id)
#                     except User.DoesNotExist:
#                         return Response(
#                             {'error': f'User with id {user_id} not found'},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     # Idempotency check: prevent double crediting
#                     if not hasattr(user.profile, 'last_transaction_reference') or user.profile.last_transaction_reference != reference:
#                         user.profile.wallet_balance += amount
#                         user.profile.last_transaction_reference = reference
#                         # Set subscription start and expiry dates based on plan
#                         now = timezone.now()
#                         user.profile.plan = plan
#                         user.profile.subscription_start_date = now
#                         if plan.lower() == 'monthly':
#                             user.profile.subscription_expiry_date = now + timezone.timedelta(days=30)
#                         elif plan.lower() == 'annual':
#                             user.profile.subscription_expiry_date = now + timezone.timedelta(days=365)
#                         else:
#                             # For free or unknown plans, set expiry 30 days from now
#                             user.profile.subscription_expiry_date = now + timezone.timedelta(days=30)
#                         user.profile.save(update_fields=['wallet_balance', 'last_transaction_reference', 'plan', 'subscription_start_date', 'subscription_expiry_date'])
#                         print(f'Updated wallet balance and subscription for user {user_id}: {user.profile.wallet_balance}, plan: {plan}')
#                     else:
#                         print(f'Transaction {reference} already processed for user {user_id}')

#                     return Response(
#                         {'message': 'Wallet credited and subscription updated successfully', 'balance': float(user.profile.wallet_balance)},
#                         status=status.HTTP_200_OK
#                     )
#                 elif transaction_status == 'abandoned':
#                     # Log abandoned transaction for monitoring
#                     logger.warning(f'Transaction abandoned: reference={reference}, user_id={user_id}')
#                     return Response(
#                         {'error': 'Transaction was abandoned and not completed. Please try again or contact support.'},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#                 else:
#                     return Response(
#                         {'error': f'Transaction status {transaction_status} not supported'},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#             else:
#                 return Response(
#                     {'error': 'Transaction verification failed. Please check your payment and try again.'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#         except Exception as e:
#             logger.error(f'Error in VerifyAndCreditView: {str(e)}')
#             return Response(
#                 {'error': f'Something went wrong. Please try again later.'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
import logging

logger = logging.getLogger(__name__)


def _subscription_summary_and_autofix(profile):
    """
    Compute start/expiry/is_active/days_remaining.
    If expired and not already 'free', auto-downgrade plan to 'free'.
    """
    now_ts = timezone.now()
    start_dt = getattr(profile, 'subscription_start_date', None)
    expiry_dt = getattr(profile, 'subscription_expiry_date', None)

    is_active = bool(expiry_dt and expiry_dt >= now_ts)
    days_remaining = max(0, (expiry_dt - now_ts).days) if expiry_dt else None

    # Auto-downgrade if expired
    if not is_active:
        plan = (getattr(profile, 'plan', '') or '').strip().lower()
        if plan and plan != 'free':
            profile.plan = 'free'
            try:
                profile.save(update_fields=['plan'])
            except Exception as e:
                logger.warning(f"Failed to auto-downgrade expired plan for user {profile.user_id}: {e}")

    return {
        'type': ((getattr(profile, 'plan', None) or 'free')).lower(),
        'start_date': start_dt.isoformat() if start_dt else None,
        'expiry_date': expiry_dt.isoformat() if expiry_dt else None,
        'is_active': is_active,
        'days_remaining': days_remaining,
    }


class VerifyAndCreditView(APIView):
    def post(self, request):
        try:
            reference = request.data.get('reference')
            user_id   = request.data.get('user_id')
            plan      = (request.data.get('plan') or '').strip()

            if not reference:
                return Response({'error': 'Transaction reference is required'}, status=status.HTTP_400_BAD_REQUEST)
            if not user_id:
                return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            if not plan:
                return Response({'error': 'Plan type is required'}, status=status.HTTP_400_BAD_REQUEST)

            secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
            if not secret_key:
                logger.error("PAYSTACK_SECRET_KEY is not configured")
                return Response({'error': 'Payment configuration error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            headers = {'Authorization': f'Bearer {secret_key}'}
            paystack_url = f'https://api.paystack.co/transaction/verify/{reference}'
            response = requests.get(paystack_url, headers=headers)
            response_data = response.json()
            logger.info(f'Paystack verification: status={response.status_code}, body={response_data}')

            if response.status_code == 200 and response_data.get('status'):
                transaction_status = response_data.get('data', {}).get('status')

                if transaction_status == 'success':
                    amount = Decimal(response_data['data']['amount']) / Decimal('100')

                    from django.contrib.auth.models import User
                    try:
                        user = User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        return Response({'error': f'User with id {user_id} not found'}, status=status.HTTP_400_BAD_REQUEST)

                    # Idempotency: prevent double-crediting
                    already_processed = (user.profile.last_transaction_reference == reference)
                    if not already_processed:
                        user.profile.wallet_balance += amount
                        user.profile.last_transaction_reference = reference

                        # Update subscription dates
                        now_ts = timezone.now()
                        user.profile.plan = plan
                        user.profile.subscription_start_date = now_ts
                        if plan.lower() == 'monthly':
                            user.profile.subscription_expiry_date = now_ts + timezone.timedelta(days=30)
                        elif plan.lower() in ('annual', 'yearly', 'year'):
                            user.profile.subscription_expiry_date = now_ts + timezone.timedelta(days=365)
                        else:
                            user.profile.subscription_expiry_date = now_ts + timezone.timedelta(days=30)

                        user.profile.save(update_fields=[
                            'wallet_balance', 'last_transaction_reference',
                            'plan', 'subscription_start_date', 'subscription_expiry_date'
                        ])
                        logger.info(f'Wallet/subscription updated for user {user_id}: +{amount} plan={plan}')
                    else:
                        logger.info(f'Transaction {reference} already processed for user {user_id}')

                    # Build summary AND auto-expire if past due
                    summary = _subscription_summary_and_autofix(user.profile)

                    return Response(
                        {
                            'message': 'Wallet credited and subscription updated successfully'
                                       if not already_processed else
                                       'Transaction already processed; returning current subscription status',
                            'already_processed': already_processed,
                            'balance': float(user.profile.wallet_balance),
                            'subscription': summary,
                        },
                        status=status.HTTP_200_OK
                    )

                elif transaction_status == 'abandoned':
                    logger.warning(f'Transaction abandoned: reference={reference}, user_id={user_id}')
                    return Response(
                        {'error': 'Transaction was abandoned and not completed. Please try again or contact support.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                return Response(
                    {'error': f'Transaction status {transaction_status} not supported'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {'error': 'Transaction verification failed. Please check your payment and try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f'Error in VerifyAndCreditView: {str(e)}')
            return Response(
                {'error': 'Something went wrong. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PrivateMessageMarkSeenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        other_user_id = request.data.get('user_id')
        if not other_user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark all messages sent to the current user by other_user_id as seen
        messages = PrivateMessage.objects.filter(
            sender_id=other_user_id,
            receiver=user,
            seen=False
        )
        updated_count = messages.update(seen=True)
        return Response({'marked_seen_count': updated_count}, status=status.HTTP_200_OK)

class PrivateMessageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        message = get_object_or_404(PrivateMessage, pk=pk)
        # Only allow sender or receiver to delete the message
        if message.sender != request.user and message.receiver != request.user:
            return Response({'error': 'You do not have permission to delete this message.'}, status=status.HTTP_403_FORBIDDEN)
        message.delete()
        return Response({'message': 'Message deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response({'error': 'Current password and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Return JSON response explicitly
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        # Return JSON response explicitly
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)

# views.py
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DeviceToken
from .utils import send_fcm_v1_to_token, send_fcm_v1_to_topic  # public helpers only

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_device_token(request):
    token     = request.data.get('token')
    platform  = request.data.get('platform')    # optional
    device_id = request.data.get('device_id')   # optional
    if not token:
        return Response({'error': 'Token is required'}, status=400)

    obj, created = DeviceToken.objects.get_or_create(
        user=request.user, token=token,
        defaults={"platform": platform or "", "device_id": device_id or ""}
    )
    if not created:
        changed = False
        if platform and obj.platform != platform:
            obj.platform = platform; changed = True
        if device_id and obj.device_id != device_id:
            obj.device_id = device_id; changed = True
        if changed:
            obj.save(update_fields=["platform", "device_id", "last_seen"])
    return Response({'message': 'Token saved'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notify_user_view(request):
    user_id = request.data.get('user_id')
    title   = request.data.get('title')
    message = request.data.get('message')
    data    = request.data.get('data', {})  # optional

    if not all([user_id, title, message]):
        return Response({'error': 'user_id, title, and message are required'}, status=400)

    user = get_object_or_404(User, id=user_id)
    tokens = list(DeviceToken.objects.filter(user=user).values_list('token', flat=True))
    if not tokens:
        return Response({'error': 'No device token for this user'}, status=404)

    results, dropped = [], 0
    for t in tokens:
        res = send_fcm_v1_to_token(t, title, message, data=data)
        if not res["ok"] and res.get("drop_token"):
            DeviceToken.objects.filter(token=t).delete()
            dropped += 1
        results.append(res["detail"])

    return Response({'message': 'Notification attempted', 'results': results, 'dropped': dropped}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notify_users_view(request):
    user_ids = request.data.get('user_ids')
    if not isinstance(user_ids, list) or not user_ids:
        return Response({'error': 'user_ids must be a non-empty list'}, status=400)
    title    = request.data.get('title')
    message  = request.data.get('message')
    data     = request.data.get('data', {})

    if not all([user_ids, title, message]):
        return Response({'error': 'user_ids, title, and message are required'}, status=400)

    tokens = list(DeviceToken.objects.filter(user_id__in=user_ids).values_list('token', flat=True))
    if not tokens:
        return Response({'error': 'No tokens found for these users'}, status=404)

    results, dropped = [], 0
    for t in tokens:
        res = send_fcm_v1_to_token(t, title, message, data=data)
        if not res["ok"] and res.get("drop_token"):
            DeviceToken.objects.filter(token=t).delete()
            dropped += 1
        results.append(res["detail"])

    return Response({'message': 'Notifications attempted', 'results': results, 'dropped': dropped}, status=200)

# Optional: Topic-based
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notify_topic_view(request):
    topic   = request.data.get('topic')  # without '/topics/'
    title   = request.data.get('title')
    message = request.data.get('message')
    data    = request.data.get('data', {})
    if not all([topic, title, message]):
        return Response({'error': 'topic, title, and message are required'}, status=400)
    res = send_fcm_v1_to_topic(topic, title, message, data=data)
    return Response(res, status=200 if res["ok"] else 400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_device_token(request):
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token is required'}, status=400)
    DeviceToken.objects.filter(user=request.user, token=token).delete()
    return Response({'message': 'Token deleted'}, status=200)


from rest_framework.permissions import IsAuthenticated
from .serializers import BankServiceChargeSerializer
from .models import BankServiceCharge
from django.contrib.auth.models import User


from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser

class BankServiceChargeUpdateView(APIView):
    authentication_classes = []                 # no JWT/Session auth
    permission_classes = [AllowAny]             # allow anonymous
    parser_classes = [MultiPartParser, FormParser]  # handle file uploads

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        bc = getattr(user, 'bank_service_charge', None)
        if not bc:
            return Response({'service_charge': None}, status=status.HTTP_200_OK)
        data = BankServiceChargeSerializer(bc, context={'request': request}).data
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        # fetch existing one (likely OneToOne), or create
        bc = getattr(user, 'bank_service_charge', None)
        if bc:
            serializer = BankServiceChargeSerializer(
                bc, data=request.data, partial=True, context={'request': request}
            )
        else:
            serializer = BankServiceChargeSerializer(
                data=request.data, context={'request': request}
            )

        serializer.is_valid(raise_exception=True)
        instance = serializer.save(user=user) if not bc else serializer.save()
        return Response(
            BankServiceChargeSerializer(instance, context={'request': request}).data,
            status=status.HTTP_200_OK
        )

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import UserProfile  # or your model
from django.contrib.auth.models import User

class UpdateUserStatusView(APIView):
    def patch(self, request, pk):
        """
        Update the user's status in a single endpoint.
        Example body: { "status": "active" }
        """
        allowed_statuses = ["pending", "active", "suspended"]  # validation

        user_profile = get_object_or_404(UserProfile, user__pk=pk)
        new_status = request.data.get("user_status")

        if not new_status:
            return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in allowed_statuses:
            return Response({"error": f"Invalid status. Allowed: {allowed_statuses}"},
                            status=status.HTTP_400_BAD_REQUEST)

        user_profile.user_status = new_status
        user_profile.save()

        return Response({
            "message": f"User status updated to '{new_status}'",
            "user_id": pk,
            "new_status": new_status
        }, status=status.HTTP_200_OK)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated

# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .serializers import UserSerializer

from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .serializers import UserSerializer

class FilterUsersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user_status = request.query_params.get("user_status")
        estate = request.query_params.get("estate")
        role_params = request.query_params.getlist("role")
        group_by_role = request.query_params.get("group_by_role") in ("1", "true", "True")

        allowed_roles = role_params or ["Residence", "Security Personnel"]

        # Query USERS and filter via related profile fields
        qs = (
            User.objects
            .select_related("profile", "bank_service_charge")  # 1-1 / 1-0 relateds
            .prefetch_related("transactions")                  # reverse FK
        )

        if user_status:
            qs = qs.filter(profile__user_status__iexact=user_status.strip())
        if estate:
            qs = qs.filter(profile__estate__iexact=estate.strip())

        qs = qs.filter(profile__role__in=allowed_roles)

        if group_by_role:
            residents_qs = qs.filter(profile__role="Residence")
            security_qs = qs.filter(profile__role="Security Personnel")
            return Response({
                "residents": UserSerializer(residents_qs, many=True, context={'request': request}).data,
                "security_personnel": UserSerializer(security_qs, many=True, context={'request': request}).data,
            }, status=status.HTTP_200_OK)

        data = UserSerializer(qs, many=True, context={'request': request}).data
        return Response(data, status=status.HTTP_200_OK)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from .serializers import UserSerializer  # you already have this

class PublicUserDetailView(APIView):
    authentication_classes = []          # no authentication at all
    permission_classes = [AllowAny]      # anyone can access

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        data = UserSerializer(user, context={'request': request}).data
        return Response(data, status=status.HTTP_200_OK)

class ResetPaidChargeView(APIView):
    authentication_classes = []                 # no JWT/Session auth
    permission_classes = [AllowAny]             # allow anonymous
    parser_classes = [MultiPartParser, FormParser]  # handle file uploads

    def post(self, request, user_id):
        # Allow only owner or staff to reset
        # if request.user.id != user_id and not request.user.is_staff:
        #     return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        bc = getattr(user, 'bank_service_charge', None)
        if not bc:
            return Response({'error': 'No bank service charge record'}, status=status.HTTP_404_NOT_FOUND)

        # Reset paid_charge and recalculate outstanding
        bc.paid_charge = Decimal('0.00')
        if bc.service_charge is not None:
            bc.outstanding_charge = bc.service_charge
        else:
            bc.outstanding_charge = Decimal('0.00')
        bc.save()

        return Response(
            BankServiceChargeSerializer(bc).data,
            status=status.HTTP_200_OK
        )
        

