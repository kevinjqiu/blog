---
title: "TIL - a static site for your notes"
date: 2018-02-21T00:13:33-05:00
categories: ["effectiveness"]
---

A couple of years ago I was introduced the idea of TIL (Today I Learned) and the habit of noting down things I learned that are note-worthy. Since then I've been looking for a perfect system that would allow me to:

* record what I learned quickly and efficiently
* version control the notes
* browse the notes either via vim or via browser
* search through them using keywords

I tried a couple of ways:

### git repo and use github as frontend

This is the most obvious choice - put notes in a git repo on github. Write in markdown so I can `vim` them while I'm in the terminal. Browsing the notes via the github UI is pretty nice too. *However*, there isn't an easy way to index and search.

### Boostnote

[Boostnote](https://boostnote.io/) is an Electron note taking application. You can use markdown along with some other formats to write the notes. The files are in plain text and is conducive to being version controlled. It has a builtin search engine. It checks all the boxes, except that it cannot be easily viewed from a browser. I cannot go to the github url for my notes repo and browse the notes there, since Boostnote uses .cson with a randomly generated filename so it won't be clear to me what a file is about until I open it...

### Devhints

Recently, I listened to an episode of [TheChangelog](https://changelog.com/podcast) where they interviewed the author of [devhints.io](devhints.io). After that I realized this would be a perfect system for my personal notes as well! [Rico](https://ricostacruz.com/) has built a very nice jekyll theme for his cheatsheat website. It meets all my requirements: simple markdown files so browsing them in terminal is nice. Github-pages builds the Jekyll website automatically on every push to master. The theme generates a keyword index so searching is also covered. The result website is also pretty slick and is better looking than any website I can manage to put together on my own. Big shout out to [@rstacruz](https://twitter.com/rstacruz) for his amazing work!

So here it is: [til.idempotent.ca](http://til.idempotent.ca).
