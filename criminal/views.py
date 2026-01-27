from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .services.rag_service import get_chain

@csrf_exempt
def index(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            chain = get_chain()
            result = chain.invoke(message)
            return JsonResponse({'message': result, 'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Invalid JSON', 'status': 'error'}, status=400)
    return render(request, 'criminal.html')
