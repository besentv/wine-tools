#
# Links system compilers to ccache, automatically enabling it for every compilation.
#

sudo mkdir -p /usr/lib/ccache && ls /usr/bin/{,*-}{cc,c++,gcc,g++}{,-[0-9]*} | sed -re s:/bin:/lib/ccache: | xargs -n1 ln -sf ../../bin/ccache
