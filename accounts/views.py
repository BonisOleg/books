from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from .forms import RegisterForm, LoginForm, ProfileForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Реєстрація успішна!')
            return redirect('core:home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {
        'form': form,
        'page_title': 'Реєстрація',
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {
        'form': form,
        'page_title': 'Вхід',
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect('core:home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профіль оновлено.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)

    orders = request.user.orders.all().order_by('-created_at')[:10]
    return render(request, 'accounts/profile.html', {
        'form': form,
        'user_orders': orders,
        'page_title': 'Мій профіль',
    })
