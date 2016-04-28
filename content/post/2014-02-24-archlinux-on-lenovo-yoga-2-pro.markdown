+++
layout = "post"
title = "Archlinux on Lenovo Yoga 2 Pro"
date = "2014-02-24 21:40:26 -0500"
comments = "true"
published = "false"
categories = ""
+++

My Lenovo Yoga 2 Pro finally arrived last week and of course I put [archlinux](http://www.archlinux.org) on it.

# Why Yoga 2

I needed an ultrabook to accompany my 3-year old Thinkpad T510, and I've been looking at a few ultrabooks. Asus Zenbooks are really slick, and have good specs but they runs about $1700, which is out of my price range. I was briefly tempted by MacBook Airs, but then I was reminded by the fact that Apple products require their proprietary connectors like Thunderbolt, an idea I'm not really fond of. Then I found Lenovo Yoga 2 Pro. They have good reviews online and my 2 Lenovo-built Thinkpads are rock-solid. The screen resolution is ridiculous: 3200 * 1800, a lot higer than the Retina display. Also, the ability to fold and to use it like a tablet is interesting. Moreover, the price tag is competitive compared to other similarly spec'ed ultrabooks. So I decided to give it a try.

# First Impression

Thin, light, slick and elegant -- these are my first impressions as soon as I open the box. Compared to my beefy Thinkpad T510, this is like a feather. The machine comes with Windows 8.1. I'm sure you all know the controversies Windows 8 has generally causing and how much flop it's poised to be. I'm going to spare my rantings on Windows 8 in this post and just say it's not as bad as some people think, but it's not going to be my primary OS.

# First Steps to Freedom

As Windows takes the whole hard drive, step one to freedom involves re-partitioning the hard drive to make room for Linux. The approach I take is to boot an Ubuntu Live CD, and use [gparted](http://gparted.org/). I happen to have an Ubuntu Live CD around, however, laptops now ships with [UEFI](http://en.wikipedia.org/wiki/Unified_Extensible_Firmware_Interface) which has many advantages but generally a pain to setup. I boot into BIOS and enabled legacy boot option and booted up the Live CD.