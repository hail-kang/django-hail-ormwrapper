from django.db import models

class FirstModel(models.Model):
    key = models.CharField(max_length=45)
    value = models.IntegerField()

class SecondModel(models.Model):
    key = models.CharField(max_length=45)
    value = models.IntegerField()
    first = models.ForeignKey(FirstModel, on_delete=models.CASCADE, related_name='second_set')

class ThirdModel(models.Model):
    key = models.CharField(max_length=45)
    value = models.IntegerField()
    second = models.ForeignKey(SecondModel, on_delete=models.CASCADE, related_name='third_set')