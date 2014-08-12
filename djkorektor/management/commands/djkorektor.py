# -*- coding: utf-8 -*-

from __future__ import absolute_import
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Max, Min, Q, F
from djkorektor import models
from django.db.utils import IntegrityError
from django.db import connection, connections, transaction
from optparse import make_option
import datetime, re, copy, codecs
import time

try:
	from ordereddict import OrderedDict
except ImportError:
	print "ordereddict module import failed > pip install ordereddict"

try:
	from unidecode import unidecode
except ImportError:
	print "unidecode module import failed > pip install unidecode"

import locale as syslocale

def dictfetchall(cursor):
	"Returns all rows from a cursor as a dict - Django docs"
	desc = cursor.description
	return [
		dict(zip([col[0] for col in desc], row))
		for row in cursor.fetchall()
	]

class Timer:    
	def __enter__(self):
		self.start = time.time()
		return self
	
	def __exit__(self, *args):
		self.end = time.time()
		self.interval = self.end - self.start

class DJKorektorException(Exception):
	pass

"""
	
	Classical Damereau errors (1964):
	
	Substitution 
		[ALPHABET] -> [ALPHSBET] 
	Deletion 
		[ALPHABET] -> [ALPHBET] 
	Insertion 
		[ALPHABET] -> [ALPHAABET] 
	Transposition 
		[ALPHABET] -> [ALPHBAET] 
		
						F.J. Damereau
"""

class Command(BaseCommand):

	re_word_spliter = re.compile(u"[\s,.+=;:<>\[\](){}\"'/™®„“‚‘»«€•$^!?]+", re.UNICODE)
	# TODO rozdelovat aj podla interpunkcie, ale len ked za nou nasleduje ciarka
	re_query_spliter = re.compile(u"[\s]+", re.UNICODE)
	re_sentence_spliter = re.compile(u"[.;:\"'„“‚‘»«•!?]+", re.UNICODE)
	re_text_nums = re.compile(u"^\d")
	re_text_urls = re.compile(u'((?:https?://|ftp://|www\.)[-_\w\d\.]+(?:[?#&/a-zA-Z\d:\@%;!$(),’~_\+\-=\\\.]+?))(?=[\.,:)\]\}\'"]*(\s|\Z))', re.MULTILINE | re.DOTALL | re.UNICODE | re.IGNORECASE)
	re_text_emails = re.compile(u"(?<=[\s,;:\(\)\{\}\[\]\<\>])(?P<address>[A-Z0-9\._%+-]+@(?P<domain>[A-Z0-9\.-]+\.[A-Z0-9-]{2,}))", re.MULTILINE | re.DOTALL | re.UNICODE | re.IGNORECASE)
	
	verbosity = 0
	using = None
	locale = None
	
	help = """This is *djkorektor* management command. Import your spellcheck learning datasets (huge chunks of texts) or import standalone words or test spelling suggestions.
    
    Example usage: 
    ./manage.py djkorektor --import_word="Bigrams are fun! It is raining, let's dance together. It will be my pleasure." --locale=en_US
    ./manage.py djkorektor --spell="It is fn to dnce" --locale=en_US
		"""
	
	option_list = BaseCommand.option_list + (
		make_option('--import_file',
			action='store',
			dest='import_file',
			default=None,
			type=str,
			help='Learning from plain text file.'),
		make_option('--import_word',
			action='store',
			dest='import_word',
			default=None,
			#type=unicode,
			help='Learning of single word or sentence.'),
		make_option('--spell',
			action='store',
			dest='spell',
			default=None,
			#type=unicode,
			help='Test spellcheck on any word/sentence.'),
		make_option('--locale',
			action='store',
			dest='locale',
			default=None,
			type=str,
			help='Specify locale string eg. sk_SK, de, en_GB - mandatory'),
		make_option('--using',
			action='store',
			dest='using',
			default=None,
			type=str,
			help='Specify db connection if necessary.'),
		)
	
	def strtouni(self,param):
		try:
			if isinstance(param,unicode):
				return "'%s'" % param
			else:
				return "'%s'" % unicode(param,encoding="utf-8",errors="replace")
		except TypeError,e:
			pass
		return param
	
	def split_bywords(self,text):
		output = text
		if "http" in output or "www" in output:
			output = self.re_text_urls.sub(" ",output)
		if "@" in output:
			output = self.re_text_emails.sub(" ",output)
		return [w for w in self.re_word_spliter.split(output)], self.re_word_spliter.findall(output)+[""]
	
	def split_query_bywords(self,text):
		output = text
		return [w for w in self.re_query_spliter.split(output)], self.re_query_spliter.findall(output)+[""]
	
	def split_bysentences(self,text):
		output = text
		if "http" in output or "www" in output:
			output = self.re_text_urls.sub(" ",output)
		if "@" in output:
			output = self.re_text_emails.sub(" ",output)
		return [w for w in self.re_sentence_spliter.split(output)], self.re_sentence_spliter.findall(output)+[""]
		
	def pairs_from_text(self,text):
		if isinstance(text,(str,)):
			text, separators = self.split_bywords(text)
		if isinstance(text,(list,tuple,)):
			return zip(text, text[1:])
		return None
	
	def load_locale(self,locale_code):
		locale = models.Locale.objects.filter(code=locale_code.lower())[:1]
		if len(locale):
			self.locale = locale[0]
			locale_parts = self.locale.code.split("_")
			syslocale_code = "%s_%s.utf8" % (locale_parts[0],locale_parts[1].upper(),) if len(locale_parts) > 1 else "%s.utf8" % locale_parts[0]
			try:
				syslocale.setlocale(syslocale.LC_ALL, str(syslocale_code))
			except syslocale.Error,e:
				raise Exception("Unable to set locale %s - %s. Check available locales with \"locale -a\", then install if necessary \"sudo locale-gen %s; sudo update-locale;\". " % (syslocale_code,str(e),syslocale_code))
		else:
			raise Exception("Unknown locale %s. Check `%s` table in your database for appropriate locale code." % (options["locale"],models.Locale._meta.db_table))
		pass
	
	def bigrams_from_word(self,word):
		word_length = len(word)
		if word_length < 1: # saving also one-letter words
			return None
		if word.isdigit():
			return None
		if self.re_text_nums.match(word) is not None:
			return None
		chars_list = list(" %s " % word)
		return ["".join(bigram_touple) for bigram_touple in zip(chars_list, chars_list[1:])]
	
	def save_pairs_batch(self,pairs,locale):
		if len([pair for pair in pairs if pair]) < 2:
			return
		# Fast one query operation
		raw_words_pairs_params = []
		raw_words_pairs_tmplate = []
		for ngram_index,ngram_value in enumerate(pairs):
			if ngram_value[0] != "" and ngram_value[1] != "":
				raw_words_pairs_tmplate.append("((SELECT `djkorektor_words`.`id` FROM `djkorektor_words` WHERE `djkorektor_words`.`word` = '%s' AND `djkorektor_words`.`locale_id` = %d), (SELECT `djkorektor_words`.`id` FROM `djkorektor_words` WHERE `djkorektor_words`.`word` = '%s' AND `djkorektor_words`.`locale_id` = %d), 1)")
				raw_words_pairs_params.extend([ngram_value[0].lower(),int(locale.id),ngram_value[1].lower(),int(locale.id)])
			elif ngram_value[0] == "":
				raw_words_pairs_tmplate.append("(NULL, (SELECT `djkorektor_words`.`id` FROM `djkorektor_words` WHERE `djkorektor_words`.`word` = '%s' AND `djkorektor_words`.`locale_id` = %d), 1)")
				raw_words_pairs_params.extend([ngram_value[1].lower(),int(locale.id)])
			elif ngram_value[1] == "":
				raw_words_pairs_tmplate.append("((SELECT `djkorektor_words`.`id` FROM `djkorektor_words` WHERE `djkorektor_words`.`word` = '%s' AND `djkorektor_words`.`locale_id` = %d), NULL, 1)")
				raw_words_pairs_params.extend([ngram_value[0].lower(),int(locale.id)])
		if len(raw_words_pairs_tmplate):
			self.cursor.execute("INSERT IGNORE INTO `djkorektor_words_pairs` (`left_id`, `right_id`, `count`) VALUES %s ON DUPLICATE KEY UPDATE `count`=`count`+1" % ((", ".join(raw_words_pairs_tmplate)) % tuple(raw_words_pairs_params),))
		transaction.commit()
		pass
	
	def save_bigrams_batch(self,ngrams,word):
		ngram_total=len(ngrams)
		bigrams_in_db = dict((row.ngram, row.pk) for row in models.Bigram.objects.filter(ngram__in=ngrams,locale=word.locale).all())
		if len(bigrams_in_db) < len(ngrams):
			transaction.enter_transaction_management()
			for ngram_index,ngram_value in enumerate(ngrams):
				ngram_unidecoded=unidecode(ngram_value)
				ngram_sorted = ''.join(sorted(list(ngram_value),cmp=syslocale.strcoll))
				try:
					# Bigrams in separate table. ~1600 combinations per language locale
					bigram_in_db, created = models.Bigram.objects.get_or_create(
						ngram=ngram_value,
						locale=word.locale,
						defaults={'ngram':ngram_value,'ngram_unidecoded':ngram_unidecoded,'ngram_sorted':ngram_sorted,'ngram_unidecoded_sorted':''.join(sorted(ngram_unidecoded)),'locale':word.locale})
				except IntegrityError,e:
					pass
			transaction.commit_unless_managed()
			bigrams_in_db = dict((row.ngram, row.pk) for row in models.Bigram.objects.filter(ngram__in=ngrams,locale=word.locale).all())
		
		raw_words_bigrams_params = []
		raw_words_bigrams_tmplate = []
		for ngram_index,ngram_value in enumerate(ngrams):
			raw_words_bigrams_tmplate.append("(%s,%s,%s,%s,%s,%s,%s,%s)")
			raw_words_bigrams_params.extend([int(bigrams_in_db.get(ngram_value)),int(ngram_index),int(ngram_total),str(float(1.0/ngram_total)),int(word.id),int(word.length),int(word.quality_index),int(word.count)])
		# Faster way and memory efficient way - insert all bigrams at once
		self.cursor.execute("INSERT IGNORE INTO `djkorektor_words_bigrams` (`bigram_id`, `bigram_index`, `bigram_total`, `bigram_perc`, `word_id`, `word_length`, `word_quality_index`, `word_count`) VALUES " + (", ".join(raw_words_bigrams_tmplate)), raw_words_bigrams_params)
		transaction.commit()
		pass

	def import_sentence(self,sentence,locale):
		words, separators_w = self.split_bywords(sentence)
		for word in words:
			self.import_word(word,locale)
		words_pairs = self.pairs_from_text(words)
		self.save_pairs_batch(words_pairs,locale)
		pass

	def import_word(self,import_word,locale):
		word = import_word.lower()
		bigrams = self.bigrams_from_word(word)
		if not bigrams:
			return
		word_in_db, created = models.Word.objects.get_or_create(word=word,locale=locale,defaults={'word':word,'word_unidecoded':unidecode(word),'length':len(word),'locale':locale,'quality_index':1,'count':1})
		if created == False:
			word_in_db.count = word_in_db.count+1
			word_in_db.save(update_fields=["count"],using=self.using)
		ngram_total=len(bigrams)
		self.save_bigrams_batch(bigrams,word_in_db)
		if self.verbosity > 0:
			self.stdout.write("Imported \"%s\" as set of %s" % (word,tuple(self.strtouni(ngram) for ngram in bigrams),))
		pass

	def do_spelling(self,query,locale):
		query_words, query_separators = self.split_query_bywords(query)
		words_dbs = dict()
		query_words_bigrams = dict()
		query_words_bigrams_all = []
		query_words_bigrams_sorted = dict()
		query_words_bigrams_sorted_all = []
		for query_word in query_words:
			query_words_bigrams[query_word] = self.bigrams_from_word(query_word.lower())
			query_words_bigrams_all.extend(query_words_bigrams[query_word])
			query_words_bigrams_sorted[query_word] = [''.join(sorted(chars,cmp=syslocale.strcoll)) for chars in query_words_bigrams[query_word]]
			query_words_bigrams_sorted_all.extend(query_words_bigrams_sorted[query_word])
			
		bigrams_db = models.Bigram.objects.filter(locale=locale).filter(Q(ngram_sorted__in=set(query_words_bigrams_sorted_all)) | Q(ngram__in=set(query_words_bigrams_all))).all()
		bigrams_by_ngram = dict([(ngram.ngram,ngram) for ngram in bigrams_db])
		
		for query_word in query_words:
			query_word_length=len(query_word)
			if not query_words_bigrams[query_word]:
				continue
			min_match_count = 1 if query_word_length > 2 else 200
			
			queryset = models.WordBigram.objects\
				.filter(bigram_id__in=[bigrams_by_ngram.get(query_bigram).id for query_bigram in query_words_bigrams[query_word] if bigrams_by_ngram.get(query_bigram,None)])\
				.filter(word_length__range=(max(2,query_word_length-1),min(1e3,query_word_length+1)))\
				.filter(Q(word_count__gte=min_match_count) | Q(word_quality_index__gte=1))\
				.values("word_id")\
				.annotate(ngrams_count=Count("id"),ngrams_weight=Sum("bigram_perc"))\
				.order_by("-ngrams_weight","-ngrams_count")[:10]
			
			sql, params = queryset.query.sql_with_params()
			sql = sql.replace("SELECT","SELECT `djkorektor_words`.`id`, `djkorektor_words`.`word`, `djkorektor_words`.`length`, `djkorektor_words`.`count`, `djkorektor_words`.`quality_index`,",1).replace("FROM `djkorektor_words_bigrams`","FROM `djkorektor_words_bigrams` LEFT JOIN `djkorektor_words` ON (`djkorektor_words_bigrams`.`word_id` = `djkorektor_words`.`id`)")
			
			if self.verbosity > 2:
				self.stdout.write('')
				self.stdout.write("Query for \"%s\":" % query_word)
				self.stdout.write(sql % tuple(params))
			
			self.cursor.execute(sql, tuple(params))
			matches = dictfetchall(self.cursor)
			
			if self.verbosity > 2:
				self.stdout.write('')
				self.stdout.write("Results for \"%s\":" % query_word)
				self.stdout.write(str(matches))
			
			for i,word in enumerate(matches):
				matches[i]["word"] = matches[i].get("word","")
				if word["length"] < 3 and (word["count"] < 2 or word["quality_index"] >= 1):
					del matches[i]
				elif word["length"] == 2 and word["count"] < 200:
					del matches[i]
				continue
			
			if matches and len(matches):
				words_dbs[query_word]=matches
			
			pass
		
		# TODO povazovat slova za korektne aj ked dosiahnu aspon 0.9 rank z bigramovania - tie potom vyuzit pri kontrole na 0.6
		words_pairs = []
		words_correct = [word.word for word in models.Word.objects.filter(word__in=query_words).filter(locale=locale).all()[:10]]
		words_correct_ids = [word.id for word in models.Word.objects.filter(word__in=query_words).filter(locale=locale).all()[:10]]
		if len(words_correct_ids):
			self.cursor.execute("SELECT `djkorektor_words_pairs`.`left_id`, `djkorektor_words_pairs`.`right_id` FROM `djkorektor_words_pairs` \
				WHERE `djkorektor_words_pairs`.`left_id` IN (%s) \
					OR `djkorektor_words_pairs`.`right_id` IN (%s);" % (",".join([str(word_id) for word_id in words_correct_ids]),",".join([str(word_id) for word_id in words_correct_ids]),))
			matches = dictfetchall(self.cursor)
			words_pairs = [word.word for word in models.Word.objects.filter(Q(id__in=[match["left_id"] for match in matches]) | Q(id__in=[match["right_id"] for match in matches])).filter(locale=locale).all()]
		
		did_you_mean = []
		did_you_mean_markdown = []
		did_you_mean_html = []
		for i,query_word in enumerate(query_words):
			try:
				if query_word.lower() in words_correct:
					raise DJKorektorException("Exact match found, %s is correct." % query_word)
				
				db_rows = words_dbs.get(query_word,[])
				if not len(db_rows):
					raise DJKorektorException("Empty db results for query word %s" % query_word)
				db_row = db_rows[0]
				db_word = db_row["word"]
				
				if db_row.get("ngrams_weight",0) < 0.6:
					for row in db_rows:
						if row["word"] in words_pairs:
							db_word = row["word"]
							break
				
				if query_word.lower() == db_word.lower():
					raise DJKorektorException("Exact match found through bigrams, %s is correct." % query_word)
					
				if query_word.isupper(): db_word = db_word.upper()
				elif query_word.islower(): db_word = db_word.lower()
				elif query_word.istitle(): db_word = db_word.title()
				did_you_mean.append(db_word+query_separators[i])
				did_you_mean_markdown.append((u"*%s*" % db_word)+query_separators[i])
				did_you_mean_html.append((u"<i>%s</i>" % db_word)+query_separators[i])
			except DJKorektorException,e:
				# TOTO raise and catch custom exceptions 
				# preserve word from input
				did_you_mean.append(query_word+query_separators[i])
				did_you_mean_markdown.append(query_word+query_separators[i])
				did_you_mean_html.append(query_word+query_separators[i])
		
		did_you_mean = "".join(did_you_mean)
		did_you_mean_markdown = "".join(did_you_mean_markdown)
		did_you_mean_html = "".join(did_you_mean_html)
		output = OrderedDict()
		output["your_input"] = query
		output["did_you_mean"] = did_you_mean
		output["did_you_mean_markdown"] = did_you_mean_markdown
		output["did_you_mean_html"] = did_you_mean_html
		
		self.stdout.write('') 
		self.stdout.write("Result:")
		for i,k in output.items():
			self.stdout.write("   '%s': %s" % (i,k.encode("utf-8",errors="replace"),))
		self.stdout.write('')
		
		return output
		pass
	
	def do_import_file(self,filepath,locale):
		with codecs.open(filepath, encoding='utf-8') as file:
			for line in file:
				sentences, separators_s = self.split_bysentences(line)
				if len([sentence for sentence in sentences if sentence]):
					for sentence in sentences:
						self.import_sentence(sentence,locale)
		pass
	
	def do_import_word(self,import_word,locale):
		sentences, separators_s = self.split_bysentences(import_word)
		if len([sentence for sentence in sentences if sentence]):
			for sentence in sentences:
				self.import_sentence(sentence,locale)
		pass
	
	def do_import(self):
		
		for source_id in [101,103,301,302,303,304]:
			ads = models.Ad.objects.filter(source_id=source_id).order_by('-date_obj')[:100]
			for ad in ads:
				import_ad_string = ad.title + ". " + ad.description
				words, separators = self.split_bywords(import_ad_string)
				words_in_dictionary_sk = [dict_word.word for dict_word in models.DictionarySK.objects.filter(word__in=words)]
				words_in_dictionary_cs = [dict_word.word for dict_word in models.DictionaryCS.objects.filter(word__in=words)]
				if len(words_in_dictionary_cs) > len(words_in_dictionary_sk):
					locale_code = 'cs_CZ'
				else:
					if ad.location_country == "CZ":
						locale_code = 'cs_CZ'
					else:
						locale_code = 'sk_SK'
				
				if not self.locale or (self.locale and self.locale.code != locale_code):
					self.load_locale(locale_code)
				
				sentences, separators_s = self.split_bysentences(import_ad_string)
				if len([sentence for sentence in sentences if sentence]):
					for sentence in sentences:
						self.import_sentence(sentence,locale)
		
		pass
	
	def handle(self, *args, **options):
		self.verbosity = int(options.get("verbosity",0))
		
		if options["using"]:
			self.using = options["using"]
		
		if self.using:
			self.cursor = connections[self.using].cursor()
		else:
			self.cursor = connection.cursor()
		
		if not options["locale"]:
			self.stderr.write('Unknown locale. use --locale to set specific locale or --help for more args.')
			return
		
		try:
			self.load_locale(options["locale"])
		except Exception,e:
			self.stderr.write(str(e))
			return
		
		# TODO brat do uvahy slovnikovost... zvysit percentualnu vahu
		# TODO slova s pomlckou indexovat aj bez a teda oddelene
		# TODO replace table names with meta settings - model_instance._meta.db_table
		# TODO fix spojene slova ktore by sme mali rozdelit
		
		if options["import_word"]:
			with Timer() as t:
				self.do_import_word(unicode(options["import_word"],encoding="utf-8"),self.locale)
			if self.verbosity > 1:
				self.stdout.write('')
				self.stdout.write('Word import took %.03f sec.' % t.interval)
		if options["import_file"]:
			with Timer() as t:
				self.do_import_file(options["import_file"],self.locale)
			if self.verbosity > 1:
				self.stdout.write('')
				self.stdout.write('Import file took %.03f sec.' % t.interval)
		if options["spell"]:
			with Timer() as t:
				self.do_spelling(unicode(options["spell"],encoding="utf-8"),self.locale)
			if self.verbosity > 1:
				self.stdout.write('')
				self.stdout.write('Spellcheck took %.03f sec.' % t.interval)
		pass