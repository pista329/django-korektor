# -*- coding: utf-8 -*- 

from django.db import models, connections, connection, transaction
from django.conf import settings


class Locale(models.Model):
    
    id = models.PositiveSmallIntegerField(primary_key=True)
    code = models.CharField(max_length=255,unique=True)
    name = models.CharField(max_length=255)
    local_name = models.CharField(max_length=255)
    
    class Meta:
        db_table = "djkorektor_locales"
    
    pass

class Bigram(models.Model):
    
    id = models.AutoField(primary_key=True)
    ngram = models.CharField(max_length=2)
    ngram_sorted = models.CharField(max_length=2)
    ngram_unidecoded = models.CharField(max_length=6)
    ngram_unidecoded_sorted = models.CharField(max_length=6)
    locale = models.ForeignKey(Locale,on_delete=models.DO_NOTHING, db_constraint=False)
    
    class Meta:
        db_table = "djkorektor_bigrams"
        unique_together = (("ngram", "locale"),)
    
    pass

class Word(models.Model):
    
    id = models.AutoField(primary_key=True)
    word = models.CharField(max_length=255)
    word_unidecoded = models.CharField(max_length=255)
    length = models.PositiveIntegerField()
    quality_index = models.PositiveSmallIntegerField(default=1)
    count = models.PositiveIntegerField(default=1)
    locale = models.ForeignKey(Locale,on_delete=models.DO_NOTHING, db_constraint=False)
    
    class Meta:
        db_table = "djkorektor_words"
        unique_together = (("word", "locale"),)
    
    pass

class WordBigram(models.Model):
    
    id = models.AutoField(primary_key=True)
    bigram = models.ForeignKey(Bigram, on_delete=models.CASCADE, db_constraint=False)
    bigram_index = models.PositiveIntegerField()
    bigram_total = models.PositiveIntegerField()
    bigram_perc = models.FloatField()
    word = models.ForeignKey(Word, on_delete=models.CASCADE, db_constraint=False)
    word_length = models.PositiveIntegerField()
    word_quality_index = models.PositiveSmallIntegerField(default=1)
    word_count = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = "djkorektor_words_bigrams"
        unique_together = (("word", "bigram", "bigram_index"),)
        index_together = (("bigram", "word_length", "word_count", "word_quality_index"),)
    
    pass

class WordPair(models.Model):
    
    id = models.AutoField(primary_key=True)
    left = models.ForeignKey(Word, null=True, related_name="left_word", on_delete=models.CASCADE, db_constraint=False)
    right = models.ForeignKey(Word, null=True, related_name="right_word", on_delete=models.CASCADE, db_constraint=False)
    count = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = "djkorektor_words_pairs"
        unique_together = (("left", "right"),)
    
    pass