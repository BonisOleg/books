from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Логін'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ім\'я'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Прізвище'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+380...', 'type': 'tel'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Пароль'})
        self.fields['password2'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Підтвердження'})


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Логін або email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Пароль'})
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'patronymic', 'phone', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'type': 'tel'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
        }
