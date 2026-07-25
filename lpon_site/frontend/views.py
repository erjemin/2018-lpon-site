#

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

# Create your views here.

def index(request: HttpRequest | None) -> HttpResponse:
    return render(request, 'index.html', {})


def catalog(request: HttpRequest | None) -> HttpResponse:
    return render(request, 'catalog.html', {})