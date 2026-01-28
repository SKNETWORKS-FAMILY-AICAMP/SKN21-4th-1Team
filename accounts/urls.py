from django.urls import path
from django.shortcuts import render

urlpatterns = [
    # /accounts/login/ 주소로 접속하면 위에서 만든 파일을 보여줌
    path('login/', lambda r: render(r, 'accounts/login.html'), name='login'),
]