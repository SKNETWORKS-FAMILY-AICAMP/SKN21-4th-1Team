#!/usr/bin/env python
"""
장고 폼에서 생성된 HTML 구조를 확인하는 스크립트
"""
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 이제 Django를 import할 수 있습니다
from django.contrib.auth.forms import UserCreationForm

# UserCreationForm으로 생성되는 HTML 확인
form = UserCreationForm()
print("=" * 80)
print("Django UserCreationForm 기본 렌더링")
print("=" * 80)
print(form.as_p())
print("\n")

# 각 필드별로 자세히 보기
print("=" * 80)
print("필드별 상세 정보")
print("=" * 80)
for field_name, field in form.fields.items():
    print(f"\n필드명: {field_name}")
    print(f"필드 타입: {type(field).__name__}")
    print(f"Help text: {field.help_text}")
    print(f"Widget: {type(field.widget).__name__}")
    print("-" * 40)
