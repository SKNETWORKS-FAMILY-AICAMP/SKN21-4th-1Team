# 법령 검색 및 Q&A 챗봇 
> RAG + LLM + Django 기반 법률 Q&A 챗봇


본 프로젝트는 **법령 데이터를 기반으로 사용자의 질문에 근거 있는 답변을 제공하는 AI 챗봇 웹서비스**입니다.  
RAG(Retrieval-Augmented Generation) 구조를 적용하여, 실제 법령 조문을 검색한 뒤 LLM을 통해 답변을 생성합니다.


<div align="center">

[![Django](https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

</div>


---

## 📑 목차


---


### 프로젝트 정보
- **프로젝트명**: 법
- **개발 기간**: 3차(RAG 챗봇) + 4차(웹 서비스) 통합 프로젝트
- **팀 구성**: 6명
- **개발 환경**: Python 3.12+, SQLite
---

### 프로젝트 배경

일반 사용자가 법령을 직접 검색하고 해석하는 것은 매우 어렵습니다.

- ❌ 법률 용어가 어렵고  
- ❌ 필요한 조문을 찾기 힘들며  
- ❌ 상황에 맞는 해석을 얻기 어렵기 때문입니다  

이를 해결하기 위해, **법령 데이터를 AI가 이해하고 설명해주는 챗봇 웹서비스**를 기획했습니다.

---

## 🎯 프로젝트 목표

- 법령 데이터를 **조문 단위로 구조화**
- 벡터 검색 기반 **정확한 근거 제시**
- Django 기반 **웹 챗봇 UI 구현**
- 누구나 쉽게 사용할 수 있는 **법률 Q&A 서비스**

---

## ✨ 주요 기능

### 1. 법령 기반 질의응답
- 사용자의 질문을 자연어로 입력
- 관련 법령 조문을 벡터 검색
- 검색 결과를 기반으로 AI 답변 생성

### 2. 근거 중심 답변
- 단순 요약이 아닌 **관련 조문 포함 답변**
- 법령 출처 명시

### 3. 웹 챗봇 UI
- Django 기반 웹 페이지
- 실시간 채팅 형태의 UX
- 사용자 질문 / AI 답변 기록 유지

---


---

## 📝 회고


## 🚀 아쉬운 점 및 개선 방향

### 아쉬운 점

### 향후 개선 계획
