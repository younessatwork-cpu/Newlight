import hashlib
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from .models import SystemUser


def sha256_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode('utf-8')).hexdigest()


def authenticate(username: str, password: str):
    try:
        user = SystemUser.objects.get(username=username)
    except SystemUser.DoesNotExist:
        return None
    if user.password_hash == sha256_password(password):
        return user
    return None


def login_session(request, user: SystemUser):
    request.session.flush()
    request.session['user'] = {
        'username': user.username,
        'role': user.role,
        'reference': user.reference,
    }
    request.session.set_expiry(60 * 60 * 12)


def current_user(request):
    return request.session.get('user')


def logout_session(request):
    request.session.flush()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not current_user(request):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = current_user(request)
            if not user:
                return redirect('login')
            if user.get('role') not in roles:
                messages.error(request, 'You do not have permission to access that page.')
                if user.get('role') == 'Client':
                    return redirect('vip_portal')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def is_admin(request):
    user = current_user(request)
    return bool(user and user.get('role') == 'Admin')


def is_technician(request):
    user = current_user(request)
    return bool(user and user.get('role') == 'Technician')
