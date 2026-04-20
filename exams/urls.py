from django.urls import path
from django.http import HttpResponse

app_name = 'exams'


def stub(request, **kwargs): return HttpResponse("Coming in Step 3!")


urlpatterns = [
    path('',                      stub, name='list'),
    path('create/',               stub, name='create'),
    path('<uuid:pk>/',            stub, name='detail'),
    path('<uuid:pk>/grade/',      stub, name='grade'),
    path('review/',               stub, name='admin_review'),
    path('results/',              stub, name='my_results'),
]
