"""
URL configuration for inventory_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Import Django's built-in authentication views
from django.views.generic import RedirectView # Optional: For redirecting the root URL
from inventory import views as inventory_views

urlpatterns = [
    # Django Admin Site
    path('admin/', admin.site.urls),

    # Include URLs from the 'inventory' app
    # All URLs starting with '' (the root) will be checked against inventory.urls
    path('', include('inventory.urls')),

    # Authentication URLs (using Django's built-in views)
    # Login View: Uses the specified template
    path('login/',
         auth_views.LoginView.as_view(template_name='registration/login.html'),
         name='login'),

    # Logout View: Redirects to LOGOUT_REDIRECT_URL defined in settings.py (defaults to 'login')
    path('logout/',
         auth_views.LogoutView.as_view(),
         name='logout'),

    path('register/', inventory_views.register, name='register'),




        # Add password reset URLs if you plan to implement them (optional)
    path('password_reset/',
        auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
        name='password_reset'),
    path('password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
        name='password_reset_confirm'),
    path('reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete'),
]