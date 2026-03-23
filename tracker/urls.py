from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.index,               name='index'),
    path('login/',              views.login_view,          name='login'),
    path('register/',           views.register_view,       name='register'),
    path('logout/',             views.logout_view,         name='logout'),
    path('dashboard/',          views.dashboard,           name='dashboard'),
    path('add/',                views.add_product,         name='add_product'),
    path('remove/<int:tracked_id>/',   views.remove_product,      name='remove_product'),
    path('history/<int:tracked_id>/',  views.price_history,       name='price_history'),
    path('update-price/',       views.update_desired_price, name='update_desired_price'),
    path('profile/',            views.profile,             name='profile'),
]

