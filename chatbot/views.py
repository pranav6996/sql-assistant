from django.shortcuts import render
from .models import UserData
from .services import run_ai_agent



def chat_view(request):

    response_data=None
    sql_query=None

    if request.method=='POST':

        user_query=request.POST.get('message')

        result=run_ai_agent(user_query)
        sql_query=result['sql']

        UserData.objects.create(
            user_question=user_query,
            ai_response=result['answer'],
            generated_sql=result['sql']
            )

        response_data=result['answer']

    history = UserData.objects.all().order_by('-created_at')

    return render(request, 'chatbot/chat.html', {
        'response': response_data,
        'history': history,
        'sql_query':sql_query
    })

