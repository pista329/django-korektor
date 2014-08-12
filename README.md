Django Korektor
===============

Django Korektor is a brigam based "Did you mean?" proof of concept.

> Have you ever heard about Google's "Did you mean" feature? Django Korektor is a simplified proof of concept based od bigrams intersection between spellchecked query and database set.

Bigrams
---
A bigram or digram is every sequence of two adjacent elements in a string of tokens, which are typically letters, syllables, or words; they are n-grams for n=2. The frequency distribution of bigrams in a string are commonly used for simple statistical analysis of text in many applications, including in computational linguistics, cryptography, speech recognition, and so on. Source: [Wiki](http://en.wikipedia.org/wiki/Bigram)

For example: "Spellcheck" broken down to bigrams will result in [Sp, pe, el, ll, lc, ch, he, ec, ck]

Django Korektor contains optimized database models. Learning management commands to import yoir huge language datasets and finally test spellcheck. It finds closest brigams match, corrects and preserves any separators.

Note
---
Please note, that Django Korektor can't fix a word if you did't learned it. Basically you need to import huge language specific dataset of correct phrases. For example newspaper articles (constant learning from any rss feed). 