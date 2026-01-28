from django.urls import path
from django.shortcuts import render
from . import views

urlpatterns = [
    # /accounts/login/ 주소로 접속하면 위에서 만든 파일을 보여줌
    path('', views.index, name='index'),
    path('login/', lambda r: render(r, 'account/login.html'), name='login'),
]

