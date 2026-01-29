from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_not_required


@csrf_exempt
def index(request):
    return JsonResponse({"message": "success"})


@login_not_required
def login(request):
    return render(request, "account/login.html")


@login_not_required
def logout_view(request):
    logout(request)
    return redirect("/")  # 로그아웃 후 메인 페이지로 이동
