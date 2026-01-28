from django.urls import path
from django.shortcuts import render
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', lambda r: render(r, 'account/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
]

