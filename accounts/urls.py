from django.urls import path
from django.shortcuts import render
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout_view, name="logout"),
]
