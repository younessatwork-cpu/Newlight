def session_user(request):
    user = request.session.get('user')
    rain_money = bool(request.session.pop('rain_money', False)) if hasattr(request, 'session') else False
    return {
        'session_user': user,
        'is_admin': bool(user and user.get('role') == 'Admin'),
        'is_technician': bool(user and user.get('role') == 'Technician'),
        'is_client': bool(user and user.get('role') == 'Client'),
        'rain_money': rain_money,
    }
