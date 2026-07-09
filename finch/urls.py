from django.urls import path, include
from . import views
from . import health

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate_account'),
    path('', include('django.contrib.auth.urls')),
    path('follow/<int:author_id>/', views.follow_user, name='follow_user'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('post/<int:finch_id>/', views.finch_detail, name='finch_detail'),
    path('post/<int:finch_id>/repost/', views.repost_finch, name='repost_finch'),
    path('post/<int:finch_id>/delete/', views.delete_finch, name='delete_finch'),
    path('subscriptions/', views.subscriptions_list, name='subscriptions_list'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/status/', views.notifications_status, name='notifications_status'),
    path('notifications/updates/', views.notifications_updates, name='notifications_updates'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('api/', include('finch.api.urls')),
    path('health/', health.health_check, name='health_check'),
]
