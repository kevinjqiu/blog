set -e
cwd=$(pwd)
current_time=$(date +%Y-%m-%dT%H%M%S)
hugo -t hugo-redlounge
cd $(mktemp -d)
git clone --depth=1 git@github.com:kevinjqiu/kevinjqiu.github.io.git && cd kevinjqiu.github.io
git checkout -b "build-$current_time"
rm -fr *
echo $cwd
cp "$cwd/CNAME" .
cp -r $cwd/public/* .
git add *
git commit -am "Build @ $current_time"
git push -u origin "build-$current_time"
