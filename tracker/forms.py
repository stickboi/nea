from urllib.parse import urlsplit, urlunsplit

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User




def normalize_product_url(url):
    """Normalize a product URL so the same item maps to one database entry."""
    split_url = urlsplit(url.strip())
    normalized_path = split_url.path.rstrip('/') or '/'
    return urlunsplit((split_url.scheme.lower(), split_url.netloc.lower(), normalized_path, '', ''))

class RegisterForm(forms.Form):
    """
    Registration form - implements Algorithm 1 validation rules from the design.
    """
    email            = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'})
    )
    password         = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'At least 8 characters'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat password'})
    )
    user_num = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07700900000'})
    )

    def clean(self):
        cleaned = super().clean()
        password         = cleaned.get('password')
        confirm_password = cleaned.get('confirm_password')

        # Check passwords match (Algorithm 1 step 1)
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        # Check email isn't already registered (Algorithm 1 step 3)
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with that email already exists.")
        return email

    def clean_user_num(self):
        num = self.cleaned_data.get('user_num', '').strip()
        if num:
            # Must be exactly 11 digits as per the data dictionary
            if not num.isdigit() or len(num) != 11:
                raise forms.ValidationError("Phone number must be exactly 11 digits (e.g. 07777755582).")
        return num or None


class LoginForm(AuthenticationForm):
    """
    Customise Django's built-in login form to add Bootstrap classes.
    """
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )


class AddProductForm(forms.Form):
    """
    Add product form - Algorithm 2: AddProductToTrack.
    User pastes a URL and optionally sets a desired price.
    """
    product_url = forms.URLField(
        label='Product URL',
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'https://www.amazon.co.uk/dp/...'
        })
    )
    desired_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0.01,
        label='Target Price (£)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'step': '0.01',
            'placeholder': 'e.g. 29.99'
        })
    )

    def clean_product_url(self):
        url = normalize_product_url(self.cleaned_data['product_url'])
        # Validate the URL is from a supported retailer
        supported = ['amazon.co.uk', 'currys.co.uk', 'johnlewis.com', 'argos.co.uk']
        if not any(domain in url for domain in supported):
            raise forms.ValidationError(
                "That URL isn't from a supported retailer. "
                "We support: Amazon UK, Currys, John Lewis, and Argos."
            )
        return url


class UpdateDesiredPriceForm(forms.Form):
    """Small inline form for updating the target price on the dashboard."""
    desired_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    product_id  = forms.IntegerField(widget=forms.HiddenInput)
    retailer_id = forms.IntegerField(widget=forms.HiddenInput)


class ProfileForm(forms.Form):
    """Lets the user update their phone number."""
    user_num = forms.CharField(
        required=False,
        label='Phone number',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07700900000'})
    )

    def clean_user_num(self):
        num = self.cleaned_data.get('user_num', '').strip()
        if num:
            if not num.isdigit() or len(num) != 11:
                raise forms.ValidationError("Phone number must be exactly 11 digits.")
        return num or None

