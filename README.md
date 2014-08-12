Django Korektor
===============

Django Korektor is a brigam based "Did you mean?" proof of concept.

> Have you ever heard about Google's "Did you mean" feature? Django Korektor is a simplified proof of concept based od bigrams intersection between spellchecked query and database set.

Django Korektor contains optimized database models. Learning management commands to import your huge language datasets and finally test spellcheck. It finds closest bigrams match, corrects and preserves any separators. Database structure should be effecient enough for production use. (e.g. 5 word query checked over 1 million words in 0.3s on cheapest Digital Ocean droplet :)  

Theory
---
Cassical Damereau errors introduced by F.J. Damereau in 1964:
- Substitution 
	``ALPHABET -> ALPHSBET``
- Deletion 
	``ALPHABET -> ALPHBET``
- Insertion 
	``ALPHABET -> ALPHAABET``
- Transposition 
	``ALPHABET -> ALPHBAET``

What is a bigram?
---
A bigram or digram is every sequence of two adjacent elements in a string of tokens, which are typically letters, syllables, or words; they are n-grams for n=2. The frequency distribution of bigrams in a string are commonly used for simple statistical analysis of text in many applications, including in computational linguistics, cryptography, speech recognition, and so on. Source: [Wiki](http://en.wikipedia.org/wiki/Bigram)

For example: "Spellcheck" broken down to bigrams will result in [Sp, pe, el, ll, lc, ch, he, ec, ck]

Example use:
---
Learning from command line:

``$ python manage.py djkorektor --do-import-word="Bigrams are fun! It is raining, let's dance together. It will be my pleasure." --locale=en_US``

Spellcheck test from command line:

``$ python manage.py djkorektor --do-spell="It is fn to dence" --locale=en_US``

Please note
---
- Django Korektor can't fix a word if you did't learned it. Basically you need to import huge language specific dataset of correct phrases. For example a lot of newspaper articles (by constant learning from any rss feed). 
- Django Korektor will only fix certain misspells between words. For example "It is fan to dance" will result as correct phrase.
- Django Korektor usage of context is limited. For example "Icland is icland" will somehow result in "Iceland is iceland"