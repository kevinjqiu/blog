theme:
	git clone https://github.com/tmaiaroto/hugo-redlounge.git themes/hugo-redlounge

preview:
	hugo server -t hugo-redlounge -D

publish:
	bin/build.sh
