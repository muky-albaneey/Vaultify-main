from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.core.validators import FileExtensionValidator


class UserProfile(models.Model):
    USER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),  # optional, for future expansion
    ]
    
      # NEW: apartment/flat types
    APARTMENT_TYPE_CHOICES = [
        ('self_contain', 'Self-contain'),
        ('1_bed',        '1-Bedroom Flat'),
        ('2_bed',        '2-Bedroom Flat'),
        ('3_bed',        '3-Bedroom Flat'),
        ('4_bed',        '4-Bedroom Flat'),
        ('5_plus',       '5+ Bedroom Flat'),
    ]
       
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    estate = models.CharField(max_length=100, blank=True, null=True)
    estate_email = models.EmailField(blank=True, null=True)
    house_address = models.CharField(max_length=255, blank=True, null=True)
     # 🔽 NEW FIELD (dropdown)
    apartment_type = models.CharField(
        max_length=16,
        choices=APARTMENT_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Type of flat/apartment (e.g., Self-contain, 1-Bedroom Flat)"
    )

    pin = models.CharField(max_length=128, blank=True, null=True)  # Hashed PIN
    plan = models.CharField(max_length=50, blank=True, null=True)
    subscription_start_date = models.DateTimeField(blank=True, null=True)
    subscription_expiry_date = models.DateTimeField(blank=True, null=True)
    last_transaction_reference = models.CharField(max_length=255, blank=True, null=True)
    wallet_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    profile_picture = models.URLField(max_length=500, blank=True, null=True)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    password_reset_otp = models.CharField(max_length=6, blank=True, null=True)
    password_reset_otp_expiry = models.DateTimeField(blank=True, null=True)
    signup_otp = models.CharField(max_length=6, blank=True, null=True)
    signup_otp_expiry = models.DateTimeField(blank=True, null=True)
    # 🔽 NEW FIELD HERE
    user_status = models.CharField(
        max_length=20,
        choices=USER_STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"
# --------------------------
# BankServiceCharge model (new)
# --------------------------
class BankServiceCharge(models.Model):
    PAYMENT_FREQUENCY_CHOICES = [
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Yearly', 'Yearly'),
    ]

    # Attach to user; nullable so a user may have no service charge set
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='bank_service_charge',
        null=True,
        blank=True
    )

    service_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        null=True,
        blank=True,
        help_text="Service Charge in Naira (#)"
    )
    paid_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        null=True,
        blank=True,
        help_text="Paid Charge in Naira (#)"
    )
    
    outstanding_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        null=True,
        blank=True,
        help_text="Outstanding Charge in Naira (#)"
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        null=True,
        blank=True
    )
    bank_name = models.CharField(max_length=150, null=True, blank=True)
    account_name = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)  # validate in serializer
    
    receipt_image = models.FileField(
        upload_to='service_charge_receipts/',
        null=True,
        blank=True,
        help_text="Upload any file for the payment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"ServiceCharge for {self.user.username}"
        return "ServiceCharge (unattached)"
# --------------------------
# Ensure profile + service charge are created when a User is created
# Put this receiver AFTER the model classes above
# --------------------------
@receiver(post_save, sender=User)
def create_user_related_objects(sender, instance, created, **kwargs):
    """
    When a new User is created, create a blank UserProfile and a blank BankServiceCharge
    so both objects always exist and can be updated later.
    """
    if created:
        # create profile if it doesn't exist
        # UserProfile.objects.create(user=instance)
        # create an empty bank service charge record attached to the user
        BankServiceCharge.objects.create(user=instance)
       
       
class BankServiceChargeFile(models.Model):
    bank_service_charge = models.ForeignKey(
        'BankServiceCharge',
        on_delete=models.CASCADE,
        related_name='receipt_files'
    )
    file = models.FileField(
        upload_to='service_charge_receipts/',
        help_text="Upload any file for the payment"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File for {self.bank_service_charge} - {self.file.name}"
 
class AccessCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    visitor_name = models.CharField(max_length=255)
    visitor_email = models.EmailField()
    visitor_phone = models.CharField(max_length=20)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_uses = models.PositiveIntegerField(default=1)
    current_uses = models.PositiveIntegerField(default=0)
    gate = models.CharField(max_length=50)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_codes')
    is_active = models.BooleanField(default=True)
    notify_on_use = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AccessCode {self.code} for {self.visitor_name}"

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    # No need to call save() unless there are updates to the profile
    
class Alert(models.Model):
    ALERT_TYPES = [
        ('Visitor Arrival', 'Visitor Arrival'),
        ('Fire Alarm', 'Fire Alarm'),
        ('Security Breach', 'Security Breach'),
        ('others', 'others'),
    ]
    URGENCY_LEVELS = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    message = models.TextField()
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    recipients = models.JSONField()  # Store list of recipients (e.g., ["Security", "Management"])
    urgency_level = models.CharField(max_length=20, choices=URGENCY_LEVELS)
    timestamp = models.DateTimeField(auto_now_add=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.alert_type} - {self.message[:50]}"

class UserDeletedAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deleted_alerts')
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='deleted_by_users')
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'alert')

    def __str__(self):
        return f"Deleted Alert {self.alert.id} by User {self.user.username}"


from django.db import models
from django.contrib.auth.models import User
class LostFoundItem(models.Model):
    ITEM_TYPES = [
        ('Lost', 'Lost'),
        ('Found', 'Found'),
    ]

    description = models.TextField()
    item_type = models.CharField(max_length=10, choices=ITEM_TYPES)
    location = models.CharField(max_length=255, blank=True, null=True)
    date_reported = models.DateTimeField(auto_now_add=True)
    contact_info = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='lostfound_images/', blank=True, null=True)

    sender = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.item_type} Item - {self.description[:50]}"


class PrivateMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username} at {self.timestamp}"


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Transaction {self.reference} for {self.user.username} - {self.status} - {self.amount}"



from django.db import models
from django.contrib.auth.models import User

class DeviceToken(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token     = models.CharField(max_length=255)                 # no unique=True
    platform  = models.CharField(max_length=16, blank=True)      # "android" | "ios" | "web"
    device_id = models.CharField(max_length=128, blank=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "token")
        indexes = [models.Index(fields=["token"])]

    def __str__(self):
        return f"{self.user.username} - {self.token[:12]}..."

