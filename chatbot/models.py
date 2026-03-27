from django.db import models

# Create your models here.

class UserData(models.Model):
    user_question = models.TextField()
    generated_sql = models.TextField(blank=True, null=True)
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f" the user question is {self.user_question[:50]}"
    
    